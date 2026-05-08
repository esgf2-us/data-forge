from __future__ import annotations

import os
from typing import Literal

from dataforge.models.dask_config import DaskConfig


def redis_jobstore_url() -> str:
    return os.getenv("DATAFORGE_REDIS_URL", "redis://localhost:6379/1")


def redis_broker_url() -> str:
    return os.getenv("DATAFORGE_BROKER_REDIS_URL", "redis://localhost:6379/0")


def output_mode() -> Literal["local", "s3"]:
    value = os.getenv("DATAFORGE_OUTPUT_MODE", "local").strip().lower()
    if value not in {"local", "s3"}:
        raise ValueError("DATAFORGE_OUTPUT_MODE must be one of: local, s3")
    return value


def local_output_path() -> str | None:
    value = os.getenv("DATAFORGE_LOCAL_OUTPUT_PATH")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def s3_output_path() -> str | None:
    value = os.getenv("DATAFORGE_S3_OUTPUT_PATH")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def s3_endpoint_url() -> str | None:
    return os.getenv("DATAFORGE_S3_ENDPOINT_URL")


def dask_config() -> DaskConfig:
    """Build DaskConfig from environment variables."""
    n_workers_raw = os.getenv("DATAFORGE_DASK_N_WORKERS")
    n_workers = int(n_workers_raw) if n_workers_raw else None

    threads_raw = os.getenv("DATAFORGE_DASK_THREADS_PER_WORKER", "1")
    threads_per_worker = int(threads_raw)

    memory_limit = os.getenv("DATAFORGE_DASK_MEMORY_LIMIT", "2GiB")

    processes_raw = os.getenv("DATAFORGE_DASK_PROCESSES", "true").strip().lower()
    processes = processes_raw in ("true", "1", "yes")

    threshold_raw = os.getenv("DATAFORGE_DASK_PARALLEL_THRESHOLD", "4")
    parallel_threshold = int(threshold_raw)

    return DaskConfig(
        n_workers=n_workers,
        threads_per_worker=threads_per_worker,
        memory_limit=memory_limit,
        processes=processes,
        parallel_threshold=parallel_threshold,
    )
