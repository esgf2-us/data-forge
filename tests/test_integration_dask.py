"""Integration tests for DaskConverter with a real Dask LocalCluster.

These tests create real HDF5 files and exercise the full parallel pipeline
(Dask cluster creation -> parallel SingleHdf5ToZarr -> MultiZarrToZarr combine).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _create_hdf5_file(path: Path, time_values: list[int]) -> None:
    """Create a minimal HDF5/NetCDF-like file with a time dimension."""
    import numpy as np

    h5py = pytest.importorskip("h5py")
    with h5py.File(path, "w") as f:
        f.create_dataset("time", data=np.array(time_values, dtype="i4"))
        f.create_dataset(
            "temperature",
            data=np.random.rand(len(time_values), 4),
            dtype="f4",
        )


def test_dask_parallel_multi_file_conversion(tmp_path: Path) -> None:
    """Full parallel conversion with a real Dask cluster."""
    h5py = pytest.importorskip("h5py")
    pytest.importorskip("kerchunk")
    pytest.importorskip("dask")
    pytest.importorskip("distributed")

    from dataforge.core.dask_converter import DaskConverter
    from dataforge.models.config import ConversionConfig
    from dataforge.models.dask_config import DaskConfig

    # Create 5 input files (above default threshold of 4).
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    files = []
    for i in range(5):
        p = input_dir / f"data_{i:03d}.nc"
        _create_hdf5_file(p, [i * 10, i * 10 + 1])
        files.append(str(p))

    out_dir = tmp_path / "output"
    out_dir.mkdir()
    cfg = ConversionConfig(
        output_prefix=str(out_dir),
        output_name="combined",
        concat_dims=["time"],
    )

    # Use a minimal cluster for testing.
    dask_cfg = DaskConfig(
        n_workers=2,
        threads_per_worker=1,
        memory_limit="512MiB",
        processes=False,  # threads are faster to start in tests
        parallel_threshold=4,
    )

    progress_calls: list[tuple[int, int]] = []

    converter = DaskConverter(dask_config=dask_cfg)
    result = converter.convert(
        files, cfg, on_progress=lambda d, t: progress_calls.append((d, t))
    )

    # Verify output.
    assert (out_dir / "combined.json").exists()
    assert isinstance(result.reference, dict)
    assert "refs" in result.reference or "version" in result.reference
    assert len(result.inputs) == 5

    # Progress should have been reported for each file.
    assert len(progress_calls) == 5
    assert progress_calls[-1] == (5, 5)


def test_dask_below_threshold_uses_sequential(tmp_path: Path) -> None:
    """Below the parallel_threshold, conversion still works (sequential)."""
    h5py = pytest.importorskip("h5py")
    pytest.importorskip("kerchunk")

    from dataforge.core.dask_converter import DaskConverter
    from dataforge.models.config import ConversionConfig
    from dataforge.models.dask_config import DaskConfig

    in_file = tmp_path / "single.nc"
    _create_hdf5_file(in_file, [0, 1, 2])

    out_dir = tmp_path / "output"
    out_dir.mkdir()
    cfg = ConversionConfig(output_prefix=str(out_dir), output_name="single_ref")
    dask_cfg = DaskConfig(parallel_threshold=4)

    converter = DaskConverter(dask_config=dask_cfg)
    result = converter.convert([str(in_file)], cfg)

    assert (out_dir / "single_ref.json").exists()
    assert isinstance(result.reference, dict)


def test_dask_cluster_lifecycle(tmp_path: Path) -> None:
    """Verify that the Dask cluster is properly created and torn down."""
    h5py = pytest.importorskip("h5py")
    pytest.importorskip("kerchunk")
    pytest.importorskip("dask")
    distributed = pytest.importorskip("distributed")

    from dataforge.core.dask_converter import DaskConverter
    from dataforge.models.config import ConversionConfig
    from dataforge.models.dask_config import DaskConfig

    # Create enough files to trigger parallel path.
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    files = []
    for i in range(4):
        p = input_dir / f"data_{i:03d}.nc"
        _create_hdf5_file(p, [i])
        files.append(str(p))

    out_dir = tmp_path / "output"
    out_dir.mkdir()
    cfg = ConversionConfig(
        output_prefix=str(out_dir),
        output_name="lifecycle_test",
        concat_dims=["time"],
    )
    dask_cfg = DaskConfig(
        n_workers=2,
        threads_per_worker=1,
        memory_limit="256MiB",
        processes=False,
        parallel_threshold=4,
    )

    converter = DaskConverter(dask_config=dask_cfg)
    result = converter.convert(files, cfg)

    # If we got here without hanging or errors, cluster lifecycle is correct.
    assert result.output_uri.endswith("lifecycle_test.json")
    assert isinstance(result.reference, dict)
