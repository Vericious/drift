"""CLI interface for Drift."""
from pathlib import Path

import click

from drift import __version__
from drift.config import load_config
from drift.scanner import DriftScanner
from drift.reporter import DriftReporter


@click.group()
@click.version_option(version=__version__, prog_name="drift")
def main() -> None:
    """Detect when your documentation no longer matches your code."""
    pass


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--config", "config_path", type=click.Path(exists=False), default=None,
              help="Path to config file (default: .drift.toml in CWD)")
@click.option("--strict", is_flag=True,
              help="Treat extractor errors as fatal (fail fast on malformed files).")
def scan(path: str, output_json: bool, config_path: str | None, strict: bool) -> None:
    """Scan a project for documentation drift."""
    # Load config
    config_file = Path(config_path) if config_path else None
    try:
        config = load_config(config_file)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    # CLI --json flag overrides config
    output_format = "json" if output_json else config.output_format

    scanner = DriftScanner(Path(path), strict=strict)
    report = scanner.scan()
    reporter = DriftReporter(report)
    if output_format == "json":
        click.echo(reporter.report_json())
    else:
        reporter.report_console()
    # Exit 1 if drift detected (error-severity items)
    if report.has_drift:
        raise SystemExit(1)
