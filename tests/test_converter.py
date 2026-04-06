import pytest


def test_conversion_config_requires_output_prefix_and_name() -> None:
    from dataforge.models.config import ConversionConfig

    with pytest.raises(Exception):
        ConversionConfig()  # type: ignore[call-arg]

    cfg = ConversionConfig(output_prefix="/tmp/out", output_name="ref")
    assert cfg.inline_threshold == 300
    assert cfg.concat_dims == ["time"]


def test_converter_rejects_empty_inputs(tmp_path) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig, InvalidInputError

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    with pytest.raises(InvalidInputError):
        KerchunkConverter().convert([], cfg)


def test_converter_rejects_non_local_input_schemes(tmp_path) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig, InvalidInputError

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    with pytest.raises(InvalidInputError):
        KerchunkConverter().convert(["s3://bucket/a.nc"], cfg)


def test_converter_writes_reference_to_storage(tmp_path, monkeypatch) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    in_file = tmp_path / "a.nc"
    in_file.touch()

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    def _fake_build_reference(self, inputs, config):
        return {"version": 1, "inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)

    result = KerchunkConverter().convert([str(in_file)], cfg)

    assert result.output_uri.endswith("/ref.json")
    assert result.reference["version"] == 1
    assert (tmp_path / "ref.json").exists()
