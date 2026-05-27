from __future__ import annotations

import pytest


def test_publish_kerchunk_fetches_item_builds_patch_and_publishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataforge.core.stac_client import ESGPublisherStacClient

    dataset_id = "CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas.gn.v20190308"
    href = "/tmp/out/job.json"
    item = {"collection": "CMIP6", "assets": {}}

    class FakeSearchCheck:
        def __init__(self, stac_api, verbose, silent) -> None:
            assert stac_api == "https://stac.example.org"

        def stac_item_fetch(self, got_dataset_id):
            assert got_dataset_id == dataset_id
            return item

    class FakeTransactionClient:
        def json_patch(self, collection, item_id, entry):
            assert collection == "CMIP6"
            assert item_id == dataset_id
            assert entry == [
                {
                    "op": "add",
                    "path": "/assets/reference_file",
                    "value": {"href": href},
                }
            ]
            return True

    class FakeESGSTACItem:
        def __init__(self, got_item) -> None:
            assert got_item is item

        def add_aggregate(self, aggregate_type, got_href, site):
            assert aggregate_type == "kerchunk"
            assert got_href == href
            assert site == "esgf-node.llnl.gov"
            return [
                {"op": "add", "path": "/assets/reference_file", "value": {"href": href}}
            ]

    class FakeESGSTACConverter:
        def __init__(self, stac_config) -> None:
            self.stac_api = stac_config["stac_api"]

    def _fake_get_transaction_client(stac_config):
        assert stac_config["stac_api"] == "https://stac.example.org"

        def _factory(config):
            assert config["stac_api"] == "https://stac.example.org"
            return FakeTransactionClient()

        return _factory

    monkeypatch.setenv("DATAFORGE_STAC_API", "https://stac.example.org")
    monkeypatch.setenv("DATAFORGE_STAC_TRANSACTION_API", "https://txn.example.org")
    monkeypatch.setenv("DATAFORGE_STAC_DATANODE", "esgf-node.llnl.gov")
    monkeypatch.setattr(
        "dataforge.core.stac_client._load_esgcet",
        lambda: (
            FakeSearchCheck,
            _fake_get_transaction_client,
            FakeESGSTACConverter,
            FakeESGSTACItem,
        ),
    )

    publication = ESGPublisherStacClient().publish_kerchunk(dataset_id, href)

    assert publication.dataset_id == dataset_id
    assert publication.collection == "CMIP6"
    assert publication.item_id == dataset_id
    assert publication.href == href
    assert publication.datanode == "esgf-node.llnl.gov"
    assert publication.asset_path == "/assets/reference_file"
    assert publication.patch_applied is True
    assert publication.published_at is not None


def test_publish_kerchunk_raises_when_dataset_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataforge.core.stac_client import ESGPublisherStacClient

    class FakeSearchCheck:
        def __init__(self, stac_api, verbose, silent) -> None:
            pass

        def stac_item_fetch(self, got_dataset_id):
            return None

    monkeypatch.setenv("DATAFORGE_STAC_API", "https://stac.example.org")
    monkeypatch.setenv("DATAFORGE_STAC_DATANODE", "esgf-node.llnl.gov")
    monkeypatch.setattr(
        "dataforge.core.stac_client._load_esgcet",
        lambda: (FakeSearchCheck, object, object, object),
    )

    with pytest.raises(RuntimeError, match="dataset not found"):
        ESGPublisherStacClient().publish_kerchunk("CMIP6.foo.bar", "/tmp/out/job.json")


def test_publish_kerchunk_requires_configured_datanode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataforge.core.stac_client import ESGPublisherStacClient

    monkeypatch.delenv("DATAFORGE_STAC_DATANODE", raising=False)
    monkeypatch.setenv("DATAFORGE_STAC_API", "https://stac.example.org")

    with pytest.raises(ValueError, match="STAC datanode"):
        ESGPublisherStacClient().publish_kerchunk("CMIP6.foo.bar", "/tmp/out/job.json")


def test_publishable_href_maps_longest_matching_prefix(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from dataforge.core.esgf_publisher import publishable_href

    root = tmp_path / "href-map"
    output = root / "kerchunks" / "cmip6" / "job.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("{}", encoding="utf-8")

    monkeypatch.setenv(
        "DATAFORGE_STAC_HREF_MAPPINGS",
        (
            "["
            + '{"local_prefix":"'
            + str(root.resolve())
            + '","public_prefix":"https://example.org/root"},'
            + '{"local_prefix":"'
            + str((root / "kerchunks").resolve())
            + '","public_prefix":"https://example.org/refs"}'
            + "]"
        ),
    )

    assert publishable_href(str(output)) == "https://example.org/refs/cmip6/job.json"


def test_publishable_href_can_bypass_mapping(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from dataforge.core.esgf_publisher import publishable_href

    output = tmp_path / "job.json"
    output.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("DATAFORGE_STAC_HREF_MAPPINGS", raising=False)

    assert publishable_href(str(output), use_local_output_as_href=True) == str(
        output.resolve()
    )


def test_publishable_href_requires_mapping_when_bypass_is_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from dataforge.core.esgf_publisher import publishable_href

    output = tmp_path / "job.json"
    output.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("DATAFORGE_STAC_HREF_MAPPINGS", raising=False)

    with pytest.raises(ValueError, match="no STAC href mapping"):
        publishable_href(str(output))
