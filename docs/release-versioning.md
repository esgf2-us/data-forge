# Release and Versioning

Data-Forge uses a simple release scheme:

- `pyproject.toml` version is the application release version.
- `helm/data-forge/Chart.yaml` `appVersion` tracks the application release version.
- `helm/data-forge/Chart.yaml` `version` tracks the chart release version.
- `helm/data-forge/values.yaml` pins the deployable image tag to the application release version.

## Bumping a Release

Use the helper script to update all relevant files together:

```bash
python scripts/bump_version.py 0.2.0
```

This updates:

- `pyproject.toml`
- `helm/data-forge/Chart.yaml`
- `helm/data-forge/values.yaml`

## Before Opening a PR

- Run `helm lint helm/data-forge`
- Run `helm template data-forge helm/data-forge`
- Run the targeted test suite for the changes

## Release Rule of Thumb

- Code changes that ship a new app version should bump both the package and chart versions.
- Chart-only changes should bump the chart version.
- Avoid `latest` for deployable chart images.
- Prerelease tags such as `v0.1.2-beta.1` should publish versioned artifacts without updating `latest`.

## Release Tags

Use these tag forms for release staging:

- Alpha: `v0.1.2-alpha.1`
- Beta: `v0.1.2-beta.1`
- Release candidate: `v0.1.2-rc.1`
- Stable release: `v0.1.2`

Meaning:

- Alpha: early validation, likely unstable
- Beta: broader site testing
- RC: final verification before stable
- Stable: production release

## Release Workflow

Use a release branch to stage alpha, beta, and RC work before the stable cut.

Example branch names:

- `release/0.1.2-alpha`
- `release/0.1.2-beta`
- `release/0.1.2-rc`

Recommended flow:

1. Bump `pyproject.toml`, `helm/data-forge/Chart.yaml`, and `helm/data-forge/values.yaml` to the prerelease version.
2. Run `helm lint helm/data-forge`.
3. Run `helm template data-forge helm/data-forge`.
4. Smoke test the container or chart in the target site environment.
5. Tag the release with the matching `vX.Y.Z-alpha.N`, `vX.Y.Z-beta.N`, or `vX.Y.Z-rc.N` tag.
6. After validation is complete, tag the stable `vX.Y.Z` release and let the release workflow publish the image and chart.

## GitHub Actions

- Pull requests from forks run host `pytest`.
- Same-repository pull requests build preview images tagged `pr-<number>` and smoke test the `PR Test` workflow against the pushed runtime image.
- Pushes to `main` run the `Main Smoke Test` workflow against the published `latest` image.
- Git tags matching `v*` build and push a release image tagged with the version number and package the Helm chart with the same version.
- Release chart archives are attached to the GitHub Release created from the tag and pushed to `ghcr.io/esgf2-us/data-forge-chart`.
- The release workflow verifies that the tag matches `pyproject.toml`, `helm/data-forge/Chart.yaml`, and the chart image tag before publishing.
- OCI chart installs are versioned; use `--version <chart-version>` to install or upgrade a specific release.
