"""khipu CLI entry point."""

from __future__ import annotations

import sys

import typer

from khipu import __version__
from khipu.analyze import analyze_sync as analyze_sessions
from khipu.emit import emit
from khipu.ingest import ingest

app = typer.Typer(
    name="khipu",
    help="Agent trace forensics & workflow crystallization.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"khipu {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """khipu — untangle agent traces into patterns."""


@app.command()
def analyze(
    paths: list[str] = typer.Argument(..., help="Paths to trace files, directories, or '-' for stdin."),
    ingestor: str | None = typer.Option(
        None,
        "--ingestor",
        help="Force a specific ingestor (required when reading from stdin).",
    ),
    emit_format: str = typer.Option(
        "markdown",
        "--emit",
        help="Output format: 'markdown' (default) or 'json'.",
    ),
    no_redact: bool = typer.Option(
        False,
        "--no-redact",
        help="Disable secret redaction (unsafe — secrets will reach the LLM).",
    ),
    backend: str | None = typer.Option(
        None,
        "--backend",
        help="Backend id to use (default: claude_cli).",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Model override passed to the backend.",
    ),
    only: list[str] = typer.Option(
        [],
        "--only",
        help="Run only these analyzer IDs (repeatable). Default: all.",
    ),
) -> None:
    """Analyze agent traces at one or more PATHs and print a report."""
    # --- Ingest ---
    sessions = []
    for path in paths:
        typer.echo(f"Ingesting {path} …", err=True)
        try:
            sessions.extend(ingest(path, ingestor=ingestor))
        except (ValueError, OSError) as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

    if not sessions:
        typer.echo("Error: no sessions found. Check the path and ingestor.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(sessions)} session(s). Running analysis …", err=True)

    # --- Analyze ---
    result = analyze_sessions(
        sessions,
        backend=backend,
        model=model,
        redact=not no_redact,
        analyzers=list(only) if only else None,
    )

    # --- Emit ---
    try:
        output = emit(result, template=emit_format)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(output)
