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
@click.option("--json", "output_json", is_flag=True, help="Output as JSON (mutually exclusive with --sarif)")
@click.option("--sarif", "output_sarif", is_flag=True, help="Output as SARIF v2.1.0 JSON (mutually exclusive with --json)")
@click.option("--config", "config_path", type=click.Path(exists=False), default=None,
              help="Path to config file (default: .drift.toml in CWD)")
@click.option("--strict", is_flag=True,
              help="Treat extractor errors as fatal (fail fast on malformed files).")
@click.option("--severity", "-s", type=click.Choice(["error", "warning", "info", "all"]),
              default="all", help="Minimum severity to show (default: all).")
@click.option("--verbose", "-V", is_flag=True, help="Show detailed output including scan timing.")
@click.option("--fail-on", type=click.Choice(["error", "warning", "info", "none"]),
              default=None, help="Exit code 1 on any drift item at or above this severity (overrides config).")
def scan(path: str, output_json: bool, output_sarif: bool, config_path: str | None, strict: bool, severity: str, verbose: bool, fail_on: str | None) -> None:
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

    # CLI --json or --sarif flag overrides config
    # --json and --sarif are mutually exclusive
    if output_json and output_sarif:
        raise click.ClickException("--json and --sarif cannot be used together.")
    if output_json:
        output_format = "json"
    elif output_sarif:
        output_format = "sarif"
    else:
        output_format = config.output_format

    # CLI --fail-on overrides config
    fail_on_level = fail_on if fail_on is not None else config.fail_on

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
    elif output_format == "sarif":
        click.echo(reporter.report_sarif(verbose=verbose, elapsed=elapsed))
    else:
        reporter.report_console(verbose=verbose, elapsed=elapsed)

    # Exit based on fail_on level
    if fail_on_level == "none":
        # Always exit 0
        return
    elif _should_fail_on_severity(report.drift_items, fail_on_level):
        raise SystemExit(1)


@main.command()
@click.option("--force", "-f", is_flag=True, help="Overwrite existing .drift.toml")
def init(force: bool) -> None:
    """Create a .drift.toml configuration file with sensible defaults.

    If .drift.toml already exists, this command will refuse to overwrite it
    unless --force is specified.
    """
    config_path = Path.cwd() / ".drift.toml"
    if config_path.exists() and not force:
        raise click.ClickException(
            f".drift.toml already exists at {config_path}. "
            "Use --force to overwrite it."
        )

    default_config = """# Drift configuration
# https://github.com/your-org/drift

# Patterns to ignore when scanning
ignore_patterns = [
    "*.pyc",
    "__pycache__",
    ".git",
    "node_modules",
    ".venv",
    ".tox",
    ".pytest_cache",
    ".mypy_cache",
]

# threshold: minimum severity to report (0.0 = all, 1.0 = none)
# 0.0 = report all findings
# 0.5 = report warnings and errors only
# 1.0 = report errors only
threshold = 0.0

# output format: "text" or "json"
output_format = "text"

# fail_on: exit code 1 when drift items at this severity or higher are found
# "error" (default) = fail on error-severity items only
# "warning" = fail on warning or error items
# "info" = fail on any drift item
# "none" = always exit 0 (CI info-only mode)
fail_on = "error"
"""
    config_path.write_text(default_config)
    click.echo(f"Created {config_path} with sensible defaults.")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--config", "config_path", type=click.Path(exists=False), default=None,
              help="Path to config file (default: .drift.toml in CWD)")
