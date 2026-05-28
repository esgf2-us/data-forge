from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from dataforge.core.storage import StorageWriter
from dataforge.core.validation import preflight_validate
from dataforge.models.config import (
    ConversionConfig,
    ConversionError,
    ConversionResult,
    InvalidInputError,
)


def _normalize_local_input(uri: str) -> str:
    if uri.startswith("file://"):
        parsed = urlparse(uri)
        if parsed.netloc not in ("", "localhost"):
            raise InvalidInputError(f"unsupported file URI netloc: {parsed.netloc!r}")
        path = Path(unquote(parsed.path))
    else:
        parsed = urlparse(uri)
        if parsed.scheme:
            raise InvalidInputError(f"unsupported input scheme: {parsed.scheme!r}")
        path = Path(uri)

    path = path.expanduser().resolve()
    if not path.exists():
        raise InvalidInputError(f"input file does not exist: {path}")
    return str(path)


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

        local_inputs = [_normalize_local_input(u) for u in inputs]
        output_uri = _join_output(config.output_prefix, config.output_name)

        reference = self._build_reference(local_inputs, config)
        self._storage.write_json(
            output_uri, reference, overwrite=config.overwrite_existing
        )

        return ConversionResult(
            output_uri=output_uri, reference=reference, inputs=local_inputs
        )

    def _build_reference(self, inputs: list[str], config: ConversionConfig) -> dict:
        try:
            from kerchunk.combine import MultiZarrToZarr
            from kerchunk.hdf import SingleHdf5ToZarr

            refs = [
                SingleHdf5ToZarr(
                    p, inline_threshold=config.inline_threshold
                ).translate()
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
