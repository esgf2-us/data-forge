from __future__ import annotations

from pathlib import Path

from dataforge.job_store.fake import FakeJobStore
from dataforge.models.job import JobSubmission


def test_input_workflow_writes_next_to_source_data(monkeypatch, tmp_path: Path) -> None:
    from dataforge.core.dask_converter import DaskConverter
    from dataforge.workers.converter_worker import run_job

    source_dir = tmp_path / "source"
    source_dir.mkdir(parents=True)
    (source_dir / "dataset_001.nc").write_text("one", encoding="utf-8")
    (source_dir / "dataset_002.nc").write_text("two", encoding="utf-8")

    in_file1 = source_dir / "dataset_001.nc"
    in_file2 = source_dir / "dataset_002.nc"

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file1), str(in_file2)],
            output_mode="input",
        )
    )

    expected_output = source_dir / "dataset.json"

    def _fake_convert(self, inputs, config, on_progress=None):
        assert config.output_prefix == str(source_dir.resolve())
        assert config.output_name == "dataset"
        expected_output.parent.mkdir(parents=True, exist_ok=True)
        expected_output.write_text("{}", encoding="utf-8")
        return str(expected_output)

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status.value == "completed"
    assert got.submission.output_path == str(source_dir.resolve())
    assert got.result_url == expected_output.resolve().as_uri()
    assert expected_output.exists()


def test_input_workflow_uses_single_file_stem(monkeypatch, tmp_path: Path) -> None:
    from dataforge.core.dask_converter import DaskConverter
    from dataforge.workers.converter_worker import run_job

    source_dir = tmp_path / "single"
    source_dir.mkdir(parents=True)
    (source_dir / "dataset.nc").write_text("one", encoding="utf-8")

    in_file = source_dir / "dataset.nc"
    expected_output = source_dir / "dataset.json"

    store = FakeJobStore()
    job = store.create(
        JobSubmission(
            input_files=[str(in_file)],
            output_mode="input",
        )
    )

    def _fake_convert(self, inputs, config, on_progress=None):
        assert config.output_prefix == str(source_dir.resolve())
        assert config.output_name == "dataset"
        expected_output.write_text("{}", encoding="utf-8")
        return str(expected_output)

    monkeypatch.setattr(DaskConverter, "convert", _fake_convert)

    run_job(store, job.id)

    got = store.get(job.id)
    assert got.status.value == "completed"
    assert got.submission.output_path == str(source_dir.resolve())
    assert got.result_url == expected_output.resolve().as_uri()
    assert expected_output.exists()
