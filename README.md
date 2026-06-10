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

## uv Setup

```bash
uv venv
uv sync --all-groups --extra server
uv run pytest -vvv
```

For a lightweight CLI-only install, the base package is enough:

```bash
uv sync
uv run data-forge --help
```

Install the `server` extra for the API, worker, conversion backends, STAC publish support, and monitoring stack.

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
- Copy `.env.example` to `.env` and set `DATAFORGE_LOCAL_INPUT_MAPPINGS` to map host local input prefixes onto mounted container prefixes
- Base stack: `docker compose up --build`
- Local output overlay: `docker compose -f docker-compose.yml -f docker-compose.local.yml up --build`
- S3 output overlay: `docker compose -f docker-compose.yml -f docker-compose.s3.yml up --build`
- Helm chart for Kubernetes (production, scalable)
- Minimal required services: API, worker(s), Redis
- Release/versioning workflow: [`docs/release-versioning.md`](docs/release-versioning.md)

For the default repo-local sample data mount, configure:

```bash
DATAFORGE_LOCAL_INPUT_MAPPINGS=[{"host_prefix":"/home/user/data-forge/data","container_prefix":"/inputs/repo-data"}]
```

If you mount additional local input directories into the API and worker containers, add more mapping entries. Local job submissions are rewritten by longest matching `host_prefix`, while `s3://` inputs pass through unchanged.

## Documentation

See the [`docs/`](docs/) directory for:
- Full user guide and CLI reference
- API specification (OpenAPI/Swagger)
- Deployment guides (Docker, Kubernetes)
- Architecture/design docs
- Contribution instructions

---

Data-Forge aims to make FAIR, cloud-optimized data publishing simple and scalable for the global climate data community.
