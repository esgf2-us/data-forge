import pytest

import redis


def _dummy_job():
    from datetime import datetime, timezone

    from dataforge.models.job import Job, JobStatus, JobSubmission

    now = datetime.now(timezone.utc)
    sub = JobSubmission(
        input_files=["/tmp/a.nc"], output_mode="local", output_path="/tmp/out"
    )
    return Job(
        id="job-123",
        status=JobStatus.QUEUED,
        submission=sub,
        created_at=now,
        updated_at=now,
    )


def test_set_status_translates_not_found_to_keyerror(monkeypatch) -> None:
    from dataforge.job_store.redis import RedisJobStore
    from dataforge.models.job import JobStatus

    store = RedisJobStore("redis://localhost:6379/0")
    monkeypatch.setattr(
        store,
        "_set_status",
        lambda *a, **k: (_ for _ in ()).throw(redis.ResponseError("not_found")),
    )

    with pytest.raises(KeyError):
        store.set_status(
            "job-missing", expected=JobStatus.QUEUED, new=JobStatus.RUNNING
        )


def test_set_status_translates_transition_not_allowed(monkeypatch) -> None:
    from dataforge.job_store.redis import RedisJobStore
    from dataforge.models.job import JobStatus

    store = RedisJobStore("redis://localhost:6379/0")
    monkeypatch.setattr(
        store,
        "_set_status",
        lambda *a, **k: (_ for _ in ()).throw(
            redis.ResponseError("transition_not_allowed")
        ),
    )

    with pytest.raises(ValueError, match="transition not allowed"):
        store.set_status("job-123", expected=JobStatus.QUEUED, new=JobStatus.COMPLETED)


def test_set_status_mismatch_raises_valueerror(monkeypatch) -> None:
    from dataforge.job_store.redis import RedisJobStore
    from dataforge.models.job import JobStatus

    store = RedisJobStore("redis://localhost:6379/0")
    monkeypatch.setattr(store, "_set_status", lambda *a, **k: [0, "running"])

    with pytest.raises(ValueError, match="status mismatch"):
        store.set_status("job-123", expected=JobStatus.QUEUED, new=JobStatus.RUNNING)


def test_cancel_translates_not_found_to_keyerror(monkeypatch) -> None:
    from dataforge.job_store.redis import RedisJobStore

    store = RedisJobStore("redis://localhost:6379/0")
    monkeypatch.setattr(
        store,
        "_cancel",
        lambda *a, **k: (_ for _ in ()).throw(redis.ResponseError("not_found")),
    )

    with pytest.raises(KeyError):
        store.cancel("job-missing")


def test_cancel_translates_transition_not_allowed(monkeypatch) -> None:
    from dataforge.job_store.redis import RedisJobStore

    store = RedisJobStore("redis://localhost:6379/0")
    monkeypatch.setattr(
        store,
        "_cancel",
        lambda *a, **k: (_ for _ in ()).throw(
            redis.ResponseError("transition_not_allowed")
        ),
    )

    with pytest.raises(ValueError, match="transition not allowed"):
        store.cancel("job-123")


def test_cancel_terminal_is_idempotent(monkeypatch) -> None:
    from dataforge.job_store.redis import RedisJobStore

    store = RedisJobStore("redis://localhost:6379/0")
    monkeypatch.setattr(store, "_cancel", lambda *a, **k: [0, "completed"])
    monkeypatch.setattr(store, "get", lambda job_id: _dummy_job())

    job = store.cancel("job-123")
    assert job.id == "job-123"
