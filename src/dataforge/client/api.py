from __future__ import annotations

import os
from typing import Any

import httpx


def _api_root() -> str:
    return os.getenv("DATAFORGE_API_URL", "http://127.0.0.1:8000").rstrip("/")


class DataForgeClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = (base_url or _api_root()).rstrip("/")
        self._timeout = timeout
        self._headers: dict[str, str] = {}
        if api_key:
            self._headers["X-API-Key"] = api_key

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/jobs", json=payload)

    def get_job(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/jobs/{job_id}")

    def list_jobs(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        if cursor is not None:
            params["cursor"] = cursor
        return self._request("GET", "/api/v1/jobs", params=params)

    def get_job_result(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/jobs/{job_id}/result")

    def get_job_stac(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/jobs/{job_id}/stac")

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/jobs/{job_id}")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            with httpx.Client(
                base_url=self._base_url,
                timeout=self._timeout,
                headers=self._headers,
            ) as client:
                response = client.request(method, path, **kwargs)
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = _error_detail(e.response)
            raise RuntimeError(
                f"API request failed with status {e.response.status_code}: {detail}"
            ) from e
        except httpx.HTTPError as e:
            raise RuntimeError(f"API request failed: {e}") from e

        return response.json()


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text or response.reason_phrase
    if isinstance(payload, dict) and "detail" in payload:
        return str(payload["detail"])
    return str(payload)
