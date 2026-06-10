# Data-Forge Helm Chart

The Helm chart lives in `helm/data-forge` and deploys:

- the Data-Forge API
- one or more Data-Forge worker pods
- an in-cluster Redis instance by default
- optional ingress and worker autoscaling

## Install

```bash
helm install data-forge .
```

To upgrade:

```bash
helm upgrade data-forge .
```

## Common Overrides

- `image.repository` / `image.tag`: container image to deploy. The chart defaults to the current release tag; pin a digest if you need immutable deployments.
- `worker.replicaCount`: static worker count
- `worker.autoscaling.enabled`: enable worker HPA
- `dataforge.outputMode`: `local` or `s3`
- `dataforge.brokerRedisUrl` / `dataforge.redisUrl`: external Redis endpoints when `redis.enabled=false`
- `storage.existingClaim`: shared PVC for local outputs
- `extraVolumes`: additional Kubernetes volumes for mounted dataset inputs
- `api.extraVolumeMounts` / `worker.extraVolumeMounts`: per-pod mounts for those extra volumes
- `dataforge.extraVolumeMounts`: shared mounts injected into both API and worker pods
- `podSecurityContext` / `containerSecurityContext`: align pod and container UID/GID with the host
- `redis.enabled`: disable if using an external Redis service
- `secrets.create`: disable if AWS credentials are supplied by another secret injector

## Versioning

- `pyproject.toml` version: application release version
- `Chart.yaml.appVersion`: application release version
- `Chart.yaml.version`: chart release version
- `image.tag`: defaults to the application release version so chart installs do not use `latest`

## Local Output Mode

For local-input jobs, the default output path is the source directory of the inputs, so Kerchunk JSON is written next to the input files. If a job includes `s3://` inputs, you must provide a writable local output path.

For local output mode, mount a shared persistent volume that is visible to both API and worker pods if you want to override the default and write to a dedicated output location. Either:

- set `storage.existingClaim` to an existing PVC, or
- let the chart create a PVC by leaving `storage.existingClaim` empty

The default output path inside the pods is `/data/kerchunks`.

### Example: writable local dataset mount

```yaml
extraVolumes:
  - name: datasets
    hostPath:
      path: /home/titters/devel/work/data-forge/data/samples

dataforge:
  localOutputPath: ""
  localInputMappings:
    - host_prefix: /home/titters/devel/work/data-forge/data/samples
      container_prefix: /datasets
  extraVolumeMounts:
    - name: datasets
      mountPath: /datasets
      readOnly: false

podSecurityContext:
  fsGroup: 1000

containerSecurityContext:
  runAsUser: 1000
  runAsGroup: 1000
  runAsNonRoot: true
```

This keeps the mounted dataset writable, writes the Kerchunk JSON next to the input, and exposes the same host-visible path back to the user and STAC publisher.

### Example: mount a local path

Use `hostPath` when the files live on the node and you want the same path available in the pods.

```yaml
extraVolumes:
  - name: datasets
    hostPath:
      path: /home/titters/devel/work/data-forge/data/samples

dataforge:
  extraVolumeMounts:
    - name: datasets
      mountPath: /datasets
      readOnly: true
  localInputMappings:
    - host_prefix: /home/titters/devel/work/data-forge/data/samples
      container_prefix: /datasets
```

The `host_prefix` is the path users submit on their machine, and `container_prefix` is the path the pods will read.

## Multiple Local Input Volumes

Use `extraVolumes` to define the shared Kubernetes volumes, and `dataforge.extraVolumeMounts` for mounts that should appear in both the API and worker pods. Keep `api.extraVolumeMounts` and `worker.extraVolumeMounts` for pod-specific mounts.

Example:

```yaml
extraVolumes:
  - name: cmip6
    persistentVolumeClaim:
      claimName: cmip6-data
  - name: cmip7
    persistentVolumeClaim:
      claimName: cmip7-data

api:
  extraVolumeMounts:
    - name: cmip6
      mountPath: /datasets/cmip6
      readOnly: true
    - name: cmip7
      mountPath: /datasets/cmip7
      readOnly: true

worker:
  extraVolumeMounts:
    - name: cmip6
      mountPath: /datasets/cmip6
      readOnly: true
    - name: cmip7
      mountPath: /datasets/cmip7
      readOnly: true

dataforge:
  extraVolumeMounts:
    - name: cmip6
      mountPath: /datasets/cmip6
      readOnly: true
    - name: cmip7
      mountPath: /datasets/cmip7
      readOnly: true
  localInputMappings:
    - host_prefix: /cmip6
      container_prefix: /datasets/cmip6
    - host_prefix: /cmip7
      container_prefix: /datasets/cmip7
```

The mappings only rewrite paths inside the application. The actual dataset volumes must still be mounted into both the API and worker pods at the referenced `container_prefix` paths.

## Dask Settings

These settings control intra-job parallelism for multi-file conversion.

- `dataforge.dask.nWorkers`: number of Dask worker processes to start. Leave empty to let the app choose a default.
- `dataforge.dask.threadsPerWorker`: threads per worker process. Higher values can help when tasks are I/O bound.
- `dataforge.dask.memoryLimit`: memory cap per worker, for example `2GiB`.
- `dataforge.dask.localDirectory`: scratch directory for Dask spill files. Leave empty to use the worker default.
- `dataforge.dask.processes`: whether workers use processes (`true`) or threads (`false`).
- `dataforge.dask.parallelThreshold`: minimum number of input files before the app switches to parallel Dask execution.

Example:

```yaml
dataforge:
  dask:
    nWorkers: 4
    threadsPerWorker: "1"
    memoryLimit: 4GiB
    localDirectory: /tmp/dask
    processes: "true"
    parallelThreshold: "8"
```

## S3 Output Mode

Set:

```bash
--set dataforge.outputMode=s3 \
--set dataforge.s3OutputPath=s3://bucket/prefix \
--set dataforge.s3EndpointUrl=https://s3.example.org
```

If credentials are required, set `secrets.awsAccessKeyId` and `secrets.awsSecretAccessKey`, or disable built-in secret creation and inject them separately.

Optional STAC and S3 endpoint settings are omitted from the rendered environment unless you set them explicitly.

## STAC Publish Settings

Set the STAC-related values when publish jobs are enabled:

- `dataforge.stacApi`
- `dataforge.stacTransactionApi`
- `dataforge.stacDatanode`
- `dataforge.stacConfigJson`
- `dataforge.stacHrefMappings`

## Validate Rendered Manifests

```bash
helm template data-forge .
```

Helm validates `values.schema.json` automatically during `helm install`, `helm upgrade`, `helm lint`, and `helm template`.
