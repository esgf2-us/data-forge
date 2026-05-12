from __future__ import annotations

from pydantic import ConfigDict

from dataforge.models.job import (
    Job as JobModel,
    JobCreateRequest as JobCreateRequestModel,
    JobListResponse as JobListResponseModel,
    JobResultResponse as JobResultResponseModel,
)


class JobCreateRequest(JobCreateRequestModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "input_files": ["/data/cmip6/tas_day_0001.nc"],
                    "output_name": "tas_day_kerchunk",
                    "concat_dims": ["time"],
                    "inline_threshold": 300,
                    "metadata": {"project": "CMIP6"},
                }
            ]
        },
    )


class Job(JobModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "job-12345678-abcd-ef01-2345-6789abcdef01",
                "status": "queued",
                "submission": {
                    "input_files": ["/data/cmip6/tas_day_0001.nc"],
                    "output_mode": "local",
                    "output_path": "/data/cmip6",
                    "output_name": "tas_day_kerchunk",
                    "overwrite_existing": False,
                    "concat_dims": ["time"],
                    "identical_dims": None,
                    "inline_threshold": 300,
                    "metadata": {"project": "CMIP6"},
                },
                "created_at": "2026-05-12T00:00:00Z",
                "updated_at": "2026-05-12T00:00:00Z",
                "started_at": None,
                "completed_at": None,
                "progress_total": None,
                "progress_done": None,
                "error_message": None,
                "result_url": None,
            }
        }
    )


class JobListResponse(JobListResponseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobs": [],
                "next_cursor": None,
            }
        }
    )


class JobResultResponse(JobResultResponseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {"result_url": "file:///data/cmip6/tas_day_kerchunk.json"}
        }
    )
