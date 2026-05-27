from __future__ import annotations

from pathlib import Path

from dataforge.settings import stac_href_mappings


def publishable_href(output_uri: str, *, use_local_output_as_href: bool = False) -> str:
    if output_uri.startswith("s3://"):
        return output_uri

    local_path = str(Path(output_uri).resolve())
    if use_local_output_as_href:
        return local_path

    mappings = stac_href_mappings()
    for local_prefix, public_prefix in sorted(
        mappings, key=lambda item: len(item[0]), reverse=True
    ):
        if local_path == local_prefix:
            return public_prefix
        prefix = f"{local_prefix}/"
        if local_path.startswith(prefix):
            suffix = local_path[len(prefix) :]
            return f"{public_prefix}/{suffix}"

    raise ValueError(
        f"no STAC href mapping configured for local output path: {local_path}"
    )
