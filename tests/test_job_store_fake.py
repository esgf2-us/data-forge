from __future__ import annotations

from dataforge.models.job import JobStatus, JobSubmission


def test_create_and_get_roundtrip() -> None:
    from dataforge.job_store.fake import FakeJobStore

    store = FakeJobStore()
    submission = JobSubmission(
        input_files=["/tmp/input.nc"],
        output_mode="local",
        output_path="/tmp/out",
        output_name=None,
    )

    job = store.create(submission)

    assert job.id.startswith("job-")
    assert job.status == JobStatus.QUEUED
    assert job.submission.output_name is None
    assert job.started_at is None
    assert job.completed_at is None
    assert job.updated_at >= job.created_at

    got = store.get(job.id)
    assert got == job


def test_cancel_is_idempotent_and_sets_terminal_status() -> None:
    from dataforge.job_store.fake import FakeJobStore

    store = FakeJobStore()
    submission = JobSubmission(
        input_files=["/tmp/input.nc"],
        output_mode="local",
        output_path="/tmp/out",
    )
    job = store.create(submission)

    cancelled1 = store.cancel(job.id)
    assert cancelled1.status == JobStatus.CANCELLED
    assert cancelled1.completed_at is not None

    cancelled2 = store.cancel(job.id)
    assert cancelled2.status == JobStatus.CANCELLED
    assert cancelled2.completed_at is not None
