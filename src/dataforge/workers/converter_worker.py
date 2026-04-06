from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

import dramatiq
from dramatiq.brokers.redis import RedisBroker

from dataforge.core.converter import KerchunkConverter
from dataforge.job_store.base import JobStore
from dataforge.job_store.redis import RedisJobStore
from dataforge.models.config import ConversionConfig
from dataforge.models.job import JobStatus
from dataforge.settings import redis_broker_url, redis_jobstore_url


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
    if job.status == JobStatus.CANCELLED:
        return

    try:
        store.set_status(job_id, expected=JobStatus.QUEUED, new=JobStatus.RUNNING)
    except Exception:
        # Cancellation takes precedence over all other terminal outcomes.
        if store.get(job_id).status == JobStatus.CANCELLED:
            return
        raise

    store.set_progress(job_id, done=0, total=1)

    try:
        submission = store.get(job_id).submission
        cfg = ConversionConfig(
            output_prefix=submission.output_path,
            output_name=submission.output_name or job_id,
            inline_threshold=submission.inline_threshold,
            concat_dims=list(submission.concat_dims),
            identical_dims=(
                list(submission.identical_dims)
                if submission.identical_dims is not None
                else None
            ),
        )

        converter = KerchunkConverter()
        res = converter.convert(list(submission.input_files), cfg)
        output_uri = getattr(res, "output_uri", res)

        # Re-check status before writing terminal state.
        if store.get(job_id).status == JobStatus.CANCELLED:
            return

        store.set_progress(job_id, done=1, total=1)

        result_url = str(output_uri)
        if submission.output_mode == "local":
            result_url = _local_result_url(result_url)

        store.set_result(job_id, result_url)

        # Re-check once more before status terminal write.
        if store.get(job_id).status == JobStatus.CANCELLED:
            return

        store.set_status(job_id, expected=JobStatus.RUNNING, new=JobStatus.COMPLETED)
    except Exception as e:
        if store.get(job_id).status == JobStatus.CANCELLED:
            return

        store.set_error(job_id, str(e))
        cur = store.get(job_id)
        if cur.status == JobStatus.RUNNING:
            store.set_status(job_id, expected=JobStatus.RUNNING, new=JobStatus.FAILED)


dramatiq.set_broker(RedisBroker(url=redis_broker_url()))


@dramatiq.actor
def convert_job(job_id: str) -> None:
    store = RedisJobStore(redis_jobstore_url())
    try:
        run_job(store, job_id)
    except Exception as e:
        # Best-effort error marking if run_job failed unexpectedly.
        try:
            if store.get(job_id).status != JobStatus.CANCELLED:
                store.set_error(job_id, str(e))
                if store.get(job_id).status == JobStatus.RUNNING:
                    store.set_status(
                        job_id, expected=JobStatus.RUNNING, new=JobStatus.FAILED
                    )
        finally:
            raise
