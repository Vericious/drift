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
@click.option("--severity", "-s", type=click.Choice(["error", "warning", "info", "all"]),
              default="all", help="Minimum severity to show (default: all).")
@click.option("--verbose", "-V", is_flag=True, help="Show detailed output including scan timing.")
def scan(path: str, output_json: bool, config_path: str | None, strict: bool, severity: str, verbose: bool) -> None:
    """Scan a project for documentation drift."""
    import time
    start = time.monotonic()

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

    elapsed = time.monotonic() - start

    # Apply severity filter
    if severity != "all":
        severity_min = severity
        report.drift_items = _filter_by_severity(report.drift_items, severity_min)

    reporter = DriftReporter(report, verbose=verbose)
    if output_format == "json":
        click.echo(reporter.report_json(verbose=verbose, elapsed=elapsed))
    else:
        reporter.report_console(verbose=verbose, elapsed=elapsed)

    # Exit 1 if drift detected (error-severity items passing the filter)
    if any(item.severity.value == "error" for item in report.drift_items):
        raise SystemExit(1)


def _filter_by_severity(items: list, min_severity: str) -> list:
    """Filter drift items to only those >= min_severity.

    Ordering: error > warning > info
    """
    order = {"error": 0, "warning": 1, "info": 2}
    min_level = order.get(min_severity, 2)
    return [item for item in items if order.get(item.severity.value, 3) <= min_level]
