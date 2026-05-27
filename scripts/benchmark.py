from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from dataforge.core.converter import KerchunkConverter
from dataforge.core.dask_converter import DaskConverter
from dataforge.models.config import ConversionConfig
from dataforge.models.dask_config import DaskConfig


def _parse_inputs(values: list[str]) -> list[str]:
    inputs = [v.strip() for v in values if v.strip()]
    if not inputs:
        raise ValueError("at least one input file is required")
    return inputs


def _run_once(
    converter: KerchunkConverter | DaskConverter,
    inputs: list[str],
    config: ConversionConfig,
) -> float:
    start = time.perf_counter()
    converter.convert(inputs, config)
    return time.perf_counter() - start


def benchmark(
    converter: KerchunkConverter | DaskConverter,
    inputs: list[str],
    output_dir: str,
    output_name: str,
    repeats: int,
) -> dict:
    config = ConversionConfig(output_prefix=output_dir, output_name=output_name)
    durations = [_run_once(converter, inputs, config) for _ in range(repeats)]
    return {
        "converter": converter.__class__.__name__,
        "inputs": inputs,
        "output_dir": output_dir,
        "output_name": output_name,
        "repeats": repeats,
        "min_seconds": min(durations),
        "max_seconds": max(durations),
        "mean_seconds": statistics.mean(durations),
        "median_seconds": statistics.median(durations),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark Kerchunk conversion")
    parser.add_argument(
        "--single",
        nargs="+",
        required=True,
        help="Local input files for the single-input benchmark",
    )
    parser.add_argument(
        "--multi",
        nargs="+",
        required=True,
        help="Local input files for the multi-input benchmark",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path("./data/benchmarks").resolve()),
        help="Directory used for benchmark outputs",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of runs per benchmark",
    )
    parser.add_argument(
        "--mode",
        choices=("sequential", "dask", "both"),
        default="both",
        help="Which converter path to benchmark.",
    )
    parser.add_argument(
        "--dask-workers",
        type=int,
        default=None,
        help="Optional Dask worker count override.",
    )
    parser.add_argument(
        "--dask-threads-per-worker",
        type=int,
        default=1,
        help="Dask threads per worker.",
    )
    parser.add_argument(
        "--dask-memory-limit",
        default="2GiB",
        help="Dask memory limit per worker.",
    )
    parser.add_argument(
        "--dask-local-directory",
        default=None,
        help="Optional Dask spill/work directory.",
    )
    parser.add_argument(
        "--dask-processes",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use Dask worker processes instead of threads.",
    )
    parser.add_argument(
        "--dask-parallel-threshold",
        type=int,
        default=1,
        help="Minimum inputs before Dask parallelization is used.",
    )
    args = parser.parse_args()

    output_dir = str(Path(args.output_dir).resolve())
    single_inputs = _parse_inputs(args.single)
    multi_inputs = _parse_inputs(args.multi)

    sequential_converter = KerchunkConverter()
    dask_converter = DaskConverter(
        dask_config=DaskConfig(
            n_workers=args.dask_workers,
            threads_per_worker=args.dask_threads_per_worker,
            memory_limit=args.dask_memory_limit,
            local_directory=args.dask_local_directory,
            processes=args.dask_processes,
            parallel_threshold=args.dask_parallel_threshold,
        )
    )

    results: dict[str, dict[str, dict]] = {}

    if args.mode in {"sequential", "both"}:
        results["sequential"] = {
            "single": benchmark(
                sequential_converter,
                single_inputs,
                output_dir,
                "stage5-sequential-single",
                args.repeats,
            ),
            "multi": benchmark(
                sequential_converter,
                multi_inputs,
                output_dir,
                "stage5-sequential-multi",
                args.repeats,
            ),
        }

    if args.mode in {"dask", "both"}:
        results["dask"] = {
            "single": benchmark(
                dask_converter,
                single_inputs,
                output_dir,
                "stage5-dask-single",
                args.repeats,
            ),
            "multi": benchmark(
                dask_converter,
                multi_inputs,
                output_dir,
                "stage5-dask-multi",
                args.repeats,
            ),
        }

    if "sequential" in results and "dask" in results:
        results["comparison"] = {
            "single_speedup": (
                results["sequential"]["single"]["mean_seconds"]
                / results["dask"]["single"]["mean_seconds"]
            ),
            "multi_speedup": (
                results["sequential"]["multi"]["mean_seconds"]
                / results["dask"]["multi"]["mean_seconds"]
            ),
        }

    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
