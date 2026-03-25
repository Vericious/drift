"""CLI interface for Drift."""
from pathlib import Path

import click

from drift import __version__
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
def scan(path: str, output_json: bool) -> None:
    """Scan a project for documentation drift."""
    scanner = DriftScanner(Path(path))
    report = scanner.scan()
    reporter = DriftReporter(report)
    if output_json:
        click.echo(reporter.report_json())
    else:
        reporter.report_console()
    # Exit 1 if drift detected (error-severity items)
    if report.has_drift:
        raise SystemExit(1)
