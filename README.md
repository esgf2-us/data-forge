# Data-Forge

Data-Forge is an asynchronous service for generating reference files (starting with Kerchunk) for large climate datasets. It converts local NetCDF-style inputs into cloud-friendly reference files and writes them to local filesystem or S3 destinations.

## Features

- Asynchronous job handling and monitoring
- Kerchunk reference file generation (NetCDF to Zarr references)
- Kerchunk output: local filesystem or S3
- REST API and CLI for job submission and tracking
- No internal storage—the service writes directly to user-managed destinations

## Typical Workflow

1. **Submit a job** with local NetCDF files and parameters (e.g., chunking).
2. **Monitor job status and progress** asynchronously via API/CLI.
3. **Download or access the generated Kerchunk reference files** at your storage endpoint.

## Example CLI Usage

```bash
# Submit a local NetCDF-to-Kerchunk job
$ data-forge submit \
  --input ./data/dataset/*.nc \
  --concat-dims time \
  --metadata '{"project": "CMIP6"}'

# Monitor job progress
$ data-forge status <job-id> --watch

# Get reference file URL or download
$ data-forge get-url <job-id>
$ data-forge download <job-id> --output ./local_refs/
```

## High-Level Architecture

- **API:** FastAPI (REST endpoints), job monitoring/status, OpenAPI docs
- **Job Queue:** Dramatiq + Redis (asynchronous processing)
- **Workers:** Process Kerchunk conversion and write outputs directly to user-managed destinations
- **Output:** Reference files are written to local filesystem or S3
- **No Internal Storage:** Reference files are written directly to user-managed destinations

## Roadmap

- Remote input support
- STAC / ESGF publish integration
- Globus Auth
- Dask-based scaling

## Deployment

- Docker Compose for local/single-node deployment
- Helm chart for Kubernetes (production, scalable)
- Minimal required services: API, worker(s), Redis

## Documentation

See the [`docs/`](docs/) directory for:
- Full user guide and CLI reference
- API specification (OpenAPI/Swagger)
- Deployment guides (Docker, Kubernetes)
- Architecture/design docs
- Contribution instructions

---

Data-Forge aims to make FAIR, cloud-optimized data publishing simple and scalable for the global climate data community.
