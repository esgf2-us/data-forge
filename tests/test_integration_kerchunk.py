import pytest


def test_end_to_end_single_file_conversion(tmp_path) -> None:
    # Keep this test skippable: the scientific stack may not be available in all dev envs.
    h5py = pytest.importorskip("h5py")
    pytest.importorskip("kerchunk")

    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    in_file = tmp_path / "a.nc"
    with h5py.File(in_file, "w") as f:
        f.create_dataset("x", data=[1, 2, 3])

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")
    result = KerchunkConverter().convert([str(in_file)], cfg)

    assert isinstance(result.reference, dict)
    assert (tmp_path / "ref.json").exists()
