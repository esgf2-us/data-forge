import pytest


def test_transition_rules() -> None:
    from dataforge.job_store.base import is_allowed_transition
    from dataforge.models.job import JobStatus

    assert is_allowed_transition(JobStatus.QUEUED, JobStatus.RUNNING)
    assert is_allowed_transition(JobStatus.RUNNING, JobStatus.COMPLETED)
    assert is_allowed_transition(JobStatus.QUEUED, JobStatus.CANCELLED)
    assert not is_allowed_transition(JobStatus.COMPLETED, JobStatus.RUNNING)


def test_cancel_precedence() -> None:
    from dataforge.job_store.base import terminal_status_precedence
    from dataforge.models.job import JobStatus

    assert (
        terminal_status_precedence(JobStatus.CANCELLED, JobStatus.COMPLETED)
        == JobStatus.CANCELLED
    )
