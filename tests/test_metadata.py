from __future__ import annotations

from pathlib import Path


def test_build_result_metadata_captures_provenance(tmp_path: Path) -> None:
    from dataforge.core.metadata import build_result_metadata

    in_file = tmp_path / "a.nc"
    in_file.write_text("x", encoding="utf-8")

    metadata = build_result_metadata(
        inputs=[str(in_file)],
        output_uri=str(tmp_path / "out" / "ref.json"),
        dataset_id="CMIP6.CMIP.foo.bar",
        user_metadata={"project": "CMIP6"},
    )

    assert metadata.dataset_id == "CMIP6.CMIP.foo.bar"
    assert metadata.project == "CMIP6"
    assert metadata.source_count == 1
    assert metadata.source_files == [str(in_file.resolve())]
    assert metadata.user_metadata == {"project": "CMIP6"}
