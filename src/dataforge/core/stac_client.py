from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from dataforge.models.job import JobPublication
from dataforge.settings import (
    stac_api,
    stac_config_json,
    stac_datanode,
    stac_transaction_api,
)


def _load_esgcet() -> tuple[Any, Any, Any, Any]:
    from esgcet.search_check import ESGSearchCheck
    from esgcet.stac_client import getTransactionClient
    from esgcet.stac_converter import ESGSTACConverter, ESGSTACItem

    return ESGSearchCheck, getTransactionClient, ESGSTACConverter, ESGSTACItem


@dataclass(frozen=True)
class StacPublishResult:
    collection: str
    item_id: str
    asset_path: str
    patch_applied: bool


class ESGPublisherStacClient:
    def __init__(self, *, datanode: str | None = None) -> None:
        self._default_datanode = datanode or stac_datanode()

    def publish_kerchunk(
        self, dataset_id: str, href: str, datanode: str | None = None
    ) -> JobPublication:
        site = (datanode or self._default_datanode or "").strip()
        if not site:
            raise ValueError("STAC datanode must be configured for publish jobs")

        discovery_api = stac_api()
        if not discovery_api:
            raise ValueError("DATAFORGE_STAC_API must be configured for publish jobs")

        ESGSearchCheck, getTransactionClient, ESGSTACConverter, ESGSTACItem = (
            _load_esgcet()
        )

        config = self._publisher_config(discovery_api)

        search = ESGSearchCheck(stac_api=discovery_api, verbose=False, silent=True)
        item = search.stac_item_fetch(dataset_id)
        if not item:
            raise RuntimeError(f"dataset not found in STAC: {dataset_id}")

        stac_item = ESGSTACItem(item)
        converter = ESGSTACConverter({"stac_api": discovery_api})
        if not getattr(converter, "stac_api", None):
            raise RuntimeError("failed to initialize ESGSTACConverter")

        ops = stac_item.add_aggregate("kerchunk", href, site)
        if not ops:
            raise RuntimeError("no STAC patch operations were generated")

        transaction_factory = getTransactionClient(config["stac_config"])
        transaction_client = transaction_factory(config)

        collection = str(
            item.get("collection") or self._collection_from_dataset_id(dataset_id)
        )
        applied = bool(
            transaction_client.json_patch(collection, item_id=dataset_id, entry=ops)
        )
        if not applied:
            raise RuntimeError(f"failed to patch STAC item for dataset {dataset_id}")

        return JobPublication(
            dataset_id=dataset_id,
            collection=collection,
            item_id=dataset_id,
            aggregate_type="kerchunk",
            href=href,
            datanode=site,
            asset_path=str(ops[0].get("path", "/assets/reference_file")),
            patch_applied=True,
            published_at=datetime.now(timezone.utc),
            error_message=None,
        )

    def _publisher_config(self, discovery_api: str) -> dict[str, Any]:
        config = stac_config_json()
        stac_cfg = dict(config)

        transaction_base_url = stac_transaction_api()
        if transaction_base_url:
            transaction_cfg = dict(stac_cfg.get("stac_transaction_api") or {})
            transaction_cfg.setdefault("base_url", transaction_base_url)
            stac_cfg["stac_transaction_api"] = transaction_cfg

        stac_cfg.setdefault("stac_api", discovery_api)
        stac_cfg.setdefault("stac_client", {})

        return {
            "stac_api": discovery_api,
            "stac_config": stac_cfg,
            "silent": True,
            "verbose": False,
        }

    @staticmethod
    def _collection_from_dataset_id(dataset_id: str) -> str:
        project = dataset_id.split(".", 1)[0]
        if project.upper() == "MIP-DRS7":
            return "CMIP7"
        return project
