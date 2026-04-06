from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


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
        return v


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
    next_cursor: str | None


class JobResultResponse(BaseModel):
    result_url: str
