from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from dataforge.core.dask_converter import DaskConverter
from dataforge.core.esgf_publisher import publishable_href
from dataforge.core.metadata import build_result_metadata
from dataforge.core.stac_client import ESGPublisherStacClient
from dataforge.job_store.base import JobStore
from dataforge.job_store.redis import RedisJobStore
from dataforge.models.config import ConversionConfig
from dataforge.models.job import JobPublication, JobStatus, default_local_output_name
from dataforge.monitoring.metrics import (
    FILES_PROCESSED_PER_SECOND,
    JOBS_COMPLETED,
    JOBS_FAILED,
    JOB_DURATION_SECONDS,
)
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
        store.set_result_metadata(
            job_id,
            build_result_metadata(
                inputs=list(submission.input_files),
                output_uri=str(output_uri),
                dataset_id=submission.dataset_id,
                user_metadata=submission.metadata,
            ),
        )
        logger.info("worker job metadata stored", extra={"job_id": job_id})

        if submission.publish_to_stac:
            publish_href = publishable_href(
                str(output_uri),
                use_local_output_as_href=submission.use_local_output_as_href,
            )
            try:
                publication = ESGPublisherStacClient().publish_kerchunk(
                    dataset_id=submission.dataset_id or "",
                    href=publish_href,
                    datanode=submission.datanode,
                )
                store.set_publication(job_id, publication)
                logger.info("worker job publication stored", extra={"job_id": job_id})
            except Exception as e:
                store.set_publication(
                    job_id,
                    JobPublication(
                        dataset_id=submission.dataset_id or "",
                        collection="",
                        item_id=submission.dataset_id or "",
                        aggregate_type="kerchunk",
                        href=publish_href,
                        datanode=submission.datanode or "",
                        asset_path="/assets/reference_file",
                        patch_applied=False,
                        published_at=datetime.now(timezone.utc),
                        error_message=str(e),
                    ),
                )
                raise

        # Re-check once more before status terminal write.
        if store.get(job_id).status == JobStatus.CANCELLED:
            return

        try:
            store.set_status(
                job_id, expected=JobStatus.RUNNING, new=JobStatus.COMPLETED
            )
            completed = store.get(job_id)
            if completed.started_at is not None and completed.completed_at is not None:
                duration = (
                    completed.completed_at - completed.started_at
                ).total_seconds()
                if duration > 0:
                    JOB_DURATION_SECONDS.observe(duration)
                    FILES_PROCESSED_PER_SECOND.observe(total / duration)
            JOBS_COMPLETED.inc()
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
                JOBS_FAILED.inc()
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
