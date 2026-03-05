"""khipu CLI entry point."""

from __future__ import annotations

import typer

from khipu import __version__

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
    path: str = typer.Argument(..., help="Path to trace file or directory."),
) -> None:
    """Analyze agent traces at PATH."""
    typer.echo(f"analyze: {path} (not yet implemented)")
