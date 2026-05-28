from __future__ import annotations

from pydantic import ConfigDict

from dataforge.models.job import (
    Job as JobModel,
    JobCreateRequest as JobCreateRequestModel,
    JobListResponse as JobListResponseModel,
    JobResultResponse as JobResultResponseModel,
    JobStacResponse as JobStacResponseModel,
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
                    "publish_to_stac": True,
                    "dataset_id": "CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas.gn.v20190308",
                    "use_local_output_as_href": False,
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
                    "publish_to_stac": True,
                    "dataset_id": "CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas.gn.v20190308",
                    "aggregate_type": "kerchunk",
                    "datanode": None,
                    "use_local_output_as_href": False,
                },
                "created_at": "2026-05-12T00:00:00Z",
                "updated_at": "2026-05-12T00:00:00Z",
                "started_at": None,
                "completed_at": None,
                "progress_total": None,
                "progress_done": None,
                "error_message": None,
                "result_url": None,
                "publication": None,
                "result_metadata": None,
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


class JobStacResponse(JobStacResponseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "job-12345678-abcd-ef01-2345-6789abcdef01",
                "publish_to_stac": True,
                "publication": {
                    "dataset_id": "CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas.gn.v20190308",
                    "collection": "CMIP6",
                    "item_id": "CMIP6.CMIP.NCAR.CESM2.historical.Amon.tas.gn.v20190308",
                    "aggregate_type": "kerchunk",
                    "href": "/data/cmip6/tas_day_kerchunk.json",
                    "datanode": "esgf-node.llnl.gov",
                    "asset_path": "/assets/reference_file",
                    "patch_applied": True,
                    "published_at": "2026-05-12T00:05:00Z",
                    "error_message": None,
                },
            }
        }
    )
