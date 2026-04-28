from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock

from dataforge.job_store.fake import FakeJobStore
from dataforge.models.job import JobStatus


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> tuple[TestClient, FakeJobStore]:
    from dataforge.api.app import create_app
    from dataforge.api.deps import get_job_store

    store = FakeJobStore()
    app = create_app()
    app.dependency_overrides[get_job_store] = lambda: store
    monkeypatch.setenv("DATAFORGE_LOCAL_OUTPUT_PATH", "/tmp/from-env")

    # Avoid hitting a real Dramatiq broker in unit tests.
    import dataforge.api.routes.jobs as jobs_routes

    send_mock = Mock()
    monkeypatch.setattr(jobs_routes.convert_job, "send", send_mock)

    return TestClient(app), store


def test_post_creates_queued_job(client: tuple[TestClient, FakeJobStore]) -> None:
    c, _store = client

    res = c.post(
        "/api/v1/jobs",
        json={
            "input_files": ["/tmp/input.nc"],
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"].startswith("job-")
    assert data["status"] == JobStatus.QUEUED.value

    import dataforge.api.routes.jobs as jobs_routes

    jobs_routes.convert_job.send.assert_called_once_with(data["id"])


def test_post_uses_env_default_local_output_path(
    client: tuple[TestClient, FakeJobStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    c, store = client
    monkeypatch.setenv("DATAFORGE_LOCAL_OUTPUT_PATH", "/tmp/from-env")

    res = c.post(
        "/api/v1/jobs",
        json={
            "input_files": ["/tmp/input.nc"],
        },
    )

    assert res.status_code == 201
    job_id = res.json()["id"]
    assert store.get(job_id).submission.output_path == "/tmp/from-env"
    assert store.get(job_id).submission.output_mode == "local"


def test_post_rejects_client_supplied_output_mode(
    client: tuple[TestClient, FakeJobStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    c, _store = client
    monkeypatch.setenv("DATAFORGE_LOCAL_OUTPUT_PATH", "/tmp/from-env")

    res = c.post(
        "/api/v1/jobs",
        json={
            "input_files": ["/tmp/input.nc"],
            "output_mode": "s3",
        },
    )

    assert res.status_code == 422


def test_post_rejects_unsafe_output_name(
    client: tuple[TestClient, FakeJobStore], monkeypatch: pytest.MonkeyPatch
) -> None:
    c, _store = client
    monkeypatch.setenv("DATAFORGE_LOCAL_OUTPUT_PATH", "/tmp/from-env")

    res = c.post(
        "/api/v1/jobs",
        json={
            "input_files": ["/tmp/input.nc"],
            "output_name": "../refs",
        },
    )

    assert res.status_code == 422


def test_get_missing_returns_404(client: tuple[TestClient, FakeJobStore]) -> None:
    c, _store = client

    res = c.get("/api/v1/jobs/job-does-not-exist")
    assert res.status_code == 404


def test_get_result_before_completed_returns_409_and_includes_status(
    client: tuple[TestClient, FakeJobStore],
) -> None:
    c, _store = client

    created = c.post(
        "/api/v1/jobs",
        json={
            "input_files": ["/tmp/input.nc"],
        },
    )
    job_id = created.json()["id"]

    res = c.get(f"/api/v1/jobs/{job_id}/result")
    assert res.status_code == 409
    data = res.json()
    assert data["status"] == JobStatus.QUEUED.value


def test_get_result_after_completed_returns_result_url(
    client: tuple[TestClient, FakeJobStore],
) -> None:
    c, store = client

    created = c.post(
        "/api/v1/jobs",
        json={
            "input_files": ["/tmp/input.nc"],
        },
    )
    job_id = created.json()["id"]

    store.set_status(job_id, expected=JobStatus.QUEUED, new=JobStatus.RUNNING)
    store.set_result(job_id, "file:///tmp/from-env/job.json")
    store.set_status(job_id, expected=JobStatus.RUNNING, new=JobStatus.COMPLETED)

    res = c.get(f"/api/v1/jobs/{job_id}/result")
    assert res.status_code == 200
    assert res.json() == {"result_url": "file:///tmp/from-env/job.json"}


def test_get_jobs_rejects_invalid_cursor(
    client: tuple[TestClient, FakeJobStore],
) -> None:
    c, _store = client
    res = c.get("/api/v1/jobs", params={"cursor": "not-a-real-cursor"})
    assert res.status_code == 400
