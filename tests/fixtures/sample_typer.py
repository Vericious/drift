"""Sample Typer CLI app for testing the TyperExtractor.

Uses both Annotated-style and default-style Options and Arguments.
"""
import typer
from typing import Annotated

app = typer.Typer(help="Sample multi-command Typer CLI tool.")


@app.command()
def build(
    name: Annotated[str, typer.Option(help="Project name.")],
    output: Annotated[str, typer.Option("--output", "-o", help="Output directory.")] = "dist",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose output.")] = False,
    strict: Annotated[bool, typer.Option(help="Strict mode.")] = False,
) -> None:
    """Build the project."""
    ...


@app.command()
def scan(
    path: Annotated[str, typer.Argument(help="Path to scan.")],
    format: Annotated[str, typer.Option("--format", "-f", help="Output format.", default="text")] = "text",
    workers: Annotated[int, typer.Option("--workers", "-w", help="Number of workers.", default=4)] = 4,
) -> None:
    """Scan files for issues."""
    ...


@app.command()
def clean(
    path: str = typer.Option(".", help="Path to clean."),
    dry_run: bool = typer.Option(False, help="Dry run mode."),
) -> None:
    """Clean up generated files."""
    ...
