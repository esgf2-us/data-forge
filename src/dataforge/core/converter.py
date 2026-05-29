from __future__ import annotations

from importlib import import_module
from pathlib import Path
from urllib.parse import unquote, urlparse

from dataforge.core.input_paths import normalize_input_for_runtime
from dataforge.core.storage import StorageWriter
from dataforge.core.validation import preflight_validate
from dataforge.models.config import (
    ConversionConfig,
    ConversionError,
    ConversionResult,
    InvalidInputError,
)


def _input_format(path: str) -> str:
    with Path(path).open("rb") as f:
        magic = f.read(8)
    if magic.startswith(b"\x89HDF\r\n\x1a\n"):
        return "hdf5"
    if magic[:3] == b"CDF":
        return "netcdf3"
    return "unknown"


def _single_file_reference(path: str, inline_threshold: int) -> dict:
    file_format = _input_format(path)

    try:
        if file_format == "netcdf3":
            converter = import_module("kerchunk.netCDF3").NetCDF3ToZarr
            return converter(path, inline_threshold=inline_threshold).translate()

        converter = import_module("kerchunk.hdf").SingleHdf5ToZarr
        return converter(path, inline_threshold=inline_threshold).translate()
    except ImportError as e:
        if file_format == "netcdf3" and "Scipy is required" in str(e):
            raise ConversionError(
                "input file appears to be classic NetCDF3; install scipy to enable kerchunk.netCDF3 conversion"
            ) from e
        raise
    except OSError as e:
        if file_format == "unknown":
            raise ConversionError(
                "input file is not recognized as HDF5/NetCDF4 or classic NetCDF3"
            ) from e
        raise


def _normalize_input(uri: str) -> str:
    return normalize_input_for_runtime(uri)


def _join_output(prefix: str, name: str) -> str:
    if prefix.startswith("s3://"):
        return f"{prefix.rstrip('/')}/{name}.json"

    if prefix.startswith("file://"):
        parsed = urlparse(prefix)
        if parsed.netloc not in ("", "localhost"):
            raise InvalidInputError(f"unsupported file URI netloc: {parsed.netloc!r}")
        base = Path(unquote(parsed.path)).expanduser().resolve()
        return (base / f"{name}.json").as_uri()

    return str(Path(prefix).expanduser().resolve() / f"{name}.json")


class KerchunkConverter:
    def __init__(self, storage: StorageWriter | None = None) -> None:
        self._storage = storage or StorageWriter()

    def convert(self, inputs: list[str], config: ConversionConfig) -> ConversionResult:
        if not inputs:
            raise InvalidInputError("inputs must be non-empty")

        preflight_validate(inputs, config)

        resolved_inputs = [_normalize_input(u) for u in inputs]
        output_uri = _join_output(config.output_prefix, config.output_name)

        reference = self._build_reference(resolved_inputs, config)
        self._storage.write_json(
            output_uri, reference, overwrite=config.overwrite_existing
        )

        return ConversionResult(
            output_uri=output_uri, reference=reference, inputs=resolved_inputs
        )

    def _build_reference(self, inputs: list[str], config: ConversionConfig) -> dict:
        try:
            from kerchunk.combine import MultiZarrToZarr

            refs = [
                _single_file_reference(p, inline_threshold=config.inline_threshold)
                for p in inputs
            ]

            if len(refs) == 1:
                return refs[0]

            mzz = MultiZarrToZarr(
                refs,
                concat_dims=list(config.concat_dims),
                identical_dims=list(config.identical_dims or []),
            )
            return mzz.translate()
        except Exception as e:
            raise ConversionError(str(e)) from e
