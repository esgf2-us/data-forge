from __future__ import annotations

import os

import pytest
import redis


def _redis_url() -> str | None:
    return os.getenv("DATAFORGE_TEST_REDIS_URL")


@pytest.mark.skipif(not _redis_url(), reason="requires DATAFORGE_TEST_REDIS_URL")
def test_redis_job_store_roundtrip() -> None:
    from dataforge.job_store.redis import RedisJobStore
    from dataforge.models.job import JobStatus, JobSubmission

    # Expected: DATAFORGE_TEST_REDIS_URL points at a disposable Redis DB.
    # We call FLUSHDB to guarantee test isolation.
    r = redis.Redis.from_url(
        os.environ["DATAFORGE_TEST_REDIS_URL"], decode_responses=True
    )
    r.flushdb()

    store = RedisJobStore(os.environ["DATAFORGE_TEST_REDIS_URL"])
    submission = JobSubmission(
        input_files=["/tmp/input.nc"],
        output_mode="local",
        output_path="/tmp/out",
        output_name=None,
    )

    job = store.create(submission)
    got = store.get(job.id)

    assert got.id == job.id
    assert got.status == JobStatus.QUEUED
    assert got.submission.output_name is None
    assert got.updated_at >= got.created_at


@pytest.mark.skipif(not _redis_url(), reason="requires DATAFORGE_TEST_REDIS_URL")
def test_redis_job_store_list_cursor_is_deterministic_no_duplicates() -> None:
    from dataforge.job_store.redis import RedisJobStore
    from dataforge.models.job import JobSubmission

    # Expected: DATAFORGE_TEST_REDIS_URL points at a disposable Redis DB.
    # We call FLUSHDB to guarantee test isolation.
    r = redis.Redis.from_url(
        os.environ["DATAFORGE_TEST_REDIS_URL"], decode_responses=True
    )
    r.flushdb()

    store = RedisJobStore(os.environ["DATAFORGE_TEST_REDIS_URL"])
    j1 = store.create(
        JobSubmission(
            input_files=["/tmp/a.nc"], output_mode="local", output_path="/tmp/out"
        )
    )
    j2 = store.create(
        JobSubmission(
            input_files=["/tmp/b.nc"], output_mode="local", output_path="/tmp/out"
        )
    )

    page1, cursor = store.list(status=None, limit=1, cursor=None)
    assert len(page1) == 1
    assert cursor is not None

    page2, cursor2 = store.list(status=None, limit=10, cursor=cursor)

    all_ids = [x.id for x in page1 + page2]
    assert len(all_ids) == len(set(all_ids))
    assert {j1.id, j2.id} == set(all_ids)
    assert cursor2 is None or cursor2 != cursor
