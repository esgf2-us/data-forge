from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from dataforge.job_store.base import is_allowed_transition
from dataforge.models.job import Job, JobStatus, JobSubmission


@dataclass
class FakeJobStore:
    """In-memory JobStore implementation for unit tests."""

    def __post_init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._created_order: list[str] = []

    def create(self, submission: JobSubmission) -> Job:
        now = datetime.now(timezone.utc)
        job_id = f"job-{uuid4()}"

        if submission.output_name is None:
            submission = submission.model_copy(update={"output_name": job_id})

        job = Job(
            id=job_id,
            status=JobStatus.QUEUED,
            submission=submission,
            created_at=now,
            updated_at=now,
            started_at=None,
            completed_at=None,
            progress_total=None,
            progress_done=None,
            error_message=None,
            result_url=None,
        )
        self._jobs[job_id] = job
        self._created_order.append(job_id)
        return job

    def get(self, job_id: str) -> Job:
        return self._jobs[job_id]

    def list(
        self, status: JobStatus | None, limit: int, cursor: str | None
    ) -> tuple[list[Job], str | None]:
        # Newest-first; cursor ignored for this in-memory test store.
        ids = reversed(self._created_order)
        out: list[Job] = []
        for job_id in ids:
            job = self._jobs[job_id]
            if status is not None and job.status != status:
                continue
            out.append(job)
            if len(out) >= limit:
                break
        return out, None

    def set_status(self, job_id: str, expected: JobStatus, new: JobStatus) -> Job:
        job = self._jobs[job_id]
        if job.status != expected:
            raise ValueError(
                f"job {job_id} status mismatch: expected {expected}, got {job.status}"
            )
        if not is_allowed_transition(job.status, new):
            raise ValueError(
                f"job {job_id} transition not allowed: {job.status} -> {new}"
            )

        now = datetime.now(timezone.utc)
        started_at = job.started_at
        completed_at = job.completed_at
        if new == JobStatus.RUNNING and started_at is None:
            started_at = now
        if new in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            completed_at = now

        job = job.model_copy(
            update={
                "status": new,
                "updated_at": now,
                "started_at": started_at,
                "completed_at": completed_at,
            }
        )
        self._jobs[job_id] = job
        return job

    def set_progress(self, job_id: str, done: int, total: int) -> Job:
        job = self._jobs[job_id]
        now = datetime.now(timezone.utc)
        job = job.model_copy(
            update={
                "progress_done": done,
                "progress_total": total,
                "updated_at": now,
            }
        )
        self._jobs[job_id] = job
        return job

    def set_result(self, job_id: str, result_url: str) -> Job:
        job = self._jobs[job_id]
        now = datetime.now(timezone.utc)
        job = job.model_copy(update={"result_url": result_url, "updated_at": now})
        self._jobs[job_id] = job
        return job

    def set_error(self, job_id: str, error_message: str) -> Job:
        job = self._jobs[job_id]
        now = datetime.now(timezone.utc)
        job = job.model_copy(update={"error_message": error_message, "updated_at": now})
        self._jobs[job_id] = job
        return job

    def cancel(self, job_id: str) -> Job:
        job = self._jobs[job_id]
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            return job
        # Idempotent cancellation for non-terminal jobs.
        return self.set_status(job_id, expected=job.status, new=JobStatus.CANCELLED)
