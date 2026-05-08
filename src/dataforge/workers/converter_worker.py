from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import unquote, urlparse

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from dataforge.core.dask_converter import DaskConverter
from dataforge.job_store.base import JobStore
from dataforge.job_store.redis import RedisJobStore
from dataforge.models.config import ConversionConfig
from dataforge.models.job import JobStatus, default_local_output_name
from dataforge.settings import dask_config, redis_broker_url, redis_jobstore_url


logger = logging.getLogger(__name__)


def _ensure_worker_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )


def _local_result_url(output_uri: str) -> str:
    # Return an absolute file:// URL for local outputs.
    if output_uri.startswith("file://"):
        parsed = urlparse(output_uri)
        p = Path(unquote(parsed.path)).resolve()
        return p.as_uri()
    return Path(output_uri).resolve().as_uri()


def run_job(store: JobStore, job_id: str) -> None:
    """Run a single conversion job.

    This is a pure helper: all side effects happen through the injected JobStore
    and via the KerchunkConverter.
    """

    job = store.get(job_id)
    logger.info(
        "worker job loaded", extra={"job_id": job_id, "status": job.status.value}
    )
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        logger.info(
            "worker job already terminal",
            extra={"job_id": job_id, "status": job.status.value},
        )
        return
    if job.status == JobStatus.RUNNING:
        logger.info("worker job already running", extra={"job_id": job_id})
        return

    try:
        store.set_status(job_id, expected=JobStatus.QUEUED, new=JobStatus.RUNNING)
        logger.info("worker job started", extra={"job_id": job_id})
    except ValueError as e:
        # Another worker or a cancel beat us.
        if "status mismatch" in str(e):
            logger.info(
                "worker job status changed before start", extra={"job_id": job_id}
            )
            return
        raise

    submission = store.get(job_id).submission
    total = len(submission.input_files)
    store.set_progress(job_id, done=0, total=total)
    logger.info(
        "worker job progress updated",
        extra={"job_id": job_id, "progress_done": 0, "progress_total": total},
    )

    try:
        submission = store.get(job_id).submission
        output_name = submission.output_name
        if output_name is None and submission.output_mode == "local":
            output_name = default_local_output_name(submission.input_files)
        if output_name is None:
            output_name = job_id

        cfg = ConversionConfig(
            output_prefix=submission.output_path,
            output_name=output_name,
            inline_threshold=submission.inline_threshold,
            concat_dims=list(submission.concat_dims),
            identical_dims=(
                list(submission.identical_dims)
                if submission.identical_dims is not None
                else None
            ),
            overwrite_existing=submission.overwrite_existing,
        )

        def _on_progress(done: int, total_files: int) -> None:
            store.set_progress(job_id, done=done, total=total_files)
            logger.info(
                "worker dask progress",
                extra={"job_id": job_id, "done": done, "total": total_files},
            )

        converter = DaskConverter(dask_config=dask_config())
        res = converter.convert(
            list(submission.input_files), cfg, on_progress=_on_progress
        )
        output_uri = getattr(res, "output_uri", res)
        logger.info("worker conversion finished", extra={"job_id": job_id})

        # Re-check status before writing terminal state.
        if store.get(job_id).status == JobStatus.CANCELLED:
            return

        store.set_progress(job_id, done=total, total=total)
        logger.info(
            "worker job progress updated",
            extra={
                "job_id": job_id,
                "progress_done": total,
                "progress_total": total,
            },
        )

        result_url = str(output_uri)
        if submission.output_mode == "local":
            result_url = _local_result_url(result_url)

        store.set_result(job_id, result_url)
        logger.info("worker job result stored", extra={"job_id": job_id})

        # Re-check once more before status terminal write.
        if store.get(job_id).status == JobStatus.CANCELLED:
            return

        try:
            store.set_status(
                job_id, expected=JobStatus.RUNNING, new=JobStatus.COMPLETED
            )
            logger.info("worker job completed", extra={"job_id": job_id})
        except ValueError as e:
            if "status mismatch" in str(e):
                logger.info(
                    "worker job completion skipped due to status change",
                    extra={"job_id": job_id},
                )
                return
            raise
    except Exception as e:
        if store.get(job_id).status == JobStatus.CANCELLED:
            logger.info(
                "worker job cancelled during execution", extra={"job_id": job_id}
            )
            return

        store.set_error(job_id, str(e))
        logger.exception("worker job failed", extra={"job_id": job_id})
        cur = store.get(job_id)
        if cur.status == JobStatus.RUNNING:
            try:
                store.set_status(
                    job_id, expected=JobStatus.RUNNING, new=JobStatus.FAILED
                )
                logger.info("worker job marked failed", extra={"job_id": job_id})
            except ValueError as e:
                if "status mismatch" in str(e):
                    logger.info(
                        "worker job failure skipped due to status change",
                        extra={"job_id": job_id},
                    )
                    return
                raise


dramatiq.set_broker(RedisBroker(url=redis_broker_url()))


@dramatiq.actor
def convert_job(job_id: str) -> None:
    _ensure_worker_logging()
    store = RedisJobStore(redis_jobstore_url())
    logger.info("worker actor received job", extra={"job_id": job_id})
    try:
        run_job(store, job_id)
    except Exception as e:
        # Best-effort error marking if run_job failed unexpectedly.
        logger.exception("worker actor failed", extra={"job_id": job_id})
        try:
            if store.get(job_id).status != JobStatus.CANCELLED:
                store.set_error(job_id, str(e))
                if store.get(job_id).status == JobStatus.RUNNING:
                    store.set_status(
                        job_id, expected=JobStatus.RUNNING, new=JobStatus.FAILED
                    )
        finally:
            raise
