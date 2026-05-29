from __future__ import annotations

import pytest
from typer.testing import CliRunner

from dataforge.cli.main import app


class StubClient:
    def __init__(self) -> None:
        self.created_payload: dict | None = None

    def create_job(self, payload: dict) -> dict:
        self.created_payload = payload
        return {"id": "job-123", "status": "queued"}

    def get_job(self, job_id: str) -> dict:
        assert job_id == "job-123"
        return {
            "id": job_id,
            "status": "completed",
            "progress_done": 2,
            "progress_total": 2,
            "result_url": "file:///tmp/out/job-123.json",
            "error_message": None,
        }

    def list_jobs(self, *, status: str | None, limit: int, cursor: str | None) -> dict:
        assert status == "completed"
        assert limit == 10
        assert cursor is None
        return {
            "jobs": [
                {
                    "id": "job-123",
                    "status": "completed",
                    "created_at": "2026-04-20T00:00:00Z",
                }
            ],
            "next_cursor": None,
        }

    def get_job_result(self, job_id: str) -> dict:
        assert job_id == "job-123"
        return {"result_url": "file:///tmp/out/job-123.json"}

    def get_job_stac(self, job_id: str) -> dict:
        assert job_id == "job-123"
        return {
            "job_id": job_id,
            "publish_to_stac": True,
            "publication": {
                "dataset_id": "CMIP6.foo.bar",
                "collection": "CMIP6",
                "item_id": "CMIP6.foo.bar",
                "aggregate_type": "kerchunk",
                "href": "/tmp/out/job-123.json",
                "datanode": "esgf-node.llnl.gov",
                "asset_path": "/assets/reference_file",
                "patch_applied": True,
                "published_at": "2026-04-20T00:00:00Z",
                "error_message": None,
            },
        }


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_submit_prints_job_summary_and_sends_payload(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    stub = StubClient()
    monkeypatch.setattr("dataforge.cli.main._client", lambda: stub)

    result = runner.invoke(
        app,
        [
            "submit",
            "--input",
            "/tmp/a.nc",
            "--input",
            "/tmp/b.nc",
            "--output-name",
            "refs",
            "--concat-dim",
            "time",
            "--identical-dim",
            "lat",
            "--identical-dim",
            "lon",
            "--metadata",
            '{"project":"CMIP6"}',
        ],
    )

    assert result.exit_code == 0
    assert "Job submitted successfully" in result.stdout
    assert "Job ID: job-123" in result.stdout
    assert stub.created_payload == {
        "input_files": ["/tmp/a.nc", "/tmp/b.nc"],
        "output_name": "refs",
        "concat_dims": ["time"],
        "identical_dims": ["lat", "lon"],
        "inline_threshold": 300,
        "metadata": {"project": "CMIP6"},
    }


def test_submit_resolves_relative_local_inputs_before_submission(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path
) -> None:
    stub = StubClient()
    monkeypatch.setattr("dataforge.cli.main._client", lambda: stub)
    monkeypatch.chdir(tmp_path)

    nested = tmp_path / "data" / "samples"
    nested.mkdir(parents=True)
    in_file = nested / "a.nc"
    in_file.write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["submit", "--input", "data/samples/a.nc"])

    assert result.exit_code == 0
    assert stub.created_payload == {
        "input_files": [str(in_file.resolve())],
        "concat_dims": ["time"],
        "inline_threshold": 300,
    }


def test_submit_preserves_s3_inputs(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    stub = StubClient()
    monkeypatch.setattr("dataforge.cli.main._client", lambda: stub)

    result = runner.invoke(app, ["submit", "--input", "s3://bucket/a.nc"])

    assert result.exit_code == 0
    assert stub.created_payload == {
        "input_files": ["s3://bucket/a.nc"],
        "concat_dims": ["time"],
        "inline_threshold": 300,
    }


def test_submit_can_enable_stac_publish(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    stub = StubClient()
    monkeypatch.setattr("dataforge.cli.main._client", lambda: stub)

    result = runner.invoke(
        app,
        [
            "submit",
            "--input",
            "/tmp/a.nc",
            "--publish-to-stac",
            "--dataset-id",
            "CMIP6.foo.bar",
            "--datanode",
            "esgf-node.llnl.gov",
        ],
    )

    assert result.exit_code == 0
    assert stub.created_payload == {
        "input_files": ["/tmp/a.nc"],
        "concat_dims": ["time"],
        "inline_threshold": 300,
        "publish_to_stac": True,
        "dataset_id": "CMIP6.foo.bar",
        "datanode": "esgf-node.llnl.gov",
    }


def test_submit_can_use_local_output_as_href(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    stub = StubClient()
    monkeypatch.setattr("dataforge.cli.main._client", lambda: stub)

    result = runner.invoke(
        app,
        [
            "submit",
            "--input",
            "/tmp/a.nc",
            "--publish-to-stac",
            "--dataset-id",
            "CMIP6.foo.bar",
            "--use-local-output-as-href",
        ],
    )

    assert result.exit_code == 0
    assert stub.created_payload == {
        "input_files": ["/tmp/a.nc"],
        "concat_dims": ["time"],
        "inline_threshold": 300,
        "publish_to_stac": True,
        "dataset_id": "CMIP6.foo.bar",
        "use_local_output_as_href": True,
    }


def test_submit_can_enable_overwrite_existing(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    stub = StubClient()
    monkeypatch.setattr("dataforge.cli.main._client", lambda: stub)

    result = runner.invoke(
        app,
        [
            "submit",
            "--input",
            "/tmp/a.nc",
            "--overwrite-existing",
        ],
    )

    assert result.exit_code == 0
    assert stub.created_payload == {
        "input_files": ["/tmp/a.nc"],
        "concat_dims": ["time"],
        "inline_threshold": 300,
        "overwrite_existing": True,
    }


def test_submit_rejects_invalid_metadata(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr("dataforge.cli.main._client", lambda: StubClient())

    result = runner.invoke(app, ["submit", "--input", "/tmp/a.nc", "--metadata", "{"])

    assert result.exit_code != 0
    assert "--metadata must be valid JSON" in result.stderr


def test_status_prints_progress(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr("dataforge.cli.main._client", lambda: StubClient())

    result = runner.invoke(app, ["status", "job-123"])

    assert result.exit_code == 0
    assert "Status: completed" in result.stdout
    assert "Progress: 2/2" in result.stdout
    assert "Result: file:///tmp/out/job-123.json" in result.stdout


def test_list_prints_jobs(monkeypatch: pytest.MonkeyPatch, runner: CliRunner) -> None:
    monkeypatch.setattr("dataforge.cli.main._client", lambda: StubClient())

    result = runner.invoke(app, ["list", "--status", "completed", "--limit", "10"])

    assert result.exit_code == 0
    assert "job-123\tcompleted\t2026-04-20T00:00:00Z" in result.stdout


def test_get_url_prints_result(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr("dataforge.cli.main._client", lambda: StubClient())

    result = runner.invoke(app, ["get-url", "job-123"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "file:///tmp/out/job-123.json"


def test_stac_show_prints_publication(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr("dataforge.cli.main._client", lambda: StubClient())

    result = runner.invoke(app, ["stac", "show", "job-123"])

    assert result.exit_code == 0
    assert "Publish to STAC: True" in result.stdout
    assert "Dataset ID: CMIP6.foo.bar" in result.stdout
    assert "Href: /tmp/out/job-123.json" in result.stdout
