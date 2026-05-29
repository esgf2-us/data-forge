from __future__ import annotations

from pathlib import Path

import pytest

from dataforge.models.config import (
    ConversionConfig,
    InvalidConfigError,
    InvalidInputError,
)


def test_preflight_validate_accepts_readable_hdf5_input(tmp_path: Path) -> None:
    import h5py

    from dataforge.core.validation import preflight_validate

    in_file = tmp_path / "a.nc"
    with h5py.File(in_file, "w") as f:
        f.create_dataset("x", data=[1, 2, 3])

    preflight_validate(
        [str(in_file)],
        ConversionConfig(output_prefix=str(tmp_path / "out"), output_name="ref"),
    )


def test_preflight_validate_rejects_unreadable_input(tmp_path: Path) -> None:
    from unittest.mock import patch

    from dataforge.core.validation import preflight_validate

    in_file = tmp_path / "a.nc"
    in_file.write_text("not-hdf5", encoding="utf-8")

    with patch("pathlib.Path.open", side_effect=OSError("boom")):
        with pytest.raises(InvalidInputError, match="input file is not readable"):
            preflight_validate(
                [str(in_file)],
                ConversionConfig(output_prefix=str(tmp_path / "out"), output_name="ref"),
            )


def test_preflight_validate_accepts_non_hdf5_regular_file(tmp_path: Path) -> None:
    from dataforge.core.validation import preflight_validate

    in_file = tmp_path / "a.nc"
    in_file.write_text("plain-bytes", encoding="utf-8")

    preflight_validate(
        [str(in_file)],
        ConversionConfig(output_prefix=str(tmp_path / "out"), output_name="ref"),
    )


def test_validate_dataset_id_rejects_whitespace() -> None:
    from dataforge.core.validation import validate_dataset_id

    with pytest.raises(InvalidInputError, match="whitespace"):
        validate_dataset_id("CMIP6.foo bar")


def test_preflight_validate_rejects_invalid_s3_output_prefix(tmp_path: Path) -> None:
    import h5py

    from dataforge.core.validation import preflight_validate

    in_file = tmp_path / "a.nc"
    with h5py.File(in_file, "w") as f:
        f.create_dataset("x", data=[1, 2, 3])

    with pytest.raises(InvalidConfigError, match="include an S3 bucket"):
        preflight_validate(
            [str(in_file)],
            ConversionConfig(output_prefix="s3://", output_name="ref"),
        )


def test_preflight_validate_allows_s3_input_without_local_checks(
    tmp_path: Path,
) -> None:
    from dataforge.core.validation import preflight_validate

    preflight_validate(
        ["s3://bucket/a.nc"],
        ConversionConfig(output_prefix=str(tmp_path / "out"), output_name="ref"),
    )


def test_preflight_validate_rewrites_local_input_through_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import h5py

    from dataforge.core.validation import preflight_validate

    host_dir = tmp_path / "host"
    in_file = host_dir / "nested" / "a.nc"
    in_file.parent.mkdir(parents=True)
    with h5py.File(in_file, "w") as f:
        f.create_dataset("x", data=[1, 2, 3])

    container_dir = tmp_path / "container"
    container_file = container_dir / "nested" / "a.nc"
    container_file.parent.mkdir(parents=True)
    with h5py.File(container_file, "w") as f:
        f.create_dataset("x", data=[1, 2, 3])

    monkeypatch.setenv(
        "DATAFORGE_LOCAL_INPUT_MAPPINGS",
        (
            '[{"host_prefix":"'
            + str(host_dir.resolve())
            + '","container_prefix":"'
            + str(container_dir.resolve())
            + '"}]'
        ),
    )

    preflight_validate(
        [str(in_file)],
        ConversionConfig(output_prefix=str(tmp_path / "out"), output_name="ref"),
    )
