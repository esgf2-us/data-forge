from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from dataforge.core.converter import KerchunkConverter
from dataforge.models.config import ConversionConfig


def _parse_inputs(values: list[str]) -> list[str]:
    inputs = [v.strip() for v in values if v.strip()]
    if not inputs:
        raise ValueError("at least one input file is required")
    return inputs


def _run_once(inputs: list[str], config: ConversionConfig) -> float:
    converter = KerchunkConverter()
    start = time.perf_counter()
    converter.convert(inputs, config)
    return time.perf_counter() - start


def benchmark(
    inputs: list[str], output_dir: str, output_name: str, repeats: int
) -> dict:
    config = ConversionConfig(output_prefix=output_dir, output_name=output_name)
    durations = [_run_once(inputs, config) for _ in range(repeats)]
    return {
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
    args = parser.parse_args()

    output_dir = str(Path(args.output_dir).resolve())
    single = benchmark(
        _parse_inputs(args.single), output_dir, "stage1-single", args.repeats
    )
    multi = benchmark(
        _parse_inputs(args.multi), output_dir, "stage1-multi", args.repeats
    )

    print(json.dumps({"single": single, "multi": multi}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
