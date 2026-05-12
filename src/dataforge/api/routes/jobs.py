from __future__ import annotations

import base64
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from dataforge.api.deps import get_job_store
from dataforge.job_store.base import JobStore
from dataforge.models.api import (
    Job,
    JobCreateRequest,
    JobListResponse,
    JobResultResponse,
)
from dataforge.models.job import JobStatus
from dataforge.settings import output_mode
from dataforge.workers.converter_worker import convert_job

router = APIRouter(prefix="/api/v1")


@router.post("/jobs", response_model=Job, status_code=201)
def create_job(
    request: JobCreateRequest,
    store: Annotated[JobStore, Depends(get_job_store)],
) -> Job:
    submission = request.to_submission(output_mode())
    job = store.create(submission)
    convert_job.send(job.id)
    return job


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(
    job_id: str,
    store: Annotated[JobStore, Depends(get_job_store)],
) -> Job:
    try:
        return store.get(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    store: Annotated[JobStore, Depends(get_job_store)],
    status: JobStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = None,
) -> JobListResponse:
    if cursor is not None:
        try:
            raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
            data = json.loads(raw.decode("utf-8"))
            int(data["t"])
            str(data["id"])
        except Exception as e:
            raise HTTPException(status_code=400, detail="invalid cursor") from e

    jobs, next_cursor = store.list(status=status, limit=limit, cursor=cursor)
    return JobListResponse(jobs=jobs, next_cursor=next_cursor)


@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
def get_job_result(
    job_id: str,
    store: Annotated[JobStore, Depends(get_job_store)],
) -> JobResultResponse | JSONResponse:
    try:
        job = store.get(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e

    if job.status != JobStatus.COMPLETED:
        return JSONResponse(status_code=409, content={"status": job.status.value})

    if not job.result_url:
        raise HTTPException(status_code=500, detail="job result missing")
    return JobResultResponse(result_url=job.result_url)


@router.delete("/jobs/{job_id}", response_model=Job)
def cancel_job(
    job_id: str,
    store: Annotated[JobStore, Depends(get_job_store)],
) -> Job:
    try:
        return store.cancel(job_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail="job not found") from e
