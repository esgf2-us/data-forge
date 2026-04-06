import pytest


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

    with pytest.raises(ValueError, match="local inputs only"):
        JobSubmission(
            input_files=["s3://bucket/a.nc"],
            output_mode="local",
            output_path="/tmp/out",
        )
