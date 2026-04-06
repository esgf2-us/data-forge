import pytest
from pydantic import ValidationError


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


def test_job_submission_rejects_remote_input_scheme() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="local inputs only"):
        JobSubmission(
            input_files=["s3://bucket/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
        )


def test_job_submission_rejects_file_uri_with_host() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="local inputs only"):
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

    with pytest.raises(ValidationError, match="local inputs only"):
        JobSubmission(
            input_files=[""],
            output_mode="local",
            output_path="/tmp/out",
        )


def test_job_submission_rejects_network_path_inputs() -> None:
    from dataforge.models.job import JobSubmission

    with pytest.raises(ValidationError, match="local inputs only"):
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
