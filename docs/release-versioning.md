# Release and Versioning

Data-Forge uses a simple release scheme:

- `pyproject.toml` version is the application release version.
- `helm/data-forge/Chart.yaml` `appVersion` tracks the application release version.
- `helm/data-forge/Chart.yaml` `version` tracks the chart release version.
- `helm/data-forge/values.yaml` and `helm/data-forge/overrides.yaml` pin the deployable image tag to the application release version.

## Bumping a Release

Use the helper script to update all relevant files together:

```bash
python scripts/bump_version.py 0.2.0
```

This updates:

- `pyproject.toml`
- `helm/data-forge/Chart.yaml`
- `helm/data-forge/values.yaml`
- `helm/data-forge/overrides.yaml`

## Before Opening a PR

- Run `helm lint helm/data-forge`
- Run `helm template data-forge helm/data-forge -f helm/data-forge/overrides.yaml`
- Run the targeted test suite for the changes

## Release Rule of Thumb

- Code changes that ship a new app version should bump both the package and chart versions.
- Chart-only changes should bump the chart version.
- Avoid `latest` for deployable chart images.

## GitHub Actions

- Pull requests build and push a preview image tagged `pr-<number>` to GHCR.
- Git tags matching `v*` build and push a release image tagged with the version number and package the Helm chart with the same version.
- Release chart archives are attached to the GitHub Release created from the tag and pushed to `ghcr.io/esgf2-us/data-forge-chart`.
- PR image pushes run for same-repository pull requests; forked PRs skip the publish step.
- The release workflow verifies that the tag matches `pyproject.toml`, `helm/data-forge/Chart.yaml`, and the chart image tag before publishing.
- OCI chart installs are versioned; use `--version <chart-version>` to install or upgrade a specific release.
