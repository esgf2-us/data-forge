"""Dask-parallelized Kerchunk converter.

For multi-file jobs above the parallel_threshold, individual file reference
generation is distributed across a Dask LocalCluster.  Small jobs fall back
to the sequential KerchunkConverter.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Generator

from dask.distributed import Client, LocalCluster, as_completed

from dataforge.core.converter import (
    KerchunkConverter,
    _join_output,
    _normalize_local_input,
)
from dataforge.core.storage import StorageWriter
from dataforge.models.config import (
    ConversionConfig,
    ConversionError,
    ConversionResult,
    InvalidInputError,
)
from dataforge.models.dask_config import DaskConfig

logger = logging.getLogger(__name__)


def _generate_single_reference(path: str, inline_threshold: int) -> dict[str, Any]:
    """Generate a Kerchunk reference for a single file.

    This function is submitted to Dask workers and must be self-contained
    (imports inside to ensure serializability).
    """
    from kerchunk.hdf import SingleHdf5ToZarr

    return SingleHdf5ToZarr(path, inline_threshold=inline_threshold).translate()


@contextmanager
def _dask_cluster(config: DaskConfig) -> Generator[Client, None, None]:
    """Create and tear down a Dask LocalCluster + Client."""
    cluster = LocalCluster(
        n_workers=config.n_workers,
        threads_per_worker=config.threads_per_worker,
        memory_limit=config.memory_limit,
        local_directory=config.local_directory,
        processes=config.processes,
    )
    client = Client(cluster)
    logger.info(
        "dask cluster started",
        extra={
            "n_workers": len(cluster.workers),
            "dashboard": cluster.dashboard_link,
        },
    )
    try:
        yield client
    finally:
        client.close()
        cluster.close()
        logger.info("dask cluster shut down")


class DaskConverter:
    """Kerchunk converter with Dask-based parallelization for multi-file jobs.

    For jobs with fewer inputs than ``dask_config.parallel_threshold``, this
    delegates to the sequential ``KerchunkConverter``.
    """

    def __init__(
        self,
        dask_config: DaskConfig | None = None,
        storage: StorageWriter | None = None,
    ) -> None:
        self._dask_config = dask_config or DaskConfig()
        self._storage = storage or StorageWriter()
        self._sequential = KerchunkConverter(storage=self._storage)

    @property
    def dask_config(self) -> DaskConfig:
        return self._dask_config

    def convert(
        self,
        inputs: list[str],
        config: ConversionConfig,
        on_progress: Any | None = None,
    ) -> ConversionResult:
        """Convert input files to a Kerchunk reference.

        Parameters
        ----------
        inputs:
            List of input file URIs/paths.
        config:
            Conversion configuration (output path, thresholds, etc.).
        on_progress:
            Optional callback ``(done: int, total: int) -> None`` invoked as
            individual file references complete.

        Returns
        -------
        ConversionResult with the output URI and combined reference dict.
        """
        if not inputs:
            raise InvalidInputError("inputs must be non-empty")

        # Below parallel threshold, use sequential converter.
        if len(inputs) < self._dask_config.parallel_threshold:
            return self._sequential.convert(inputs, config)

        local_inputs = [_normalize_local_input(u) for u in inputs]
        output_uri = _join_output(config.output_prefix, config.output_name)

        try:
            reference = self._build_parallel(local_inputs, config, on_progress)
        except (InvalidInputError, ConversionError):
            raise
        except Exception as e:
            raise ConversionError(str(e)) from e

        self._storage.write_json(
            output_uri, reference, overwrite=config.overwrite_existing
        )

        return ConversionResult(
            output_uri=output_uri, reference=reference, inputs=local_inputs
        )

    def _build_parallel(
        self,
        inputs: list[str],
        config: ConversionConfig,
        on_progress: Any | None = None,
    ) -> dict[str, Any]:
        """Generate references in parallel using Dask, then combine."""
        try:
            from kerchunk.combine import MultiZarrToZarr

            total = len(inputs)
            logger.info(
                "starting parallel reference generation",
                extra={"n_files": total},
            )

            with _dask_cluster(self._dask_config) as client:
                futures = {
                    client.submit(
                        _generate_single_reference,
                        path,
                        config.inline_threshold,
                        pure=False,
                    ): i
                    for i, path in enumerate(inputs)
                }

                # Gather results as they complete, but preserve input order so
                # concat_dims remain deterministic.
                refs: list[dict[str, Any] | None] = [None] * total
                for done, future in enumerate(as_completed(futures), start=1):
                    refs[futures[future]] = future.result()
                    if on_progress is not None:
                        on_progress(done, total)

            logger.info(
                "parallel reference generation complete",
                extra={"n_files": total},
            )

            if len(refs) == 1:
                ref = refs[0]
                if ref is None:
                    raise ConversionError("missing Dask reference result")
                return ref

            ordered_refs = [ref for ref in refs if ref is not None]
            if len(ordered_refs) != total:
                raise ConversionError("missing one or more Dask reference results")

            mzz = MultiZarrToZarr(
                ordered_refs,
                concat_dims=list(config.concat_dims),
                identical_dims=list(config.identical_dims or []),
            )
            return mzz.translate()
        except (InvalidInputError, ConversionError):
            raise
        except Exception as e:
            raise ConversionError(str(e)) from e
