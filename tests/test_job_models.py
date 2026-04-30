import pytest
from pydantic import ValidationError


def test_job_create_request_defaults() -> None:
    from dataforge.models.job import JobCreateRequest

    req = JobCreateRequest(input_files=["/tmp/a.nc"])

    assert req.output_name is None
    assert req.concat_dims == ["time"]
    assert req.identical_dims is None
    assert req.inline_threshold == 300
    assert req.metadata is None
    assert req.overwrite_existing is False


def test_job_create_request_rejects_unsafe_output_name() -> None:
    from dataforge.models.job import JobCreateRequest

    with pytest.raises(ValidationError, match="path separators"):
        JobCreateRequest(input_files=["/tmp/a.nc"], output_name="../refs")

    with pytest.raises(ValidationError, match=".json suffix"):
        JobCreateRequest(input_files=["/tmp/a.nc"], output_name="refs.json")


def test_job_create_request_rejects_output_path_field() -> None:
    from dataforge.models.job import JobCreateRequest

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        JobCreateRequest(input_files=["/tmp/a.nc"], output_path="/tmp/out")


def test_job_create_request_rejects_output_mode_field() -> None:
    from dataforge.models.job import JobCreateRequest

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        JobCreateRequest(
            input_files=["/tmp/a.nc"],
            output_path="/tmp/out",
            output_mode="local",
        )


def test_job_submission_defaults() -> None:
    from dataforge.models.job import JobSubmission

    sub = JobSubmission(
        input_files=["/tmp/a.nc"], output_mode="local", output_path="/tmp/out"
    )

    assert sub.output_name is None
    assert sub.concat_dims == ["time"]
    assert sub.identical_dims is None
    assert sub.inline_threshold == 300
    assert sub.metadata is None
    assert sub.overwrite_existing is False


def test_job_submission_rejects_unsafe_output_name() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="path separators"):
        JobSubmission(
            input_files=["/tmp/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
            output_name="refs/unsafe",
        )

    with pytest.raises(ValidationError, match=".json suffix"):
        JobSubmission(
            input_files=["/tmp/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
            output_name="refs.json",
        )


def test_job_submission_rejects_remote_input_scheme() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="local paths"):
        JobSubmission(
            input_files=["s3://bucket/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
        )


def test_job_submission_rejects_file_uri_with_host() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="local paths"):
        JobSubmission(
            input_files=["file://example.com/tmp/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
        )


def test_job_submission_accepts_file_uri_localhost() -> None:
    from dataforge.models.job import JobSubmission

    sub = JobSubmission(
        input_files=["file://localhost/tmp/a.nc"],
        output_mode="local",
        output_path="/tmp/out",
    )
    assert sub.input_files == ["file://localhost/tmp/a.nc"]


def test_job_submission_rejects_empty_inputs() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="input_files must be non-empty"):
        JobSubmission(input_files=[], output_mode="local", output_path="/tmp/out")


def test_job_submission_rejects_empty_input_string() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="local paths"):
        JobSubmission(
            input_files=[""],
            output_mode="local",
            output_path="/tmp/out",
        )


def test_job_submission_rejects_network_path_inputs() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="local paths"):
        JobSubmission(
            input_files=["//example.com/tmp/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
        )


def test_job_submission_rejects_negative_inline_threshold() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="inline_threshold"):
        JobSubmission(
            input_files=["/tmp/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
            inline_threshold=-1,
        )


def test_job_submission_enforces_output_mode_path_match() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="output_path must be an s3://"):
        JobSubmission(
            input_files=["/tmp/a.nc"],
            output_mode="s3",
            output_path="/tmp/out",
        )

    with pytest.raises(ValidationError, match="include an S3 bucket"):
        JobSubmission(
            input_files=["/tmp/a.nc"],
            output_mode="s3",
            output_path="s3://",
        )

    with pytest.raises(ValidationError, match="output_path must be a local"):
        JobSubmission(
            input_files=["/tmp/a.nc"],
            output_mode="local",
            output_path="s3://bucket/out/",
        )


def test_job_submission_rejects_empty_output_path() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="output_path must be non-empty"):
        JobSubmission(
            input_files=["/tmp/a.nc"],
            output_mode="local",
            output_path="",
        )


def test_job_submission_uses_env_default_for_local_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataforge.models.job import JobSubmission

    monkeypatch.setenv("DATAFORGE_LOCAL_OUTPUT_PATH", "/tmp/from-env")

    sub = JobSubmission(
        input_files=["/tmp/a.nc"],
        output_mode="local",
    )

    assert sub.output_path == "/tmp/from-env"


def test_job_submission_uses_env_default_for_s3_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataforge.models.job import JobSubmission

    monkeypatch.setenv("DATAFORGE_S3_OUTPUT_PATH", "s3://bucket/prefix")

    sub = JobSubmission(
        input_files=["/tmp/a.nc"],
        output_mode="s3",
    )

    assert sub.output_path == "s3://bucket/prefix"


def test_job_submission_defaults_local_output_path_to_source_directory(
    tmp_path,
) -> None:
    from dataforge.models.job import JobSubmission

    in_file = tmp_path / "nested" / "a.nc"
    in_file.parent.mkdir(parents=True)
    in_file.touch()

    sub = JobSubmission(
        input_files=[str(in_file)],
        output_mode="local",
    )

    assert sub.output_path == str(in_file.parent.resolve())


def test_job_submission_defaults_local_output_path_for_file_uri_input(
    tmp_path,
) -> None:
    from dataforge.models.job import JobSubmission

    in_file = tmp_path / "nested" / "a.nc"
    in_file.parent.mkdir(parents=True)
    in_file.touch()

    sub = JobSubmission(
        input_files=[f"file://localhost{in_file}"],
        output_mode="local",
    )

    assert sub.output_path == str(in_file.parent.resolve())


def test_local_output_defaults_are_predictable_for_multi_file_inputs(tmp_path) -> None:
    from dataforge.models.job import (
        default_local_output_directory,
        default_local_output_name,
    )

    in_dir = tmp_path / "nested"
    in_dir.mkdir()
    in1 = in_dir / "dataset_001.nc"
    in2 = in_dir / "dataset_002.nc"
    in1.touch()
    in2.touch()

    assert default_local_output_directory([str(in1), str(in2)]) == str(in_dir.resolve())
    assert default_local_output_name([str(in1), str(in2)]) == "dataset"