def summary(path: str, output_json: bool, config_path: str | None) -> None:
    """Show a quick health overview of a project's documentation drift."""
    from drift.config import load_config
    from drift.extractors.registry import get_extractors
    from drift.extractors.markdown import MarkdownExtractor
    from drift.extractors.config_file import ConfigFileExtractor

    # Load config
    config_file = Path(config_path) if config_path else None
    try:
        config = load_config(config_file)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    scan_path = Path(path)

    # Discover files
    py_extractor = None
    md_extractor = MarkdownExtractor()
    config_extractor = ConfigFileExtractor()
    for ext in get_extractors():
        if ext.__class__.__name__ == "PythonExtractor":
            py_extractor = ext
            break

    if scan_path.is_file():
        py_files = [scan_path] if py_extractor and py_extractor.can_handle(scan_path) else []
        md_files = [scan_path] if md_extractor.can_handle(scan_path) else []
        config_files = [scan_path] if config_extractor.can_handle(scan_path) else []
    else:
        py_files = [f for f in scan_path.rglob("*.py")
                    if not any(part in {".git", "__pycache__", ".venv", "node_modules", ".tox", ".pytest_cache", ".mypy_cache"} for part in f.parts)]
        md_files = list(scan_path.rglob("*.md"))
        config_files = (
            list(scan_path.rglob("*.yaml")) +
            list(scan_path.rglob("*.yml")) +
            list(scan_path.rglob("*.toml"))
        )

    files_scanned = len(py_files) + len(md_files) + len(config_files)

    # Run the scanner
    scanner = DriftScanner(scan_path, strict=False)
    report = scanner.scan()

    total_facts = len(report.facts)
    total_claims = len(report.claims)
    total_drift = len(report.drift_items)
    errors = sum(1 for d in report.drift_items if d.severity.value == "error")
    warnings = sum(1 for d in report.drift_items if d.severity.value == "warning")

    # Health score: matched claims / total claims × 100 (no claims = 100%)
    # A claim is "matched" if it does NOT appear in a "documented_but_missing" drift item
    if total_claims > 0:
        # Collect names of claims that are documented-but-missing
        missing_claim_names: set[tuple] = set()
        for item in report.drift_items:
            if item.category == "documented_but_missing" and item.claim:
                missing_claim_names.add((item.claim.name, item.claim.kind.value))
        matched_claims = sum(
            1 for c in report.claims
            if (c.name, c.kind.value) not in missing_claim_names
        )
        health_score = round(matched_claims / total_claims * 100, 1)
    else:
        health_score = 100.0

    if output_json:
        import json
        data = {
            "files_scanned": files_scanned,
            "code_facts": total_facts,
            "doc_claims": total_claims,
            "drift_items": total_drift,
            "errors": errors,
            "warnings": warnings,
            "health_score": health_score,
        }
        click.echo(json.dumps(data, indent=2))
        return

    # Rich formatted output
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    console.print()
    console.print(Panel(
        f"[bold]Drift Summary — {path}[/bold]\n"
        f"[dim]Files scanned: {files_scanned}  |  "
        f"Code facts: {total_facts}  |  "
        f"Doc claims: {total_claims}[/dim]",
        border_style="cyan",
    ))

    # Drift status
    if total_drift == 0:
        status_text = Text("✓  No drift detected", style="bold green")
    elif errors > 0:
        status_text = Text(f"✗  {total_drift} drift item(s) ({errors} error(s), {warnings} warning(s))", style="bold red")
    else:
        status_text = Text(f"⚠  {total_drift} drift item(s) ({warnings} warning(s))", style="bold yellow")

    console.print()
    console.print(status_text)
    console.print()

    # Health score bar
    if health_score >= 80:
        score_color = "green"
    elif health_score >= 50:
        score_color = "yellow"
    else:
        score_color = "red"

    console.print(f"[bold]Health score:[/bold] [bold {score_color}]{health_score}%[/bold {score_color}]")

    if total_claims > 0:
        console.print(f"[dim]Matched {matched_claims}/{total_claims} documented items[/dim]")

    console.print()


def _filter_by_severity(items: list, min_severity: str) -> list:
    """Filter drift items to only those >= min_severity.

    Ordering: error > warning > info
    """
    order = {"error": 0, "warning": 1, "info": 2}
    min_level = order.get(min_severity, 2)
    return [item for item in items if order.get(item.severity.value, 3) <= min_level]


def _should_fail_on_severity(items: list, fail_on: str) -> bool:
    """Check if any drift item reaches the fail_on severity level.

    Ordering: error > warning > info
    Returns True if any item has severity >= fail_on level.
    """
    order = {"error": 0, "warning": 1, "info": 2}
    fail_level = order.get(fail_on, 3)
    return any(order.get(item.severity.value, 3) <= fail_level for item in items)
