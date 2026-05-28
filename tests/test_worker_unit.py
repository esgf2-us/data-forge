from __future__ import annotations

from pathlib import Path

import pytest

from dataforge.job_store.fake import FakeJobStore
from dataforge.models.job import JobStatus, JobSubmission


def test_run_job_sets_running_progress_and_completes_with_file_result_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from dataforge.core.dask_converter import DaskConverter
    from dataforge.workers.converter_worker import run_job

    in_file1 = tmp_path / "in1.nc"
    in_file2 = tmp_path / "in2.nc"
    in_file1.write_bytes(b"dummy")
    in_file2.write_bytes(b"dummy")

    out_dir = tmp_path / "out"
    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file1), str(in_file2)],
            output_mode="local",
            output_path=str(out_dir),
            output_name="job-out",
        )
    )

    expected_output = out_dir / "job-out.json"

    def _fake_convert(self, inputs, config, on_progress=None):
        # Simulate writing the conversion output.
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(expected_output), reference={}, inputs=inputs
        )

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)
    caplog.set_level("INFO")

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.COMPLETED
    assert got.progress_total == 2
    assert got.progress_done == 2
    assert got.result_url == expected_output.resolve().as_uri()
    assert got.result_metadata is not None
    assert got.result_metadata.source_count == 2
    assert got.result_metadata.output_uri == str(expected_output)
    assert "worker job started" in caplog.text
    assert "worker job completed" in caplog.text
    assert "worker job result stored" in caplog.text


def test_run_job_uses_local_defaults_when_output_name_is_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.dask_converter import DaskConverter
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "dataset_001.nc"
    in_file.write_bytes(b"dummy")

    out_dir = tmp_path / "out"
    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(out_dir),
        )
    )

    expected_output = out_dir / "dataset_001.json"

    def _fake_convert(self, inputs, config, on_progress=None):
        assert config.output_name == "dataset_001"
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(expected_output), reference={}, inputs=inputs
        )

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.COMPLETED
    assert got.result_url == expected_output.resolve().as_uri()
    assert got.result_metadata is not None
    assert got.result_metadata.dataset_id is None


def test_run_job_forwards_overwrite_existing_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.dask_converter import DaskConverter
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "dataset_001.nc"
    in_file.write_bytes(b"dummy")

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(tmp_path / "out"),
            overwrite_existing=True,
        )
    )

    def _fake_convert(self, inputs, config, on_progress=None):
        assert config.overwrite_existing is True
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(tmp_path / "out" / "dataset_001.json"),
            reference={},
            inputs=inputs,
        )

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)

    run_job(store, job.id)

    assert store.get(job.id).status == JobStatus.COMPLETED


def test_run_job_is_noop_when_already_running(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.dask_converter import DaskConverter
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
    store.set_status(job.id, expected=JobStatus.QUEUED, new=JobStatus.RUNNING)

    def _should_not_run(self, inputs, config, on_progress=None):
        raise AssertionError("convert should not be called for already running jobs")

    monkeypatch.setattr(DaskConverter, "convert", _should_not_run)

    run_job(store, job.id)

    assert store.get(job.id).status == JobStatus.RUNNING


def test_run_job_cancelled_before_start_has_precedence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.dask_converter import DaskConverter
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

    def _should_not_run(self, inputs, config, on_progress=None):
        raise AssertionError("convert should not be called for cancelled jobs")

    monkeypatch.setattr(DaskConverter, "convert", _should_not_run)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.CANCELLED
    assert got.result_url is None


def test_run_job_cancelled_during_conversion_does_not_write_completed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.dask_converter import DaskConverter
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

    def _fake_convert(self, inputs, config, on_progress=None):
        # Cancellation happens while conversion is running.
        store.cancel(job.id)
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(expected_output), reference={}, inputs=inputs
        )

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.CANCELLED
    assert got.result_url is None


def test_run_job_conversion_error_sets_failed_and_error_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.dask_converter import DaskConverter
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

    def _boom(self, inputs, config, on_progress=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(DaskConverter, "convert", _boom)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.FAILED
    assert got.error_message is not None
    assert "boom" in got.error_message


def test_run_job_publishes_to_stac_when_requested(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from datetime import datetime, timezone

    from dataforge.core.dask_converter import DaskConverter
    from dataforge.models.job import JobPublication
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")
    out_dir = tmp_path / "out"
    expected_output = out_dir / "job-out.json"

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(out_dir),
            output_name="job-out",
            publish_to_stac=True,
            dataset_id="CMIP6.foo.bar",
            use_local_output_as_href=True,
        )
    )

    def _fake_convert(self, inputs, config, on_progress=None):
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(expected_output), reference={}, inputs=inputs
        )

    class FakeStacClient:
        def publish_kerchunk(self, dataset_id, href, datanode=None):
            assert dataset_id == "CMIP6.foo.bar"
            assert href == str(expected_output)
            return JobPublication(
                dataset_id=dataset_id,
                collection="CMIP6",
                item_id=dataset_id,
                aggregate_type="kerchunk",
                href=href,
                datanode="esgf-node.llnl.gov",
                asset_path="/assets/reference_file",
                patch_applied=True,
                published_at=datetime.now(timezone.utc),
            )

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)
    monkeypatch.setattr(
        "dataforge.workers.converter_worker.ESGPublisherStacClient", FakeStacClient
    )

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.COMPLETED
    assert got.result_url == expected_output.resolve().as_uri()
    assert got.publication is not None
    assert got.publication.collection == "CMIP6"


