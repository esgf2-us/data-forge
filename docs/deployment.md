# Deployment Guide

## Docker Compose

The repository includes a default Compose stack plus output-mode overlays.

Base stack:

```bash
docker compose up --build
```

Local output overlay:

```bash
docker compose -f compose.yaml -f compose.local.yaml up --build
```

S3 output overlay:

```bash
docker compose -f compose.yaml -f compose.s3.yaml up --build
```

The base stack runs:

- `api`: FastAPI application on port `8000`
- `worker`: Dramatiq worker consuming conversion jobs
- `redis`: Redis for broker and job metadata

## Kubernetes With Helm

The Helm chart is located at `helm/data-forge`.

The chart README lives at `helm/data-forge/README.md` and documents the user-facing values and examples.

See [`docs/release-versioning.md`](release-versioning.md) for the version bump workflow.

Install:

```bash
helm install data-forge ./helm/data-forge
```

Upgrade:

```bash
helm upgrade data-forge ./helm/data-forge
```

Render templates locally:

```bash
helm template data-forge ./helm/data-forge
```

Helm also validates the chart's `values.schema.json` during install, upgrade, lint, and template commands.

## Important Values

- `image.repository` and `image.tag`: application image to deploy
- `dataforge.outputMode`: `local` or `s3`
- `dataforge.brokerRedisUrl` and `dataforge.redisUrl`: external Redis endpoints when not deploying in-chart Redis
- `storage.existingClaim`: shared PVC for local output mode
- `extraVolumes`: additional mounted dataset volumes
- `api.extraVolumeMounts` and `worker.extraVolumeMounts`: where those dataset volumes appear in each pod
- `worker.replicaCount`: worker count when autoscaling is disabled
- `worker.autoscaling.enabled`: enable HPA for worker pods
- `redis.enabled`: disable if you are using external Redis

## Health Checks

- API liveness/readiness probes call `GET /health`
- Worker liveness/readiness probes verify Redis broker connectivity
- Redis liveness/readiness probes use TCP socket checks

## STAC Publishing Configuration

When STAC publishing is enabled, configure the following environment-backed chart values:

- `dataforge.stacApi`
- `dataforge.stacTransactionApi`
- `dataforge.stacDatanode`
- `dataforge.stacConfigJson`
- `dataforge.stacHrefMappings`

Optional STAC, S3 endpoint, and AWS credential settings are only rendered into the manifests when you set them.

## Local Storage Notes

For `local` output mode, both API and worker pods must share the same mounted volume and path. The chart supports either:

- a pre-existing PVC via `storage.existingClaim`, or
- a chart-managed PVC

If your inputs live on multiple volumes, add them with `extraVolumes` and mount them into both API and worker with matching `api.extraVolumeMounts` and `worker.extraVolumeMounts`. Then set `dataforge.localInputMappings` so host-side submission paths map onto those in-container mount paths.
