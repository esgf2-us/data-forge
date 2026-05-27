# Stage 5 Benchmark

Use `scripts/benchmark.py` to compare sequential Kerchunk conversion against the Dask-backed converter.

## Goals

- Measure the cost of Dask startup on small inputs
- Measure the speedup for multi-file runs
- Verify the configured worker count and memory settings are stable for representative datasets

## Example

```bash
python scripts/benchmark.py \
  --single ./data/benchmark-samples/single/*.nc \
  --multi ./data/benchmark-samples/multi/*.nc \
  --mode both \
  --repeats 3 \
  --dask-workers 4 \
  --dask-memory-limit 2GiB \
  --dask-local-directory /tmp/dataforge-dask
```

## Output

The script prints JSON with separate `sequential` and `dask` sections for single-file and multi-file scenarios.

When `--mode both` is used, a `comparison` section reports mean-duration speedups for single-file and multi-file runs.

## Notes

- Use `--dask-parallel-threshold 1` during benchmarking to force the Dask path for the selected input set.
- Use `--dask-local-directory` when you want worker spill data on a specific filesystem.
- Keep the same input file lists across runs so sequential and Dask timings remain comparable.
