from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from dataforge.models.config import (
    ConversionConfig,
    InvalidConfigError,
    InvalidInputError,
)


def validate_dataset_id(dataset_id: str) -> str:
    value = dataset_id.strip()
    if not value:
        raise InvalidInputError("dataset_id must be non-empty")
    parts = [part for part in value.split(".") if part]
    if len(parts) < 2:
        raise InvalidInputError(
            "dataset_id must contain at least a project and dataset components"
        )
    if any(any(ch.isspace() for ch in part) for part in parts):
        raise InvalidInputError("dataset_id must not contain whitespace")
    return value


def preflight_validate(inputs: list[str], config: ConversionConfig) -> None:
    if not inputs:
        raise InvalidInputError("inputs must be non-empty")

    for value in inputs:
        path = _normalize_local_path(value)
        if not path.exists():
            raise InvalidInputError(f"input file does not exist: {path}")
        if not path.is_file():
            raise InvalidInputError(f"input path is not a file: {path}")
        _validate_hdf5_readable(path)

    _validate_output_prefix(config.output_prefix)


def _normalize_local_path(value: str) -> Path:
    if value.startswith("file://"):
        parsed = urlparse(value)
        if parsed.netloc not in ("", "localhost"):
            raise InvalidInputError(f"unsupported file URI netloc: {parsed.netloc!r}")
        path = Path(unquote(parsed.path))
    else:
        parsed = urlparse(value)
        if parsed.scheme:
            raise InvalidInputError(f"unsupported input scheme: {parsed.scheme!r}")
        path = Path(value)
    return path.expanduser().resolve()


def _validate_hdf5_readable(path: Path) -> None:
    try:
        import h5py

        with h5py.File(path, "r"):
            return
    except OSError as e:
        raise InvalidInputError(
            f"input file is not a readable HDF5/NetCDF file: {path}"
        ) from e


def _validate_output_prefix(prefix: str) -> None:
    if prefix.startswith("s3://"):
        parsed = urlparse(prefix)
        if not parsed.netloc:
            raise InvalidConfigError("output_prefix must include an S3 bucket")
        return

    if prefix.startswith("file://"):
        parsed = urlparse(prefix)
        if parsed.netloc not in ("", "localhost"):
            raise InvalidConfigError(f"unsupported file URI netloc: {parsed.netloc!r}")
        path = Path(unquote(parsed.path)).expanduser().resolve()
    else:
        path = Path(prefix).expanduser().resolve()

    candidate = path if path.exists() else path.parent
    if not candidate.exists():
        candidate.mkdir(parents=True, exist_ok=True)
    if not candidate.is_dir():
        raise InvalidConfigError(
            f"output prefix parent is not a directory: {candidate}"
        )
