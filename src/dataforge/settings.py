from __future__ import annotations

import os


def redis_jobstore_url() -> str:
    return os.getenv("DATAFORGE_REDIS_URL", "redis://localhost:6379/1")


def redis_broker_url() -> str:
    return os.getenv("DATAFORGE_BROKER_REDIS_URL", "redis://localhost:6379/0")


def s3_endpoint_url() -> str | None:
    return os.getenv("DATAFORGE_S3_ENDPOINT_URL")
