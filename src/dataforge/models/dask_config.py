from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DaskConfig(BaseModel):
    """Configuration for the Dask local cluster used within a conversion job."""

    n_workers: int | None = Field(
        default=None,
        description="Number of Dask workers. None = auto (based on available CPUs).",
    )
    threads_per_worker: int = Field(
        default=1,
        description="Threads per Dask worker. 1 is safest for HDF5/kerchunk.",
    )
    memory_limit: str = Field(
        default="2GiB",
        description="Memory limit per worker (e.g. '2GiB', '512MiB').",
    )
    local_directory: str | None = Field(
        default=None,
        description=(
            "Optional spill/work directory used by Dask workers for temporary "
            "data when memory pressure is high."
        ),
    )
    processes: bool = Field(
        default=True,
        description="Use processes (True) or threads (False) for workers.",
    )
    parallel_threshold: int = Field(
        default=4,
        description=(
            "Minimum number of input files before Dask parallelization is used. "
            "Below this threshold, sequential processing is used instead."
        ),
    )

    @field_validator("threads_per_worker")
    @classmethod
    def _validate_threads(cls, v: int) -> int:
        if v < 1:
            raise ValueError("threads_per_worker must be >= 1")
        return v

    @field_validator("parallel_threshold")
    @classmethod
    def _validate_threshold(cls, v: int) -> int:
        if v < 1:
            raise ValueError("parallel_threshold must be >= 1")
        return v

    @field_validator("local_directory")
    @classmethod
    def _validate_local_directory(cls, v: str | None) -> str | None:
        if v is None:
            return None
        stripped = v.strip()
        return stripped or None
