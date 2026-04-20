from __future__ import annotations

import os
from typing import Literal


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
