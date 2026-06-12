from __future__ import annotations

from typing import Any

import pytest

from dataforge.client.api import DataForgeClient


class FakeResponse:
    status_code = 200
    text = "ok"
    reason_phrase = "OK"

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"result_url": "file:///tmp/out/job-123.json"}


class FakeHttpxClient:
    last_headers: dict[str, str] | None = None
    last_request: tuple[str, str, dict[str, Any]] | None = None

    def __init__(self, *, base_url: str, timeout: float, headers: dict[str, str]) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers

    def __enter__(self) -> "FakeHttpxClient":
        self.__class__.last_headers = dict(self.headers)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def request(self, method: str, path: str, **kwargs: Any) -> FakeResponse:
        self.__class__.last_request = (method, path, kwargs)
        return FakeResponse()


def test_client_sends_api_key_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("dataforge.client.api.httpx.Client", FakeHttpxClient)

    client = DataForgeClient(base_url="http://api.example", api_key="secret")
    payload = client.get_job_result("job-123")

    assert payload == {"result_url": "file:///tmp/out/job-123.json"}
    assert FakeHttpxClient.last_headers == {"X-API-Key": "secret"}
    assert FakeHttpxClient.last_request == ("GET", "/api/v1/jobs/job-123/result", {})
