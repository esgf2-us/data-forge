from __future__ import annotations

from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from dataforge.models.job import JobResultMetadata


def build_result_metadata(
    *,
    inputs: list[str],
    output_uri: str,
    dataset_id: str | None,
    user_metadata: dict[str, object] | None,
) -> JobResultMetadata:
    generated_at = datetime.now(timezone.utc)
    normalized_inputs = [str(Path(value).resolve()) for value in inputs]
    projects = _dataset_projects(dataset_id)

    return JobResultMetadata(
        dataset_id=dataset_id,
        project=projects,
        source_files=normalized_inputs,
        source_count=len(normalized_inputs),
        output_uri=output_uri,
        generated_at=generated_at,
        dataforge_version=version("data-forge"),
        user_metadata=dict(user_metadata or {}),
    )


def _dataset_projects(dataset_id: str | None) -> str | None:
    if not dataset_id:
        return None
    return dataset_id.split(".", 1)[0] or None
