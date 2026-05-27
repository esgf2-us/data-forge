from __future__ import annotations

from datetime import datetime, timezone

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


def test_set_publication_persists_on_job() -> None:
    from dataforge.job_store.fake import FakeJobStore
    from dataforge.models.job import JobPublication

    store = FakeJobStore()
    submission = JobSubmission(
        input_files=["/tmp/input.nc"],
        output_mode="local",
        output_path="/tmp/out",
        publish_to_stac=True,
        dataset_id="CMIP6.foo.bar",
    )
    job = store.create(submission)

    publication = JobPublication(
        dataset_id="CMIP6.foo.bar",
        collection="CMIP6",
        item_id="CMIP6.foo.bar",
        aggregate_type="kerchunk",
        href="/tmp/out/job.json",
        datanode="esgf-node.llnl.gov",
        asset_path="/assets/reference_file",
        patch_applied=True,
        published_at=datetime.now(timezone.utc),
    )

    updated = store.set_publication(job.id, publication)

    assert updated.publication == publication
