"""Unit tests for the DaskConverter module."""

from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from dataforge.core.dask_converter import DaskConverter, _generate_single_reference
from dataforge.models.config import ConversionConfig, ConversionError, InvalidInputError
from dataforge.models.dask_config import DaskConfig


# ---------------------------------------------------------------------------
# DaskConfig validation
# ---------------------------------------------------------------------------


def test_dask_config_defaults() -> None:
    cfg = DaskConfig()
    assert cfg.n_workers is None
    assert cfg.threads_per_worker == 1
    assert cfg.memory_limit == "2GiB"
    assert cfg.local_directory is None
    assert cfg.processes is True
    assert cfg.parallel_threshold == 4


def test_dask_config_rejects_zero_threads() -> None:
    with pytest.raises(ValueError, match="threads_per_worker must be >= 1"):
        DaskConfig(threads_per_worker=0)


def test_dask_config_rejects_zero_threshold() -> None:
    with pytest.raises(ValueError, match="parallel_threshold must be >= 1"):
        DaskConfig(parallel_threshold=0)


def test_dask_config_normalizes_blank_local_directory() -> None:
    cfg = DaskConfig(local_directory="   ")
    assert cfg.local_directory is None


# ---------------------------------------------------------------------------
# Fallback to sequential converter below threshold
# ---------------------------------------------------------------------------


