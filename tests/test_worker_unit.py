from __future__ import annotations

from pathlib import Path

import pytest

from dataforge.job_store.fake import FakeJobStore
from dataforge.models.job import JobStatus, JobSubmission


def test_run_job_sets_running_progress_and_completes_with_file_result_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")

    out_dir = tmp_path / "out"
    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(out_dir),
            output_name="job-out",
        )
    )

    expected_output = out_dir / "job-out.json"

    def _fake_convert(self, inputs, config):
        # Simulate writing the conversion output.
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        return str(expected_output)

    monkeypatch.setattr(KerchunkConverter, "convert", _fake_convert)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.COMPLETED
    assert got.progress_total == 1
    assert got.progress_done == 1
    assert got.result_url == expected_output.resolve().as_uri()


def test_run_job_cancelled_before_start_has_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(tmp_path / "out"),
            output_name="job-out",
        )
    )
    store.set_status(job.id, expected=JobStatus.QUEUED, new=JobStatus.CANCELLED)

    def _should_not_run(self, inputs, config):
        raise AssertionError("convert should not be called for cancelled jobs")

    monkeypatch.setattr(KerchunkConverter, "convert", _should_not_run)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.CANCELLED
    assert got.result_url is None


def test_run_job_cancelled_during_conversion_does_not_write_completed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")

    out_dir = tmp_path / "out"
    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(out_dir),
            output_name="job-out",
        )
    )

    expected_output = out_dir / "job-out.json"

    def _fake_convert(self, inputs, config):
        # Cancellation happens while conversion is running.
        store.cancel(job.id)
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        return str(expected_output)

    monkeypatch.setattr(KerchunkConverter, "convert", _fake_convert)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.CANCELLED
    assert got.result_url is None


def test_run_job_conversion_error_sets_failed_and_error_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.converter import KerchunkConverter
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(tmp_path / "out"),
            output_name="job-out",
        )
    )

    def _boom(self, inputs, config):
        raise RuntimeError("boom")

    monkeypatch.setattr(KerchunkConverter, "convert", _boom)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.FAILED
    assert got.error_message is not None
    assert "boom" in got.error_message
