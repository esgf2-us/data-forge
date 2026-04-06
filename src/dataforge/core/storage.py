from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import fsspec

from dataforge.models.config import WriteError


def _file_uri_to_path(uri: str) -> Path | None:
    if not uri.startswith("file://"):
        return None

    parsed = urlparse(uri)
    if parsed.netloc not in ("", "localhost"):
        raise WriteError(f"unsupported file URI netloc: {parsed.netloc!r}")

    return Path(unquote(parsed.path))


class StorageWriter:
    def write_json(self, output_uri: str, data: dict[str, Any]) -> None:
        payload = json.dumps(data).encode("utf-8")

        try:
            file_path = _file_uri_to_path(output_uri)
            if file_path is not None:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with fsspec.open(str(file_path), "wb") as f:
                    f.write(payload)
                return

            if output_uri.startswith("s3://"):
                with fsspec.open(output_uri, "wb") as f:
                    f.write(payload)
                return

            local_path = Path(output_uri)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            with fsspec.open(str(local_path), "wb") as f:
                f.write(payload)
        except WriteError:
            raise
        except Exception as e:
            raise WriteError(str(e)) from e
