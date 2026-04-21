import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest


def test_storage_writer_writes_local_json(tmp_path: Path) -> None:
    from dataforge.core.storage import StorageWriter

    out = tmp_path / "out" / "ref.json"
    StorageWriter().write_json(str(out), {"a": 1})

    assert out.exists()
    assert json.loads(out.read_text("utf-8")) == {"a": 1}


def test_storage_writer_supports_file_uri_outputs(tmp_path: Path) -> None:
    from dataforge.core.storage import StorageWriter

    out = tmp_path / "out" / "ref.json"
    StorageWriter().write_json(f"file://{out}", {"a": 1})

    assert out.exists()
    assert json.loads(out.read_text("utf-8")) == {"a": 1}


def test_storage_writer_uses_fsspec_for_s3_uri() -> None:
    from dataforge.core.storage import StorageWriter

    with patch("dataforge.core.storage.fsspec.open") as open_mock:
        StorageWriter().write_json("s3://bucket/prefix/ref.json", {"a": 1})

    assert open_mock.called


def test_storage_writer_passes_endpoint_url_for_s3_when_configured() -> None:
    from dataforge.core.storage import StorageWriter

    with patch.dict(
        os.environ,
        {"DATAFORGE_S3_ENDPOINT_URL": "http://garage:3900"},
        clear=False,
    ):
        with patch("dataforge.core.storage.fsspec.open") as open_mock:
            StorageWriter().write_json("s3://bucket/prefix/ref.json", {"a": 1})

    _args, kwargs = open_mock.call_args
    assert kwargs["client_kwargs"]["endpoint_url"] == "http://garage:3900"
    assert kwargs["client_kwargs"]["region_name"] == "garage"
    assert kwargs["config_kwargs"]["s3"]["addressing_style"] == "path"


def test_storage_writer_wraps_permission_errors_for_local_outputs(
    tmp_path: Path,
) -> None:
    from dataforge.core.storage import StorageWriter
    from dataforge.models.config import WriteError

    out = tmp_path / "out" / "ref.json"

    def _deny(*args, **kwargs):
        raise PermissionError("denied")

    with patch("dataforge.core.storage.fsspec.open", side_effect=_deny):
        with pytest.raises(WriteError, match="permission denied writing"):
            StorageWriter().write_json(str(out), {"a": 1})


def test_storage_writer_wraps_permission_errors_when_creating_parent_dir(
    tmp_path: Path,
) -> None:
    from dataforge.core.storage import StorageWriter
    from dataforge.models.config import WriteError

    out = tmp_path / "out" / "ref.json"

    with patch("pathlib.Path.mkdir", side_effect=PermissionError("denied")):
        with pytest.raises(WriteError, match="permission denied writing"):
            StorageWriter().write_json(str(out), {"a": 1})
