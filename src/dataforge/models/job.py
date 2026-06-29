from __future__ import annotations

import os
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal
from urllib.parse import unquote, urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dataforge.core.input_paths import (
    input_is_local,
    input_name_stem,
    normalize_input_for_runtime,
    validate_input_reference,
)
from dataforge.settings import local_output_path, s3_output_path
from dataforge.core.validation import validate_dataset_id


def _validate_output_name(value: str | None) -> str | None:
    if value is None:
        return None
    if not value:
        raise ValueError("output_name must be non-empty")
    if "/" in value or "\\" in value:
        raise ValueError("output_name must not contain path separators")
    if value.endswith(".json"):
        raise ValueError("output_name must not include .json suffix")
    return value


def default_input_output_directory(input_files: list[str]) -> str:
    if not input_files:
        raise ValueError("input_files must be non-empty")

    parents = [Path(normalize_input_for_runtime(value)).parent for value in input_files]
    if len(parents) == 1:
        return str(parents[0])
    return os.path.commonpath([str(parent) for parent in parents])


def default_local_output_directory(input_files: list[str]) -> str:
    return default_input_output_directory(input_files)


def default_output_name(input_files: list[str]) -> str:
    if not input_files:
        raise ValueError("input_files must be non-empty")

    stems = [input_name_stem(value) for value in input_files]
    if len(stems) == 1:
        return stems[0]

    prefix = os.path.commonprefix(stems).rstrip("._-0123456789")
    return prefix or stems[0]


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_files: list[str]
    output_name: str | None = None
    overwrite_existing: bool = False

    concat_dims: list[str] = Field(default_factory=lambda: ["time"])
    identical_dims: list[str] | None = None
    inline_threshold: int = 300
    metadata: dict[str, Any] | None = None
    publish_to_stac: bool = False
    dataset_id: str | None = None
    aggregate_type: Literal["kerchunk"] = "kerchunk"
    datanode: str | None = None
    use_local_output_as_href: bool = False

    @field_validator("output_name")
    @classmethod
    def _validate_output_name(cls, v: str | None) -> str | None:
        return _validate_output_name(v)

    @field_validator("input_files")
    @classmethod
    def _validate_inputs(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("input_files must be non-empty")
        for item in v:
            validate_input_reference(item)
        return v

    @field_validator("inline_threshold")
    @classmethod
    def _validate_inline_threshold(cls, v: int) -> int:
        if v < 0:
            raise ValueError("inline_threshold must be >= 0")
        return v

    @model_validator(mode="after")
    def _validate_publish_inputs(self) -> "JobCreateRequest":
        if self.publish_to_stac and not self.dataset_id:
            raise ValueError("dataset_id is required when publish_to_stac is true")
        if self.dataset_id is not None:
            self.dataset_id = validate_dataset_id(self.dataset_id)
        return self

    def to_submission(
        self, output_mode: Literal["local", "input", "s3"]
    ) -> "JobSubmission":
        return JobSubmission(output_mode=output_mode, **self.model_dump())


class JobSubmission(BaseModel):
    input_files: list[str]
    output_mode: Literal["local", "input", "s3"]
    output_path: str | None = None
    output_name: str | None = None
    overwrite_existing: bool = False

    concat_dims: list[str] = Field(default_factory=lambda: ["time"])
    identical_dims: list[str] | None = None
    inline_threshold: int = 300
    metadata: dict[str, Any] | None = None
    publish_to_stac: bool = False
    dataset_id: str | None = None
    aggregate_type: Literal["kerchunk"] = "kerchunk"
    datanode: str | None = None
    use_local_output_as_href: bool = False

    @field_validator("output_name")
    @classmethod
    def _validate_output_name(cls, v: str | None) -> str | None:
        return _validate_output_name(v)

    @field_validator("input_files")
    @classmethod
    def _validate_inputs(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("input_files must be non-empty")
        for item in v:
            validate_input_reference(item)
        return v

    @field_validator("inline_threshold")
    @classmethod
    def _validate_inline_threshold(cls, v: int) -> int:
        if v < 0:
            raise ValueError("inline_threshold must be >= 0")
        return v

    @model_validator(mode="after")
    def _validate_output_mode_path(self) -> "JobSubmission":
        if self.output_path is not None:
            output_path = self.output_path.strip()
            if not output_path:
                raise ValueError("output_path must be non-empty")
        else:
            output_path = None

        if self.output_mode == "local" and output_path is None:
            output_path = local_output_path()
        if self.output_mode == "input" and output_path is None:
            if all(input_is_local(value) for value in self.input_files):
                output_path = default_input_output_directory(self.input_files)
            else:
                raise ValueError(
                    "output_path must be provided for input mode when inputs are not local paths"
                )
        if self.output_mode == "s3" and output_path is None:
            output_path = s3_output_path()

        if output_path is None:
            raise ValueError("output_path must be non-empty")

        self.output_path = output_path

        if self.output_mode in {"local", "input"} and self.output_path.startswith(
            "s3://"
        ):
            raise ValueError(
                "output_path must be a local path when output_mode is local or input"
            )
        if self.output_mode == "s3" and not self.output_path.startswith("s3://"):
            raise ValueError("output_path must be an s3:// URL when output_mode is s3")
        if self.output_mode == "s3":
            p = urlparse(self.output_path)
            if not p.netloc:
                raise ValueError("output_path must include an S3 bucket")

        if self.publish_to_stac and not self.dataset_id:
            raise ValueError("dataset_id is required when publish_to_stac is true")
        if self.dataset_id is not None:
            self.dataset_id = validate_dataset_id(self.dataset_id)

        return self


class JobPublication(BaseModel):
    dataset_id: str
    collection: str
    item_id: str
    aggregate_type: Literal["kerchunk"]
    href: str
    datanode: str
    asset_path: str
    patch_applied: bool = False
    published_at: datetime | None = None
    error_message: str | None = None


class JobResultMetadata(BaseModel):
    dataset_id: str | None = None
    project: str | None = None
    source_files: list[str]
    source_count: int
    output_uri: str
    generated_at: datetime
    dataforge_version: str
    user_metadata: dict[str, Any] = Field(default_factory=dict)


class Job(BaseModel):
    id: str
    status: JobStatus
    submission: JobSubmission

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    progress_total: int | None = None
    progress_done: int | None = None

    error_message: str | None = None
    result_url: str | None = None
    publication: JobPublication | None = None
    result_metadata: JobResultMetadata | None = None


class JobListResponse(BaseModel):
    jobs: list[Job]
    next_cursor: str | None = None


class JobResultResponse(BaseModel):
    result_url: str


class JobStacResponse(BaseModel):
    job_id: str
    publish_to_stac: bool
    publication: JobPublication | None = None