def test_below_threshold_delegates_to_sequential(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With fewer inputs than parallel_threshold, DaskConverter uses sequential path."""
    from dataforge.core.converter import KerchunkConverter

    in_file = tmp_path / "a.nc"
    in_file.write_bytes(b"dummy")
    out_dir = tmp_path / "out"

    cfg = ConversionConfig(output_prefix=str(out_dir), output_name="result")
    dask_cfg = DaskConfig(parallel_threshold=5)

    called = {}

    def _fake_convert(self, inputs, config):
        called["yes"] = True
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "result.json").write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(out_dir / "result.json"), reference={}, inputs=inputs
        )

    monkeypatch.setattr(KerchunkConverter, "convert", _fake_convert)
    monkeypatch.setattr("dataforge.core.dask_converter.preflight_validate", lambda inputs, config: None)

    converter = DaskConverter(dask_config=dask_cfg)
    result = converter.convert([str(in_file)], cfg)

    assert called.get("yes")
    assert "result.json" in result.output_uri


# ---------------------------------------------------------------------------
# Parallel path (mocked Dask)
# ---------------------------------------------------------------------------


def test_above_threshold_uses_dask_parallel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """With inputs >= parallel_threshold, DaskConverter uses the Dask path."""
    # Create enough input files to exceed threshold.
    dask_cfg = DaskConfig(parallel_threshold=2)
    files = []
    for i in range(3):
        f = tmp_path / f"input_{i}.nc"
        f.write_bytes(b"dummy")
        files.append(str(f))

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    cfg = ConversionConfig(output_prefix=str(out_dir), output_name="combined")

    fake_ref = {"version": 1, "refs": {".zmetadata": "{}"}}

    # Mock _build_parallel to avoid needing a real Dask cluster.
    def _fake_build_parallel(self, inputs, config, on_progress=None):
        if on_progress:
            for i in range(len(inputs)):
                on_progress(i + 1, len(inputs))
        return fake_ref

    monkeypatch.setattr(DaskConverter, "_build_parallel", _fake_build_parallel)
    monkeypatch.setattr("dataforge.core.dask_converter.preflight_validate", lambda inputs, config: None)

    converter = DaskConverter(dask_config=dask_cfg)
    result = converter.convert(files, cfg)

    assert result.reference == fake_ref
    assert "combined.json" in result.output_uri
    # Verify the file was written.
    assert (out_dir / "combined.json").exists()


def test_parallel_path_reports_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """on_progress callback is invoked during parallel conversion."""
    dask_cfg = DaskConfig(parallel_threshold=2)
    files = []
    for i in range(4):
        f = tmp_path / f"input_{i}.nc"
        f.write_bytes(b"dummy")
        files.append(str(f))

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    cfg = ConversionConfig(output_prefix=str(out_dir), output_name="prog")

    progress_calls: list[tuple[int, int]] = []

    def _fake_build_parallel(self, inputs, config, on_progress=None):
        if on_progress:
            for i in range(len(inputs)):
                on_progress(i + 1, len(inputs))
        return {"version": 1, "refs": {}}

    monkeypatch.setattr(DaskConverter, "_build_parallel", _fake_build_parallel)
    monkeypatch.setattr("dataforge.core.dask_converter.preflight_validate", lambda inputs, config: None)

    converter = DaskConverter(dask_config=dask_cfg)
    converter.convert(
        files, cfg, on_progress=lambda d, t: progress_calls.append((d, t))
    )

    assert len(progress_calls) == 4
    assert progress_calls[-1] == (4, 4)


def test_generate_single_reference_uses_shared_single_file_router(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataforge.core.dask_converter import _generate_single_reference

    calls: list[tuple[str, int]] = []

    def _fake_single_file_reference(path: str, inline_threshold: int) -> dict[str, object]:
        calls.append((path, inline_threshold))
        return {"path": path}

    monkeypatch.setattr(
        "dataforge.core.dask_converter._single_file_reference", _fake_single_file_reference
    )

    result = _generate_single_reference("/tmp/a.nc", 321)

    assert calls == [("/tmp/a.nc", 321)]
    assert result == {"path": "/tmp/a.nc"}


def test_parallel_path_preserves_input_order_when_tasks_finish_out_of_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dask_cfg = DaskConfig(parallel_threshold=2)
    files = []
    for i in range(3):
        f = tmp_path / f"input_{i}.nc"
        f.write_bytes(b"dummy")
        files.append(str(f))

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    cfg = ConversionConfig(
        output_prefix=str(out_dir),
        output_name="ordered",
        concat_dims=["time"],
    )

    class FakeFuture:
        def __init__(self, value: dict[str, object]) -> None:
            self._value = value

        def result(self) -> dict[str, object]:
            return self._value

    class FakeClient:
        def __init__(self) -> None:
            self.futures: list[FakeFuture] = []

        def submit(self, fn, path, inline_threshold, pure=False):
            future = FakeFuture({"path": path, "inline_threshold": inline_threshold})
            self.futures.append(future)
            return future

    fake_client = FakeClient()

    @contextmanager
    def _fake_cluster(config):
        yield fake_client

    combine_calls: dict[str, object] = {}

    class FakeMultiZarrToZarr:
        def __init__(self, refs, concat_dims, identical_dims) -> None:
            combine_calls["refs"] = refs
            combine_calls["concat_dims"] = concat_dims
            combine_calls["identical_dims"] = identical_dims

        def translate(self) -> dict[str, object]:
            return {"refs": combine_calls["refs"]}

    def _reverse_completion_order(futures):
        return list(reversed(list(futures)))

    monkeypatch.setattr("dataforge.core.dask_converter._dask_cluster", _fake_cluster)
    monkeypatch.setattr(
        "dataforge.core.dask_converter.as_completed", _reverse_completion_order
    )
    monkeypatch.setattr("dataforge.core.dask_converter.preflight_validate", lambda inputs, config: None)
    with patch("kerchunk.combine.MultiZarrToZarr", FakeMultiZarrToZarr):
        result = DaskConverter(dask_config=dask_cfg).convert(files, cfg)

    assert [ref["path"] for ref in combine_calls["refs"]] == files
    assert result.reference["refs"] == combine_calls["refs"]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_empty_inputs_raises_invalid_input_error() -> None:
    converter = DaskConverter()
    cfg = ConversionConfig(output_prefix="/tmp/out", output_name="x")
    with pytest.raises(InvalidInputError, match="non-empty"):
        converter.convert([], cfg)


def test_parallel_path_wraps_exceptions_as_conversion_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Exceptions during parallel build are wrapped in ConversionError."""
    dask_cfg = DaskConfig(parallel_threshold=2)
    files = []
    for i in range(3):
        f = tmp_path / f"input_{i}.nc"
        f.write_bytes(b"dummy")
        files.append(str(f))

    out_dir = tmp_path / "out"
    out_dir.mkdir()
    cfg = ConversionConfig(output_prefix=str(out_dir), output_name="fail")

    def _boom(self, inputs, config, on_progress=None):
        raise RuntimeError("cluster exploded")

    monkeypatch.setattr(DaskConverter, "_build_parallel", _boom)
    monkeypatch.setattr("dataforge.core.dask_converter.preflight_validate", lambda inputs, config: None)

    converter = DaskConverter(dask_config=dask_cfg)
    with pytest.raises(ConversionError, match="cluster exploded"):
        converter.convert(files, cfg)


# ---------------------------------------------------------------------------
# _generate_single_reference (the function sent to Dask workers)
# ---------------------------------------------------------------------------


def test_generate_single_reference_calls_kerchunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_generate_single_reference delegates to the shared single-file router."""
    fake_ref = {"version": 1, "refs": {".zattrs": "{}"}}

    mock_router = MagicMock(return_value=fake_ref)
    monkeypatch.setattr("dataforge.core.dask_converter._single_file_reference", mock_router)

    result = _generate_single_reference("/fake/path.nc", inline_threshold=200)

    assert result == fake_ref
    mock_router.assert_called_once_with("/fake/path.nc", inline_threshold=200)


# ---------------------------------------------------------------------------
# Settings integration
# ---------------------------------------------------------------------------


def test_settings_dask_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """dask_config() returns sensible defaults from environment."""
    monkeypatch.delenv("DATAFORGE_DASK_N_WORKERS", raising=False)
    monkeypatch.delenv("DATAFORGE_DASK_THREADS_PER_WORKER", raising=False)
    monkeypatch.delenv("DATAFORGE_DASK_MEMORY_LIMIT", raising=False)
    monkeypatch.delenv("DATAFORGE_DASK_LOCAL_DIRECTORY", raising=False)
    monkeypatch.delenv("DATAFORGE_DASK_PROCESSES", raising=False)
    monkeypatch.delenv("DATAFORGE_DASK_PARALLEL_THRESHOLD", raising=False)

    from dataforge.settings import dask_config

    cfg = dask_config()
    assert cfg.n_workers is None
    assert cfg.threads_per_worker == 1
    assert cfg.memory_limit == "2GiB"
    assert cfg.local_directory is None
    assert cfg.processes is True
    assert cfg.parallel_threshold == 4


def test_settings_dask_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """dask_config() reads from environment variables."""
    monkeypatch.setenv("DATAFORGE_DASK_N_WORKERS", "8")
    monkeypatch.setenv("DATAFORGE_DASK_THREADS_PER_WORKER", "2")
    monkeypatch.setenv("DATAFORGE_DASK_MEMORY_LIMIT", "4GiB")
    monkeypatch.setenv("DATAFORGE_DASK_LOCAL_DIRECTORY", " /tmp/dataforge-dask ")
    monkeypatch.setenv("DATAFORGE_DASK_PROCESSES", "false")
    monkeypatch.setenv("DATAFORGE_DASK_PARALLEL_THRESHOLD", "10")

    from dataforge.settings import dask_config

    cfg = dask_config()
    assert cfg.n_workers == 8
    assert cfg.threads_per_worker == 2
    assert cfg.memory_limit == "4GiB"
    assert cfg.local_directory == "/tmp/dataforge-dask"
    assert cfg.processes is False
    assert cfg.parallel_threshold == 10
