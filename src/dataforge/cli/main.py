from __future__ import annotations

import json
import time
from typing import Annotated, Any

import typer

from dataforge.client.api import DataForgeClient

app = typer.Typer(add_completion=False, no_args_is_help=True)


def _client() -> DataForgeClient:
    return DataForgeClient()


def _emit_json(payload: Any) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


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
    as_json: Annotated[
        bool, typer.Option("--json", help="Print the full API response as JSON.")
    ] = False,
) -> None:
    payload: dict[str, Any] = {
        "input_files": input_files,
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
