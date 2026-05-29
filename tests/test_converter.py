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


def test_converter_accepts_s3_inputs_without_local_rewrite(
    tmp_path, monkeypatch
) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    def _fake_build_reference(self, inputs, config):
        return {"inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)

    result = KerchunkConverter().convert(["s3://bucket/a.nc"], cfg)

    assert result.inputs == ["s3://bucket/a.nc"]


def test_converter_rejects_missing_local_input_file(tmp_path) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig, InvalidInputError

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    with pytest.raises(InvalidInputError, match="input file does not exist"):
        KerchunkConverter().convert([str(tmp_path / "missing.nc")], cfg)


def test_converter_rejects_missing_file_uri_input(tmp_path) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig, InvalidInputError

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    with pytest.raises(InvalidInputError, match="input file does not exist"):
        KerchunkConverter().convert([f"file://{tmp_path / 'missing.nc'}"], cfg)


def test_converter_writes_reference_to_storage(tmp_path, monkeypatch) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    in_file = tmp_path / "a.nc"
    in_file.touch()

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    def _fake_build_reference(self, inputs, config):
        return {"version": 1, "inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)
    monkeypatch.setattr("dataforge.core.converter.preflight_validate", lambda inputs, config: None)

    result = KerchunkConverter().convert([str(in_file)], cfg)

    assert result.output_uri.endswith("/ref.json")
    assert result.reference["version"] == 1
    assert (tmp_path / "ref.json").exists()


def test_converter_rejects_overwriting_existing_output_by_default(
    tmp_path, monkeypatch
) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig, WriteError

    in_file = tmp_path / "a.nc"
    in_file.touch()
    out_file = tmp_path / "ref.json"
    out_file.write_text("{}", encoding="utf-8")

    cfg = ConversionConfig(output_prefix=str(tmp_path), output_name="ref")

    def _fake_build_reference(self, inputs, config):
        return {"version": 1, "inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)
    monkeypatch.setattr("dataforge.core.converter.preflight_validate", lambda inputs, config: None)

    with pytest.raises(WriteError, match="output already exists"):
        KerchunkConverter().convert([str(in_file)], cfg)


def test_converter_can_overwrite_existing_output_when_enabled(
    tmp_path, monkeypatch
) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    in_file = tmp_path / "a.nc"
    in_file.touch()
    out_file = tmp_path / "ref.json"
    out_file.write_text("{}", encoding="utf-8")

    cfg = ConversionConfig(
        output_prefix=str(tmp_path), output_name="ref", overwrite_existing=True
    )

    def _fake_build_reference(self, inputs, config):
        return {"version": 2, "inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)
    monkeypatch.setattr("dataforge.core.converter.preflight_validate", lambda inputs, config: None)

    result = KerchunkConverter().convert([str(in_file)], cfg)

    assert result.reference["version"] == 2
    assert result.output_uri.endswith("/ref.json")


def test_converter_normalizes_local_input_paths(tmp_path, monkeypatch) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    in_file = tmp_path / "nested" / "a.nc"
    in_file.parent.mkdir(parents=True)
    in_file.touch()

    monkeypatch.chdir(tmp_path)

    cfg = ConversionConfig(output_prefix="./out", output_name="ref")

    def _fake_build_reference(self, inputs, config):
        return {"inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)
    monkeypatch.setattr("dataforge.core.converter.preflight_validate", lambda inputs, config: None)

    result = KerchunkConverter().convert([f"file://{in_file}"], cfg)

    assert result.inputs == [str(in_file.resolve())]
    assert result.output_uri.endswith("/out/ref.json")


def test_converter_rewrites_local_inputs_through_mapping(tmp_path, monkeypatch) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    host_dir = tmp_path / "host"
    in_file = host_dir / "nested" / "a.nc"
    in_file.parent.mkdir(parents=True)
    in_file.touch()
    container_dir = tmp_path / "container"
    container_file = container_dir / "nested" / "a.nc"
    container_file.parent.mkdir(parents=True)
    container_file.touch()

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

    cfg = ConversionConfig(output_prefix=str(tmp_path / "out"), output_name="ref")

    def _fake_build_reference(self, inputs, config):
        return {"inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)
    monkeypatch.setattr("dataforge.core.converter.preflight_validate", lambda inputs, config: None)

    result = KerchunkConverter().convert([str(in_file)], cfg)

    assert result.inputs == [str(container_file.resolve())]


def test_converter_accepts_relative_local_inputs(tmp_path, monkeypatch) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.models.config import ConversionConfig

    in_file = tmp_path / "a.nc"
    in_file.touch()

    monkeypatch.chdir(tmp_path)

    cfg = ConversionConfig(output_prefix="out", output_name="ref")

    def _fake_build_reference(self, inputs, config):
        return {"inputs": inputs}

    monkeypatch.setattr(KerchunkConverter, "_build_reference", _fake_build_reference)
    monkeypatch.setattr("dataforge.core.converter.preflight_validate", lambda inputs, config: None)

    result = KerchunkConverter().convert(["a.nc"], cfg)

    assert result.inputs == [str(in_file.resolve())]
    assert result.output_uri.endswith("/out/ref.json")


def test_single_file_reference_uses_netcdf3_converter_for_cdf_magic(
    tmp_path, monkeypatch
) -> None:
    from dataforge.core.converter import _single_file_reference

    in_file = tmp_path / "a.nc"
    in_file.write_bytes(b"CDF\x01\x00\x00\x00\x00payload")

    class FakeNetCDF3:
        def __init__(self, path, inline_threshold):
            assert path == str(in_file)
            assert inline_threshold == 123

        def translate(self):
            return {"kind": "netcdf3"}

    def _fake_import(name):
        if name == "kerchunk.netCDF3":
            return type("M", (), {"NetCDF3ToZarr": FakeNetCDF3})
        raise AssertionError(name)

    monkeypatch.setattr("dataforge.core.converter.import_module", _fake_import)

    assert _single_file_reference(str(in_file), 123) == {"kind": "netcdf3"}


def test_single_file_reference_reports_missing_scipy_for_netcdf3(
    tmp_path, monkeypatch
) -> None:
    from dataforge.core.converter import _single_file_reference
    from dataforge.models.config import ConversionError

    in_file = tmp_path / "a.nc"
    in_file.write_bytes(b"CDF\x01\x00\x00\x00\x00payload")

    def _fake_import(name):
        raise ImportError(
            "Scipy is required for kerchunking NetCDF3 files. Please install with pip/conda install scipy."
        )

    monkeypatch.setattr("dataforge.core.converter.import_module", _fake_import)

    with pytest.raises(ConversionError, match="classic NetCDF3"):
        _single_file_reference(str(in_file), 10)


def test_single_file_reference_reports_unknown_format(tmp_path) -> None:
    from dataforge.core.converter import _single_file_reference
    from dataforge.models.config import ConversionError

    in_file = tmp_path / "a.bin"
    in_file.write_bytes(b"not-a-netcdf")

    with pytest.raises(ConversionError, match="not recognized"):
        _single_file_reference(str(in_file), 10)
