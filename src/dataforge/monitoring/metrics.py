from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


JOBS_SUBMITTED = Counter(
    "dataforge_jobs_submitted_total",
    "Total number of jobs submitted.",
)
JOBS_COMPLETED = Counter(
    "dataforge_jobs_completed_total",
    "Total number of jobs completed successfully.",
)
JOBS_FAILED = Counter(
    "dataforge_jobs_failed_total",
    "Total number of jobs failed.",
)
JOB_DURATION_SECONDS = Histogram(
    "dataforge_job_duration_seconds",
    "End-to-end job duration in seconds.",
)
FILES_PROCESSED_PER_SECOND = Histogram(
    "dataforge_files_processed_per_second",
    "Observed file processing throughput for completed jobs.",
)
API_REQUEST_LATENCY_SECONDS = Histogram(
    "dataforge_api_request_latency_seconds",
    "HTTP request latency by method and path.",
    labelnames=("method", "path"),
)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
