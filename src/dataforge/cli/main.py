from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import tomllib

import click
import typer

from dataforge.client.api import DataForgeClient
from dataforge.core.input_paths import (
    input_is_local,
    local_input_host_path,
    validate_input_reference,
)

app = typer.Typer(add_completion=False, no_args_is_help=True)
stac_app = typer.Typer(add_completion=False, no_args_is_help=True)
app.add_typer(stac_app, name="stac")


@dataclass
class CliConfig:
    server_url: str | None = None
    api_key: str | None = None


def _default_config_path() -> Path:
    return Path.home() / ".dataforge" / "config"


def _load_cli_config(config_path: str | None) -> CliConfig:
    path = Path(config_path).expanduser() if config_path else _default_config_path()
    if not path.exists():
        return CliConfig()

    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except OSError as e:
        raise typer.BadParameter(f"unable to read config file {path}: {e}") from e
    except tomllib.TOMLDecodeError as e:
        raise typer.BadParameter(f"invalid TOML in config file {path}: {e}") from e

    if not isinstance(raw, dict):
        raise typer.BadParameter(f"config file {path} must contain a TOML table")

    if isinstance(raw.get("default"), dict):
        raw = raw["default"]

    server_url = raw.get("server_url")
    api_key = raw.get("api_key")
    if server_url is not None and not isinstance(server_url, str):
        raise typer.BadParameter(f"config file {path}: server_url must be a string")
    if api_key is not None and not isinstance(api_key, str):
        raise typer.BadParameter(f"config file {path}: api_key must be a string")

    server_url_value = server_url.strip() if isinstance(server_url, str) else None
    api_key_value = api_key.strip() if isinstance(api_key, str) else None
    return CliConfig(
        server_url=server_url_value or None,
        api_key=api_key_value or None,
    )


@app.callback()
def main(
    ctx: typer.Context,
    config: Annotated[
        str | None,
        typer.Option(
            "--config",
            help="Path to a TOML config file. Defaults to ~/.dataforge/config.",
        ),
    ] = None,
    server_url: Annotated[
        str | None,
        typer.Option("--server-url", help="Data-Forge server address."),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option("--api-key", help="API key sent as the X-API-Key header."),
    ] = None,
) -> None:
    file_config = _load_cli_config(config)
    ctx.obj = CliConfig(
        server_url=server_url if server_url is not None else file_config.server_url,
        api_key=api_key if api_key is not None else file_config.api_key,
    )


def _client() -> DataForgeClient:
    ctx = click.get_current_context()
    state = ctx.obj if isinstance(ctx.obj, CliConfig) else None
    return DataForgeClient(
        base_url=state.server_url if state else None,
        api_key=state.api_key if state else None,
    )


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def _expand_cli_input(value: str) -> list[str]:
    try:
        validate_input_reference(value)
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--input") from e

    return [value]


def _normalize_cli_inputs(input_files: list[str]) -> list[str]:
    normalized: list[str] = []
    for value in input_files:
        for expanded in _expand_cli_input(value):
            if input_is_local(expanded):
                normalized.append(str(local_input_host_path(expanded)))
            else:
                normalized.append(expanded)
    return normalized


