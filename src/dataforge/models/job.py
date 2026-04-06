from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator, model_validator


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobSubmission(BaseModel):
    input_files: list[str]
    output_mode: Literal["local", "s3"]
    output_path: str
    output_name: str | None = None

    concat_dims: list[str] = Field(default_factory=lambda: ["time"])
    identical_dims: list[str] | None = None
    inline_threshold: int = 300
    metadata: dict[str, Any] | None = None

    @field_validator("input_files")
    @classmethod
    def _validate_inputs_are_local(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("input_files must be non-empty")
        for item in v:
            p = urlparse(item)
            if p.scheme and p.scheme != "file":
                raise ValueError("Stage 2 supports local inputs only")
            if p.scheme == "file" and p.netloc not in ("", "localhost"):
                raise ValueError("Stage 2 supports local inputs only")
            if p.scheme == "file" and not p.path:
                raise ValueError("Stage 2 supports local inputs only")
        return v

    @field_validator("inline_threshold")
    @classmethod
    def _validate_inline_threshold(cls, v: int) -> int:
        if v < 0:
            raise ValueError("inline_threshold must be >= 0")
        return v

    @model_validator(mode="after")
    def _validate_output_mode_path(self) -> "JobSubmission":
        if self.output_mode == "s3" and not self.output_path.startswith("s3://"):
            raise ValueError("output_path must be an s3:// URL when output_mode is s3")
        if self.output_mode == "local" and self.output_path.startswith("s3://"):
            raise ValueError(
                "output_path must be a local path when output_mode is local"
            )
        return self


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


class JobListResponse(BaseModel):
    jobs: list[Job]
    next_cursor: str | None = None


class JobResultResponse(BaseModel):
    result_url: str
