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
            "output_mode": "local",
            "output_path": "/tmp/out",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["id"].startswith("job-")
    assert data["status"] == JobStatus.QUEUED.value

    import dataforge.api.routes.jobs as jobs_routes

    jobs_routes.convert_job.send.assert_called_once_with(data["id"])


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
            "output_mode": "local",
            "output_path": "/tmp/out",
        },
    )
    job_id = created.json()["id"]

    res = c.get(f"/api/v1/jobs/{job_id}/result")
    assert res.status_code == 409
    data = res.json()
    assert data["status"] == JobStatus.QUEUED.value


def test_get_jobs_rejects_invalid_cursor(
    client: tuple[TestClient, FakeJobStore],
) -> None:
    c, _store = client
    res = c.get("/api/v1/jobs", params={"cursor": "not-a-real-cursor"})
    assert res.status_code == 400
