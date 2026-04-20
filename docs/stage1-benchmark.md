# Stage 1 Benchmark

Use `scripts/benchmark_stage1.py` to compare single-input and multi-input Kerchunk conversion.

## Inputs

- Local NetCDF files only
- One file list for single-input runs
- One file list for multi-input runs

## Source Data

Use `scripts/source_cmip6_benchmark_data.py` to download a small CMIP6 sample set from the public ESGF S3 bucket.

The default sample set includes:

- One `snd` NetCDF file for the single-input case
- Three sequential `snd` NetCDF files for the multi-input case

## Example

```bash
python scripts/benchmark_stage1.py \
  --single ./data/benchmark-samples/single/*.nc \
  --multi ./data/benchmark-samples/multi/*.nc \
  --repeats 3
```

## Output

The script prints JSON with min/mean/median/max durations for each scenario.

## Notes

- The script writes benchmark outputs under `./data/benchmarks` by default.
- Use representative local files when collecting the final benchmark numbers.