def test_run_job_publish_failure_marks_job_failed_but_keeps_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from dataforge.core.dask_converter import DaskConverter
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")
    out_dir = tmp_path / "out"
    expected_output = out_dir / "job-out.json"

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(out_dir),
            output_name="job-out",
            publish_to_stac=True,
            dataset_id="CMIP6.foo.bar",
            use_local_output_as_href=True,
        )
    )

    def _fake_convert(self, inputs, config, on_progress=None):
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(expected_output), reference={}, inputs=inputs
        )

    class FakeStacClient:
        def publish_kerchunk(self, dataset_id, href, datanode=None):
            raise RuntimeError("patch failed")

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)
    monkeypatch.setattr(
        "dataforge.workers.converter_worker.ESGPublisherStacClient", FakeStacClient
    )

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.FAILED
    assert got.result_url == expected_output.resolve().as_uri()
    assert got.publication is not None
    assert got.publication.patch_applied is False
    assert got.publication.href == str(expected_output)
    assert got.result_metadata is not None
    assert got.error_message is not None
    assert "patch failed" in got.error_message


def test_run_job_maps_local_output_before_stac_publish(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from datetime import datetime, timezone

    from dataforge.core.dask_converter import DaskConverter
    from dataforge.models.job import JobPublication
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")
    out_dir = tmp_path / "mapped" / "cmip6"
    expected_output = out_dir / "job-out.json"

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(out_dir),
            output_name="job-out",
            publish_to_stac=True,
            dataset_id="CMIP6.foo.bar",
        )
    )

    def _fake_convert(self, inputs, config, on_progress=None):
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(expected_output), reference={}, inputs=inputs
        )

    class FakeStacClient:
        def publish_kerchunk(self, dataset_id, href, datanode=None):
            assert href == "https://example.org/refs/cmip6/job-out.json"
            return JobPublication(
                dataset_id=dataset_id,
                collection="CMIP6",
                item_id=dataset_id,
                aggregate_type="kerchunk",
                href=href,
                datanode="esgf-node.llnl.gov",
                asset_path="/assets/reference_file",
                patch_applied=True,
                published_at=datetime.now(timezone.utc),
            )

    monkeypatch.setenv(
        "DATAFORGE_STAC_HREF_MAPPINGS",
        (
            '[{"local_prefix":"'
            + str((tmp_path / "mapped").resolve())
            + '","public_prefix":"https://example.org/refs"}]'
        ),
    )
    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)
    monkeypatch.setattr(
        "dataforge.workers.converter_worker.ESGPublisherStacClient", FakeStacClient
    )

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.COMPLETED
    assert got.publication is not None
    assert got.publication.href == "https://example.org/refs/cmip6/job-out.json"


def test_run_job_can_bypass_mapping_and_use_local_output_as_href(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from datetime import datetime, timezone

    from dataforge.core.dask_converter import DaskConverter
    from dataforge.models.job import JobPublication
    from dataforge.workers.converter_worker import run_job

    in_file = tmp_path / "in.nc"
    in_file.write_bytes(b"dummy")
    out_dir = tmp_path / "out"
    expected_output = out_dir / "job-out.json"

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="local",
            output_path=str(out_dir),
            output_name="job-out",
            publish_to_stac=True,
            dataset_id="CMIP6.foo.bar",
            use_local_output_as_href=True,
        )
    )

    def _fake_convert(self, inputs, config, on_progress=None):
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        from dataforge.models.config import ConversionResult

        return ConversionResult(
            output_uri=str(expected_output), reference={}, inputs=inputs
        )

    class FakeStacClient:
        def publish_kerchunk(self, dataset_id, href, datanode=None):
            assert href == str(expected_output.resolve())
            return JobPublication(
                dataset_id=dataset_id,
                collection="CMIP6",
                item_id=dataset_id,
                aggregate_type="kerchunk",
                href=href,
                datanode="esgf-node.llnl.gov",
                asset_path="/assets/reference_file",
                patch_applied=True,
                published_at=datetime.now(timezone.utc),
            )

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)
    monkeypatch.setattr(
        "dataforge.workers.converter_worker.ESGPublisherStacClient", FakeStacClient
    )

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status == JobStatus.COMPLETED
    assert got.publication is not None
    assert got.publication.href == str(expected_output.resolve())
