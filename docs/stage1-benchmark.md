# Stage 1 Benchmark

Use `scripts/benchmark.py` to compare single-input and multi-input Kerchunk conversion.

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
python scripts/benchmark.py \
  --single ./data/benchmark-samples/single/*.nc \
  --multi ./data/benchmark-samples/multi/*.nc \
  --repeats 3
```

## Container Run

Run the benchmark inside the project container when local Python deps are not installed:

```bash
docker compose run --rm -v "$PWD":/workspace -w /workspace api sh -lc 'python -m pip install fsspec s3fs kerchunk h5py xarray h5netcdf pydantic >/tmp/bench-pip.log 2>&1 && PYTHONPATH=/workspace/src python scripts/benchmark.py --single /workspace/data/benchmark-samples/single/*.nc --multi /workspace/data/benchmark-samples/multi/*.nc --repeats 3 --output-dir /tmp/benchmarks'
```

If you use a container run, the sample files must be HDF5/NetCDF4 inputs that Kerchunk can open.

## Output

The script prints JSON with min/mean/median/max durations for each scenario.

## Notes

- The script writes benchmark outputs under `./data/benchmarks` by default.
- Use representative local files when collecting the final benchmark numbers.
