from __future__ import annotations

import glob
import os
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse

from dataforge.models.config import InvalidInputError
from dataforge.settings import local_input_mappings


def input_is_s3(value: str) -> bool:
    return value.startswith("s3://")


def input_is_local(value: str) -> bool:
    if not value:
        return False
    if input_is_s3(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("", "file") and parsed.netloc in ("", "localhost")


def validate_input_reference(value: str) -> str:
    if not value:
        raise InvalidInputError("input_files entries must be non-empty")

    if input_is_s3(value):
        parsed = urlparse(value)
        if not parsed.netloc:
            raise InvalidInputError("s3 input must include a bucket")
        return value

    parsed = urlparse(value)
    if parsed.scheme == "file":
        if parsed.netloc not in ("", "localhost"):
            raise InvalidInputError("input_files must reference local paths or s3 URLs")
        if not parsed.path:
            raise InvalidInputError("input_files must reference local paths or s3 URLs")
        return value

    if parsed.scheme:
        raise InvalidInputError(f"unsupported input scheme: {parsed.scheme!r}")
    if parsed.netloc:
        raise InvalidInputError("input_files must reference local paths or s3 URLs")
    return value


def normalize_input_for_runtime(value: str) -> str:
    validate_input_reference(value)
    if input_is_s3(value):
        return value

    host_path = _local_host_path(value)
    mappings = local_input_mappings()
    if not mappings:
        return str(host_path)

    host_path_str = str(host_path)
    for host_prefix, container_prefix in sorted(
        mappings, key=lambda item: len(item[0]), reverse=True
    ):
        if host_path_str == host_prefix:
            return container_prefix
        prefix = f"{host_prefix}{os.sep}"
        if host_path_str.startswith(prefix):
            suffix = host_path_str[len(prefix) :]
            return str(PurePosixPath(container_prefix) / suffix.replace(os.sep, "/"))

    raise InvalidInputError(
        f"input path is not covered by DATAFORGE_LOCAL_INPUT_MAPPINGS: {host_path}"
    )


def expand_input_for_runtime(value: str) -> list[str]:
    validate_input_reference(value)
    if input_is_s3(value):
        return [value]

    pattern = normalize_input_for_runtime(value)
    if not glob.has_magic(pattern):
        return [pattern]

    matches = sorted(glob.glob(pattern, recursive=True))
    if not matches:
        raise InvalidInputError(f"no local input files matched pattern: {value}")

    return [externalize_runtime_path(str(Path(match).expanduser().resolve())) for match in matches]


def externalize_runtime_path(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        if parsed.netloc not in ("", "localhost"):
            raise InvalidInputError("unsupported file URI netloc for runtime path")
        runtime_path = Path(unquote(parsed.path)).expanduser().resolve()
    else:
        runtime_path = Path(value).expanduser().resolve()

    mappings = local_input_mappings()
    if not mappings:
        return str(runtime_path)

    runtime_path_str = str(runtime_path)
    for host_prefix, container_prefix in sorted(
        mappings, key=lambda item: len(item[1]), reverse=True
    ):
        if runtime_path_str == container_prefix:
            return host_prefix
        prefix = f"{container_prefix}{os.sep}"
        if runtime_path_str.startswith(prefix):
            suffix = runtime_path_str[len(prefix) :]
            return str(PurePosixPath(host_prefix) / suffix.replace(os.sep, "/"))

    return str(runtime_path)


def local_input_host_path(value: str) -> Path:
    validate_input_reference(value)
    if input_is_s3(value):
        raise InvalidInputError("s3 inputs do not have a local filesystem path")
    return _local_host_path(value)


def input_name_stem(value: str) -> str:
    validate_input_reference(value)
    if input_is_s3(value):
        parsed = urlparse(value)
        path = PurePosixPath(parsed.path)
        return Path(path.name).stem or "reference"
    return local_input_host_path(value).stem or "reference"


def _local_host_path(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path))
    else:
        path = Path(value)
    return path.expanduser().resolve()
