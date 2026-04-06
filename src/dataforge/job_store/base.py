from __future__ import annotations

from typing import Protocol

from dataforge.models.job import Job, JobStatus, JobSubmission


def is_allowed_transition(old: JobStatus, new: JobStatus) -> bool:
    if old == JobStatus.QUEUED and new in (JobStatus.RUNNING, JobStatus.CANCELLED):
        return True
    if old == JobStatus.RUNNING and new in (
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    ):
        return True
    return False


def terminal_status_precedence(a: JobStatus, b: JobStatus) -> JobStatus:
    # Used for checkpoint decisions: if either side observed CANCELLED, it wins.
    rank = {
        JobStatus.FAILED: 1,
        JobStatus.COMPLETED: 2,
        JobStatus.CANCELLED: 3,
    }
    if a == b:
        return a
    if a in rank and b in rank:
        return a if rank[a] >= rank[b] else b
    return a


class JobStore(Protocol):
    def create(self, submission: JobSubmission) -> Job: ...

    def get(self, job_id: str) -> Job: ...

    def list(
        self, status: JobStatus | None, limit: int, cursor: str | None
    ) -> tuple[list[Job], str | None]: ...

    def set_status(self, job_id: str, expected: JobStatus, new: JobStatus) -> Job: ...

    def set_progress(self, job_id: str, done: int, total: int) -> Job: ...

    def set_result(self, job_id: str, result_url: str) -> Job: ...

    def set_error(self, job_id: str, error_message: str) -> Job: ...

    def cancel(self, job_id: str) -> Job: ...
