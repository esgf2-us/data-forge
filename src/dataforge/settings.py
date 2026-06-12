from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Literal

from dataforge.models.dask_config import DaskConfig


def redis_jobstore_url() -> str:
    return os.getenv("DATAFORGE_REDIS_URL", "redis://localhost:6379/1")


def redis_broker_url() -> str:
    return os.getenv("DATAFORGE_BROKER_REDIS_URL", "redis://localhost:6379/0")


def api_keys() -> set[str]:
    keys: set[str] = set()

    value = os.getenv("DATAFORGE_API_KEYS")
    if value:
        for item in value.split(","):
            stripped = item.strip()
            if stripped:
                keys.add(stripped)

    return keys


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


def stac_api() -> str | None:
    value = os.getenv("DATAFORGE_STAC_API")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def stac_transaction_api() -> str | None:
    value = os.getenv("DATAFORGE_STAC_TRANSACTION_API")
    if value is None:
        return stac_api()
    stripped = value.strip()
    return stripped or stac_api()


def stac_datanode() -> str | None:
    value = os.getenv("DATAFORGE_STAC_DATANODE")
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def stac_config_json() -> dict:
    value = os.getenv("DATAFORGE_STAC_CONFIG_JSON")
    if value is None:
        return {}
    stripped = value.strip()
    if not stripped:
        return {}
    data = json.loads(stripped)
    if not isinstance(data, dict):
        raise ValueError("DATAFORGE_STAC_CONFIG_JSON must decode to an object")
    return data


def stac_href_mappings() -> list[tuple[str, str]]:
    value = os.getenv("DATAFORGE_STAC_HREF_MAPPINGS")
    if value is None:
        return []
    stripped = value.strip()
    if not stripped:
        return []

    data = json.loads(stripped)
    if not isinstance(data, list):
        raise ValueError("DATAFORGE_STAC_HREF_MAPPINGS must decode to a list")

    mappings: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("DATAFORGE_STAC_HREF_MAPPINGS entries must be objects")
        local_prefix = item.get("local_prefix")
        public_prefix = item.get("public_prefix")
        if not isinstance(local_prefix, str) or not local_prefix.strip():
            raise ValueError(
                "DATAFORGE_STAC_HREF_MAPPINGS local_prefix must be non-empty"
            )
        if not isinstance(public_prefix, str) or not public_prefix.strip():
            raise ValueError(
                "DATAFORGE_STAC_HREF_MAPPINGS public_prefix must be non-empty"
            )
        mappings.append((str(Path(local_prefix).resolve()), public_prefix.rstrip("/")))
    return mappings


def local_input_mappings() -> list[tuple[str, str]]:
    value = os.getenv("DATAFORGE_LOCAL_INPUT_MAPPINGS")
    if value is None:
        return []
    stripped = value.strip()
    if not stripped:
        return []

    data = json.loads(stripped)
    if not isinstance(data, list):
        raise ValueError("DATAFORGE_LOCAL_INPUT_MAPPINGS must decode to a list")

    mappings: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("DATAFORGE_LOCAL_INPUT_MAPPINGS entries must be objects")
        host_prefix = item.get("host_prefix")
        container_prefix = item.get("container_prefix")
        if not isinstance(host_prefix, str) or not host_prefix.strip():
            raise ValueError(
                "DATAFORGE_LOCAL_INPUT_MAPPINGS host_prefix must be non-empty"
            )
        if not isinstance(container_prefix, str) or not container_prefix.strip():
            raise ValueError(
                "DATAFORGE_LOCAL_INPUT_MAPPINGS container_prefix must be non-empty"
            )
        mappings.append(
            (
                str(Path(host_prefix).expanduser().resolve()),
                container_prefix.rstrip("/"),
            )
        )
    return mappings


def cors_allowed_origins() -> list[str]:
    value = os.getenv("DATAFORGE_CORS_ALLOWED_ORIGINS", "*")
    origins = [origin.strip() for origin in value.split(",") if origin.strip()]
    return origins or ["*"]


def dask_config() -> DaskConfig:
    """Build DaskConfig from environment variables."""
    n_workers_raw = os.getenv("DATAFORGE_DASK_N_WORKERS")
    n_workers = int(n_workers_raw) if n_workers_raw else None

    threads_raw = os.getenv("DATAFORGE_DASK_THREADS_PER_WORKER", "1")
    threads_per_worker = int(threads_raw)

    memory_limit = os.getenv("DATAFORGE_DASK_MEMORY_LIMIT", "2GiB")
    local_directory = os.getenv("DATAFORGE_DASK_LOCAL_DIRECTORY")

    processes_raw = os.getenv("DATAFORGE_DASK_PROCESSES", "true").strip().lower()
    processes = processes_raw in ("true", "1", "yes")

    threshold_raw = os.getenv("DATAFORGE_DASK_PARALLEL_THRESHOLD", "4")
    parallel_threshold = int(threshold_raw)

    return DaskConfig(
        n_workers=n_workers,
        threads_per_worker=threads_per_worker,
        memory_limit=memory_limit,
        local_directory=local_directory,
        processes=processes,
        parallel_threshold=parallel_threshold,
    )