@app.command("submit")
def submit(
    input_files: Annotated[
        list[str],
        typer.Option("--input", help="Input file path or file:// URL.", min=1),
    ],
    output_name: Annotated[
        str | None, typer.Option("--output-name", help="Output file stem.")
    ] = None,
    concat_dims: Annotated[
        list[str],
        typer.Option(
            "--concat-dim",
            help="Dimension to concatenate across. Repeat to specify multiple.",
        ),
    ] = ["time"],
    identical_dims: Annotated[
        list[str] | None,
        typer.Option(
            "--identical-dim",
            help="Dimension expected to match across inputs. Repeat to specify multiple.",
        ),
    ] = None,
    inline_threshold: Annotated[
        int,
        typer.Option("--inline-threshold", min=0, help="Kerchunk inline threshold."),
    ] = 300,
    metadata: Annotated[
        str | None, typer.Option("--metadata", help="JSON object metadata.")
    ] = None,
    overwrite_existing: Annotated[
        bool,
        typer.Option(
            "--overwrite-existing",
            help="Overwrite existing output files when present.",
        ),
    ] = False,
    publish_to_stac: Annotated[
        bool,
        typer.Option(
            "--publish-to-stac",
            help="Publish the generated Kerchunk output to the configured STAC catalog.",
        ),
    ] = False,
    dataset_id: Annotated[
        str | None,
        typer.Option(
            "--dataset-id", help="Dataset identifier used to look up the STAC Item."
        ),
    ] = None,
    datanode: Annotated[
        str | None,
        typer.Option(
            "--datanode",
            help="Optional datanode/site override for the published aggregate.",
        ),
    ] = None,
    use_local_output_as_href: Annotated[
        bool,
        typer.Option(
            "--use-local-output-as-href",
            help="Publish the resolved local output path directly instead of applying STAC href prefix mapping.",
        ),
    ] = False,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full API response as JSON.")
    ] = False,
) -> None:
    payload: dict[str, Any] = {
        "input_files": _normalize_cli_inputs(input_files),
        "concat_dims": list(concat_dims),
        "inline_threshold": inline_threshold,
    }
    if output_name is not None:
        payload["output_name"] = output_name
    if identical_dims:
        payload["identical_dims"] = list(identical_dims)
    if metadata is not None:
        try:
            payload["metadata"] = json.loads(metadata)
        except json.JSONDecodeError as e:
            raise typer.BadParameter("--metadata must be valid JSON") from e
    if overwrite_existing:
        payload["overwrite_existing"] = True
    if publish_to_stac:
        payload["publish_to_stac"] = True
    if dataset_id is not None:
        payload["dataset_id"] = dataset_id
    if datanode is not None:
        payload["datanode"] = datanode
    if use_local_output_as_href:
        payload["use_local_output_as_href"] = True

    job = _client().create_job(payload)
    if as_json:
        _emit_json(job)
        return

    typer.echo("Job submitted successfully")
    typer.echo(f"Job ID: {job['id']}")
    typer.echo(f"Status: {job['status']}")


@app.command()
def status(
    job_id: str,
    watch: Annotated[
        bool,
        typer.Option("--watch", help="Poll until the job reaches a terminal state."),
    ] = False,
    interval: Annotated[
        float, typer.Option("--interval", min=0.1, help="Polling interval in seconds.")
    ] = 1.0,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full API response as JSON.")
    ] = False,
) -> None:
    terminal = {"completed", "failed", "cancelled"}

    while True:
        job = _client().get_job(job_id)
        if as_json:
            _emit_json(job)
        else:
            typer.echo(f"Job ID: {job['id']}")
            typer.echo(f"Status: {job['status']}")
            if (
                job.get("progress_done") is not None
                and job.get("progress_total") is not None
            ):
                typer.echo(f"Progress: {job['progress_done']}/{job['progress_total']}")
            if job.get("result_url"):
                typer.echo(f"Result: {job['result_url']}")
            if job.get("error_message"):
                typer.echo(f"Error: {job['error_message']}")

        if not watch or job["status"] in terminal:
            return

        time.sleep(interval)
        if not as_json:
            typer.echo("")


@app.command("list")
def list_jobs(
    status: Annotated[
        str | None, typer.Option("--status", help="Filter by job status.")
    ] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200)] = 50,
    cursor: Annotated[
        str | None, typer.Option("--cursor", help="Opaque pagination cursor.")
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full API response as JSON.")
    ] = False,
) -> None:
    payload = _client().list_jobs(status=status, limit=limit, cursor=cursor)
    if as_json:
        _emit_json(payload)
        return

    jobs = payload.get("jobs", [])
    if not jobs:
        typer.echo("No jobs found")
        return

    for job in jobs:
        typer.echo(f"{job['id']}\t{job['status']}\t{job['created_at']}")

    if payload.get("next_cursor"):
        typer.echo("")
        typer.echo(f"Next cursor: {payload['next_cursor']}")


@app.command("get-url")
def get_url(
    job_id: str,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full API response as JSON.")
    ] = False,
) -> None:
    payload = _client().get_job_result(job_id)
    if as_json:
        _emit_json(payload)
        return

    typer.echo(payload["result_url"])


@stac_app.command("show")
def stac_show(
    job_id: str,
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full API response as JSON.")
    ] = False,
) -> None:
    payload = _client().get_job_stac(job_id)
    if as_json:
        _emit_json(payload)
        return

    typer.echo(f"Job ID: {payload['job_id']}")
    typer.echo(f"Publish to STAC: {payload['publish_to_stac']}")
    publication = payload.get("publication")
    if not publication:
        typer.echo("Publication: none")
        return

    typer.echo(f"Dataset ID: {publication['dataset_id']}")
    typer.echo(f"Collection: {publication['collection']}")
    typer.echo(f"Item ID: {publication['item_id']}")
    typer.echo(f"Aggregate Type: {publication['aggregate_type']}")
    typer.echo(f"Href: {publication['href']}")
    typer.echo(f"Datanode: {publication['datanode']}")
    typer.echo(f"Patch Applied: {publication['patch_applied']}")
