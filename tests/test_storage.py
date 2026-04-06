import json
from pathlib import Path
from unittest.mock import patch


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
