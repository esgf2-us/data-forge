# Data-Forge

Data-Forge is an asynchronous service for generating reference files (starting with Kerchunk) and publishing searchable catalogs for large climate datasets. It enables data publishers to convert NetCDF (and similar) data into cloud-friendly formats and catalog them, streamlining data access and discovery for the scientific community.

## Features

- Asynchronous job handling and monitoring
- Kerchunk reference file generation (NetCDF to Zarr references)
- Kerchunk output: local filesystem, S3, or ESGF publish (upload + STAC asset update)
- Update existing STAC items with new Kerchunk assets (ESGF-NG integration)
- REST API and CLI for job submission and tracking
- Robust support for remote/cloud data sources
- Secure authentication with Globus Auth
- Scalable Dask-powered parallel processing
- No internal storage—the service writes directly to user-managed destinations

## Typical Workflow

1. **Authenticate** using Globus Auth via CLI or API.
2. **Submit a job** with NetCDF file URLs and parameters (e.g., chunking, output path).
3. **Monitor job status and progress** Async via API/CLI.
4. **Download or access the generated Kerchunk reference files** at your storage endpoint.
5. **View published entries** in a STAC catalog (optionally).

## Example CLI Usage

```bash
# Authenticate via Globus
$ data-forge login

# Submit a NetCDF-to-Kerchunk job
$ data-forge submit \
  --input "s3://my-bucket/dataset/*.nc" \
  --dataset-id "CMIP6.Project.Inst.Model.Experiment.Variable" \
  --concat-dims time \
  --output-path "s3://my-refs-bucket/output/" \
  --metadata '{"project": "CMIP6"}'

# Submit a job and publish to ESGF (upload + update existing STAC Item asset)
$ data-forge submit \
  --input "s3://my-bucket/dataset/*.nc" \
  --dataset-id "CMIP6.Project.Inst.Model.Experiment.Variable" \
  --concat-dims time \
  --esgf-publish \
  --stac-collection-id "cmip6" \
  --stac-item-id "CMIP6.Project.Inst.Model.Experiment.Variable" \
  --stac-asset-key kerchunk_reference

# Monitor job progress
$ data-forge status <job-id> --watch

# Get reference file URL or download
$ data-forge get-url <job-id>
$ data-forge download <job-id> --output ./local_refs/
```

## High-Level Architecture

- **API:** FastAPI (REST endpoints), job monitoring/status, OpenAPI docs
- **Job Queue:** Dramatiq + Redis (asynchronous processing)
- **Workers:** Process Kerchunk conversion, Dask parallelization, write outputs directly to user location
- **STAC Integration:** Optional, for automatic catalog publishing (ESGF-NG, server-authenticated)
- **ESGF Publish:** Optional, for uploading artifacts and patching existing STAC Item assets (server-authenticated)
- **Authentication:** Globus Auth (OAuth2), user-scoped job management
- **No Internal Storage:** Reference files are written to local/S3, or uploaded via ESGF publish (service-managed)

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
