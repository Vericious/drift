"""CLI interface for Drift."""

from pathlib import Path

import click

from drift import __version__
from drift.baseline import filter_new_drift, load_baseline, save_baseline
from drift.config import load_config
from drift.git_utils import get_changed_files, get_changed_lines, get_merge_base, is_git_repo, ref_exists
from drift.models import CodeFact, DocClaim, DriftItem, DriftReport
from drift.reporter import DriftReporter
from drift.scanner import DriftScanner


@click.group()
@click.version_option(version=__version__, prog_name="drift")
def main() -> None:
    """Detect when your documentation no longer matches your code."""
    pass


@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON (mutually exclusive with --sarif and --html)",
)
@click.option(
    "--sarif",
    "output_sarif",
    is_flag=True,
    help="Output as SARIF v2.1.0 JSON (mutually exclusive with --json and --html)",
)
@click.option(
    "--html",
    "output_html",
    is_flag=True,
    help="Output as self-contained HTML (mutually exclusive with --json and --sarif)",
)
@click.option(
    "--diff-output",
    "output_diff",
    is_flag=True,
    help="Output diff-style unified diff showing exact changes needed (mutually exclusive with --json, --sarif, --html, --patch)",
)
@click.option(
    "--patch",
    "output_patch",
    is_flag=True,
    help="Output git-compatible unified patches for fixable categories (wrong_default, wrong_type, wrong_return_type, documented_but_missing). Non-fixable categories are skipped with a comment. (mutually exclusive with --json, --sarif, --html, --diff-output)",
)
@click.option(
    "--output",
    "-o",
    "output_file",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write report to file (in addition to console)",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to config file (default: .drift.toml in CWD)",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Treat extractor errors as fatal (fail fast on malformed files).",
)
@click.option(
    "--severity",
    "-s",
    type=click.Choice(["error", "warning", "info", "all"]),
    default="all",
    help="Minimum severity to show (default: all).",
)
@click.option(
    "--verbose", "-V", is_flag=True, help="Show detailed output including scan timing."
)
@click.option(
    "--fail-on",
    type=str,
    default=None,
    help="Comma-separated category names that trigger non-zero exit. "
    "Categories: undocumented, missing_param, renamed, fuzzy_renamed, "
    "wrong_default, wrong_type, wrong_return_type, documented_but_missing, "
    "extra_param, signature_mismatch. "
    "Special: 'all' (any drift), 'none' (always exit 0). "
    "Legacy severity keywords (backward compat): 'error', 'warning', 'info'. "
    "Default: uses config value (config default: error).",
)
@click.option(
    "--min-confidence",
    type=float,
    default=None,
    help="Only show drift items with confidence >= this value (0.0-1.0).",
)
@click.option(
    "--parallel",
    "-p",
    "parallel",
    is_flag=True,
    help="Enable parallel file processing (uses ThreadPoolExecutor).",
)
@click.option(
    "--include-js",
    is_flag=True,
    help="Scan .js/.ts files for JSDoc documentation claims.",
)
@click.option(
    "--no-cache",
    is_flag=True,
    help="Disable incremental scan cache. All files are re-scanned.",
)
@click.option(
    "--clear-cache",
    is_flag=True,
    help="Clear the incremental scan cache before scanning.",
)
@click.option(
    "--baseline",
    is_flag=True,
    help="Filter results against .drift/baseline.json — only show NEW drift items.",
)
@click.option(
    "--update-baseline",
    is_flag=True,
    help="After filtering with --baseline, save the current scan as the new baseline.",
)
@click.option(
    "--diff",
    "diff_ref",
    type=str,
    default=None,
    help="Scan only files changed vs a git ref (e.g., 'main', 'HEAD~3').",
)
@click.option(
    "--diff-branch",
    "diff_branch",
    type=str,
    default=None,
    help="Scan files changed vs a branch's merge-base with HEAD (e.g., 'main').",
)
@click.option(
    "--extractor",
    "extractors",
    multiple=True,
    help="Run only the specified extractor(s). Can be passed multiple times. Overrides config.",
)
@click.option(
    "--watch",
    is_flag=True,
    help="Watch for file changes and re-run scan automatically. Ctrl+C to exit.",
)
def scan(
    paths: tuple[str, ...],
    output_json: bool,
    output_sarif: bool,
    output_html: bool,
    output_diff: bool,
    output_patch: bool,
    output_file: str | None,
    config_path: str | None,
    strict: bool,
    severity: str,
    verbose: bool,
    fail_on: str | None,
    min_confidence: float | None,
    parallel: bool,
    include_js: bool,
    no_cache: bool,
    clear_cache: bool,
    baseline: bool,
    update_baseline: bool,
    diff_ref: str | None,
    diff_branch: str | None,
    extractors: tuple[str, ...],
    watch: bool,
) -> None:
    """Scan one or more paths for documentation drift."""
    import time

    # Default to current directory if no paths given
    if not paths:
        paths = (".")

    start = time.monotonic()

    # Load config
    config_file = Path(config_path) if config_path else None
    try:
        config = load_config(config_file)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    # CLI --json, --sarif, --html, or --diff-output flag overrides config
    # These flags are mutually exclusive
    flag_count = sum(1 for f in [output_json, output_sarif, output_html, output_diff, output_patch] if f)
    if flag_count > 1:
        raise click.ClickException(
            "--json, --sarif, --html, --diff-output, and --patch cannot be used together."
        )
    if output_json:
        output_format = "json"
    elif output_sarif:
        output_format = "sarif"
    elif output_html:
        output_format = "html"
    elif output_diff:
        output_format = "diff"
    elif output_patch:
        output_format = "patch"
    else:
        output_format = config.output_format

    # CLI --fail-on overrides config
    fail_on_level = fail_on if fail_on is not None else config.fail_on

    # Watch mode: poll for file changes and re-run continuously
    if watch:
        import time
        if not paths:
            paths = (".")
        scan_path = Path(paths[0])
        click.secho("Watching for changes... (Ctrl+C to exit)", fg="cyan", err=True)
        last_mtimes: dict[Path, float] = {}
        while True:
            try:
                watch_files = _get_watch_files(scan_path)
                current_mtimes = _file_mtimes(watch_files)
                if current_mtimes != last_mtimes:
                    last_mtimes = current_mtimes
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    click.echo(f"\n--- Scan at {timestamp} ---")
                    _run_watch_scan(
                        scan_path=scan_path,
                        output_json=output_json,
                        output_sarif=output_sarif,
                        output_html=output_html,
                        output_diff=output_diff,
                        output_patch=output_patch,
                        output_file=output_file,
                        config_path=config_path,
                        strict=strict,
                        severity=severity,
                        verbose=verbose,
                        fail_on=fail_on,
                        min_confidence=min_confidence,
                        parallel=parallel,
                        include_js=include_js,
                        no_cache=no_cache,
                        clear_cache=clear_cache,
                        baseline=baseline,
                        diff_ref=diff_ref,
                        extractors=extractors,
                    )
                time.sleep(2)
            except KeyboardInterrupt:
                click.echo("\nStopped watching.")
                break
        return

    # Scan each path and merge reports (with optional --diff filtering per path)
    all_reports = []
    for path in paths:
        scan_path = Path(path)

        # Handle --diff flag per path
        changed_files: list[Path] | None = None
        changed_lines: dict[Path, set[int]] | None = None
        diff_ref_to_use: str | None = diff_ref

        # Resolve --diff-branch to merge-base commit
        if diff_branch is not None:
            if is_git_repo(scan_path):
                merge_base = get_merge_base(diff_branch, scan_path)
                if merge_base is None:
                    click.secho(
                        f"ERROR: Could not find merge-base for branch '{diff_branch}'. "
                        f"No common ancestor with HEAD.",
                        fg="red",
                        err=True,
                    )
                    raise click.ClickException(
                        f"Branch '{diff_branch}' has no common ancestor with HEAD."
                    )
                diff_ref_to_use = merge_base
                click.echo(f"Using merge-base {merge_base[:7]} as diff ref for branch '{diff_branch}'")
            else:
                click.secho(
                    f"WARNING: {path} is not in a git repo. --diff-branch flag ignored.",
                    fg="yellow",
                    err=True,
                )

        if diff_ref_to_use is not None:
            if is_git_repo(scan_path):
                if not ref_exists(diff_ref_to_use, scan_path):
                    click.secho(
                        f"WARNING: git ref '{diff_ref_to_use}' not found. Running full scan for {path}.",
                        fg="yellow",
                        err=True,
                    )
                else:
                    changed_files = get_changed_files(diff_ref_to_use, scan_path)
                    changed_lines = get_changed_lines(diff_ref_to_use, scan_path)
                    if changed_files is None:
                        click.secho(
                            f"WARNING: Could not get changed files for ref '{diff_ref_to_use}'. "
                            f"Running full scan for {path}.",
                            fg="yellow",
                            err=True,
                        )
                    else:
                        click.echo(f"Scanning {len(changed_files)} file(s) changed vs {diff_ref_to_use} in {path}")
            else:
                click.secho(
                    f"WARNING: {path} is not in a git repo. --diff flag ignored, running full scan.",
                    fg="yellow",
                    err=True,
                )

        # Per-extractor config: --extractor CLI flag overrides config file
        if extractors:
            extractors_enabled = list(extractors)
            extractors_disabled: list[str] | None = None
        else:
            extractors_enabled = config.extractors_enabled
            extractors_disabled = config.extractors_disabled if config.extractors_disabled else None

        scanner = DriftScanner(
            scan_path,
            strict=strict,
            parallel=parallel,
            include_js=include_js,
            no_cache=no_cache,
            clear_cache=clear_cache,
            changed_files=changed_files,
            changed_lines=changed_lines,
            extractors_enabled=extractors_enabled,
            extractors_disabled=extractors_disabled,
            ignore_patterns=config.ignore_patterns,
        )
        report = scanner.scan()
        all_reports.append(report)

    # Merge reports
    report = _merge_reports(all_reports)

    # Filter against baseline if --baseline is set
    baseline_info: str | None = None
    if baseline:
        loaded = load_baseline(Path(paths[0]))
        if loaded is None:
            raise click.ClickException(
                "No baseline found. Run 'drift baseline' first to create one."
            )
        created_at, baseline_items = loaded
        original_count = len(report.drift_items)
        report.drift_items = filter_new_drift(report.drift_items, baseline_items)
        baseline_info = f" (filtered: {len(report.drift_items)} new / {original_count} total vs baseline from {created_at[:10]})"

    # Validate --update-baseline requires --baseline
    if update_baseline and not baseline:
        raise click.ClickException(
            "--update-baseline requires --baseline to be set. "
            "Use 'drift scan --baseline --update-baseline' to update the baseline."
        )

    # Save new baseline if --baseline and --update-baseline are both set
    if baseline and update_baseline:
        new_baseline_path = save_baseline(report, Path(paths[0]))
        click.echo(f"Baseline updated: {len(report.drift_items)} items -> {new_baseline_path}")

    elapsed = time.monotonic() - start

    # Apply severity filter
    if severity != "all":
        severity_min = severity
        report.drift_items = _filter_by_severity(report.drift_items, severity_min)

    # Apply confidence filter
    if min_confidence is not None:
        original_count = len(report.drift_items)
        report.drift_items = [
            item for item in report.drift_items if item.confidence >= min_confidence
        ]
        if verbose and original_count != len(report.drift_items):
            click.echo(
                f"  [dim]Confidence filter:[/dim] "
                f"{len(report.drift_items)}/{original_count} items shown "
                f"(min={min_confidence})"
            )

    reporter = DriftReporter(report, verbose=verbose)

    # Generate output based on format
    if output_format == "json":
        output_content = reporter.report_json(verbose=verbose, elapsed=elapsed)
        click.echo(output_content)
    elif output_format == "sarif":
        output_content = reporter.report_sarif(verbose=verbose, elapsed=elapsed)
        click.echo(output_content)
    elif output_format == "html":
        output_content = reporter.report_html(verbose=verbose, elapsed=elapsed)
        click.echo(output_content)
    elif output_format == "diff":
        output_content = reporter.report_diff(verbose=verbose, elapsed=elapsed)
        click.echo(output_content)
    elif output_format == "patch":
        output_content = reporter.report_patch(verbose=verbose, elapsed=elapsed)
        click.echo(output_content)
    else:
        # For text output, capture to file without Rich formatting
        # Use StringIO to capture plain text with markup interpreted and stripped
        import io

        from rich.console import Console

        text_buffer = io.StringIO()
        # Use default console (markup=True) so Rich interprets markup tags
        # and the output buffer contains plain text without markup
        text_console = Console(file=text_buffer, force_terminal=False)
        # Temporarily swap the reporter's console
        original_console = reporter.console
        reporter.console = text_console
        reporter.report_console(verbose=verbose, elapsed=elapsed)
        reporter.console = original_console
        output_content = text_buffer.getvalue()
        click.echo(output_content)

    # Write to file if --output specified
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_content)

    # Exit based on fail_on categories
    if _should_fail_on_items(report.drift_items, fail_on_level):
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
            f".drift.toml already exists at {config_path}. Use --force to overwrite it."
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

# fail_on: comma-separated category names that trigger non-zero exit code.
# Exit code 1 if any drift item has a category in this list.
# Categories: undocumented, missing_param, renamed, fuzzy_renamed,
#   wrong_default, wrong_type, wrong_return_type, documented_but_missing,
#   extra_param, signature_mismatch.
# Special: "all" (any drift), "none" (always exit 0).
# Legacy severity keywords (backward compat): "error", "warning", "info".
#   "error" = fail on ERROR-severity items (missing_param, renamed, etc.)
# Default: "error" (backward compatible).
fail_on = "error"

# [extractors] — enable/disable specific extractors
# Use 'extractors.enabled' to list which ones to run (["all"] = all enabled)
# Or use 'extractors.disabled' to list which ones to skip
# Example: enabled = ["all"]                     # run all extractors (default)
# Example: enabled = ["flask_routes", "pydantic"]  # only run these
# Example: disabled = ["openapi", "graphql"]    # skip these
[extractors]
# enabled = ["all"]
# disabled = []
"""
    config_path.write_text(default_config)
    click.echo(f"Created {config_path} with sensible defaults.")


@main.command("list-extractors")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to config file (default: .drift.toml in CWD).",
)
def list_extractors(config_path: str | None) -> None:
    """List all loaded extractors (built-in + plugins) with enabled/disabled status.

    Shows every registered Extractor class including those discovered
    via the drift.extractors entry_point group.
    """
    from drift.extractors.registry import get_extractors

    extractors = get_extractors()

    # Load config to get extractor enable/disable list
    config_file = Path(config_path) if config_path else None
    try:
        config = load_config(config_file)
    except (FileNotFoundError, ValueError):
        config = None

    enabled_list = config.extractors_enabled if config else None
    disabled_list = config.extractors_disabled if config else []

    from rich.console import Console
    from rich.table import Table

    console = Console()
    table = Table(title="Drift Extractors", show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Source", style="dim")
    table.add_column("Handles")
    table.add_column("Status", style="bold")

    # Categorize built-in vs plugin
    builtins = {
        "ArgparseExtractor",
        "ClickExtractor",
        "TyperExtractor",
        "ConfigFileExtractor",
        "DataclassFieldsExtractor",
        "DecoratorExtractor",
        "DocstringExtractor",
        "EnvVarExtractor",
        "FastAPIRoutesExtractor",
        "FlaskRoutesExtractor",
        "MarkdownExtractor",
        "PydanticExtractor",
        "RSTDocsExtractor",
        "OpenAPIExtractor",
    }

    for cls in extractors:
        name = cls.__name__
        source = "built-in" if name in builtins else "plugin"
        handles = getattr(cls, "_handles", None) or "*"

        # Determine status
        if disabled_list and name in disabled_list:
            status = "[red]disabled[/red]"
        elif enabled_list is not None and name not in enabled_list:
            status = "[red]disabled[/red]"
        else:
            status = "[green]enabled[/green]"

        table.add_row(name, source, str(getattr(cls, "handles_pattern", handles)), status)

    console.print(table)

    if config and (config.extractors_enabled or config.extractors_disabled):
        console.print(
            f"\n[dim]Loaded from {config_file or '.drift.toml'}: "
            f"enabled={config.extractors_enabled}, disabled={config.extractors_disabled}[/dim]"
        )
    console.print(f"\n[dim]{len(extractors)} extractor(s) loaded[/dim]")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to config file (default: .drift.toml in CWD)",
)
def summary(path: str, output_json: bool, config_path: str | None) -> None:
    """Show a quick health overview of a project's documentation drift."""
    from drift.config import load_config
    from drift.extractors.config_file import ConfigFileExtractor
    from drift.extractors.markdown import MarkdownExtractor
    from drift.extractors.registry import get_extractors

    # Load config
    config_file = Path(config_path) if config_path else None
    try:
        load_config(config_file)
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
            py_extractor = ext()
            break

    if scan_path.is_file():
        py_files = (
            [scan_path] if py_extractor and py_extractor.can_handle(scan_path) else []
        )
        md_files = [scan_path] if md_extractor.can_handle(scan_path) else []
        config_files = [scan_path] if config_extractor.can_handle(scan_path) else []
    else:
        py_files = [
            f
            for f in scan_path.rglob("*.py")
            if not any(
                part
                in {
                    ".git",
                    "__pycache__",
                    ".venv",
                    "node_modules",
                    ".tox",
                    ".pytest_cache",
                    ".mypy_cache",
                }
                for part in f.parts
            )
        ]
        md_files = list(scan_path.rglob("*.md"))
        config_files = (
            list(scan_path.rglob("*.yaml"))
            + list(scan_path.rglob("*.yml"))
            + list(scan_path.rglob("*.toml"))
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
        missing_claim_names: set[tuple[str | None, str]] = set()
        for item in report.drift_items:
            if item.category == "documented_but_missing" and item.claim:
                missing_claim_names.add((item.claim.name, item.claim.kind.value))
        matched_claims = sum(
            1
            for c in report.claims
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
    console.print(
        Panel(
            f"[bold]Drift Summary — {path}[/bold]\n"
            f"[dim]Files scanned: {files_scanned}  |  "
            f"Code facts: {total_facts}  |  "
            f"Doc claims: {total_claims}[/dim]",
            border_style="cyan",
        )
    )

    # Drift status
    if total_drift == 0:
        status_text = Text("✓  No drift detected", style="bold green")
    elif errors > 0:
        status_text = Text(
            f"✗  {total_drift} drift item(s) ({errors} error(s), {warnings} warning(s))",
            style="bold red",
        )
    else:
        status_text = Text(
            f"⚠  {total_drift} drift item(s) ({warnings} warning(s))",
            style="bold yellow",
        )

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

    console.print(
        f"[bold]Health score:[/bold] [bold {score_color}]{health_score}%[/bold {score_color}]"
    )

    if total_claims > 0:
        console.print(
            f"[dim]Matched {matched_claims}/{total_claims} documented items[/dim]"
        )

    console.print()


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--fail-on",
    type=str,
    default="error",
    help="Category or comma-separated categories that trigger exit 1. "
    "Categories: undocumented, missing_param, renamed, fuzzy_renamed, "
    "wrong_default, wrong_type, wrong_return_type, documented_but_missing, "
    "extra_param, signature_mismatch. "
    "Special: 'all', 'none'. Legacy: 'error', 'warning'. "
    "Default: error (backward compatible).",
)
@click.option(
    "--quiet", "-q", is_flag=True, help="Suppress output, only set exit code."
)
def check(path: str, fail_on: str, quiet: bool) -> None:
    """Check a file or path for documentation drift.

    Targeted, fast check useful for pre-commit hooks.
    Returns exit code 0 if no drift, 1 if drift found.

    Examples:

        drift check README.md
        drift check src/
        git diff --name-only | xargs drift check
    """
    import time

    start = time.monotonic()

    scan_path = Path(path)

    # Run scanner
    scanner = DriftScanner(scan_path, strict=False)
    report = scanner.scan()
    elapsed = time.monotonic() - start

    # Determine if we should fail
    should_fail = _should_fail_on_items(report.drift_items, fail_on)

    if not quiet:
        if not should_fail:
            click.secho("✓  No drift", fg="green")
        else:
            # Show brief inline summary
            errors = [d for d in report.drift_items if d.severity.value == "error"]
            warnings = [d for d in report.drift_items if d.severity.value == "warning"]
            if errors:
                click.secho(f"✗  {len(errors)} error(s)", fg="red", err=True)
            if warnings:
                click.secho(f"⚠  {len(warnings)} warning(s)", fg="yellow", err=True)
            click.echo(f"Drift detected in {scan_path} ({elapsed:.2f}s)")

    if should_fail:
        raise SystemExit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--dry-run",
    "-n",
    is_flag=True,
    help="Show what would be fixed without making changes.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=False),
    default=None,
    help="Path to config file (default: .drift.toml in CWD)",
)
def fix(path: str, dry_run: bool, config_path: str | None) -> None:
    """Attempt to auto-fix documentation drift where possible.

    Currently supports:
    - Removing documented parameters that don't exist in code

    Experimental: auto-fix for other extractors may be added in future versions.

    Use --dry-run to see what would be changed without modifying files.
    """
    from drift.config import load_config

    # Load config
    config_file = Path(config_path) if config_path else None
    try:
        load_config(config_file)
    except FileNotFoundError:
        pass  # Use defaults if no config
    except ValueError:
        pass

    scan_path = Path(path)

    # Run scanner
    scanner = DriftScanner(scan_path, strict=False)
    report = scanner.scan()

    if not report.drift_items:
        click.secho("✓  No drift to fix", fg="green")
        return

    # Categorize drift items by whether they can be auto-fixed
    fixable: list[DriftItem] = []
    not_fixable: list[DriftItem] = []

    for item in report.drift_items:
        # Currently only "documented_but_missing" parameter claims are fixable
        # (remove the documentation claim from the docstring)
        if item.category == "documented_but_missing":
            if item.claim and item.claim.kind.value in (
                "parameter_description",
                "return_description",
            ):
                fixable.append(item)
            else:
                not_fixable.append(item)
        else:
            not_fixable.append(item)

    if not fixable:
        click.secho(
            "⚠  No auto-fixable drift found. Try fixing manually.",
            fg="yellow",
        )
        if not_fixable:
            click.echo(f"  ({len(not_fixable)} item(s) cannot be auto-fixed)")
        raise SystemExit(1)

    # Show what would be fixed
    click.echo(f"Found {len(fixable)} fixable drift item(s):")
    for item in fixable:
        claim_name = item.claim.name if item.claim else "unknown"
        claim_kind = item.claim.kind.value if item.claim else "unknown"
        click.echo(f"  - [{claim_kind}] {claim_name} ({item.category})")
        if item.fact and item.fact.source_file:
            click.echo(f"    at {item.fact.source_file}:{item.fact.line_number}")

    if dry_run:
        click.echo()
        click.secho("Dry run - no changes made. Run without --dry-run to apply.", fg="cyan")
        raise SystemExit(1)

    # TODO: Implement actual file modification
    # For now, just report that we'd fix them
    click.echo()
    click.secho(
        "Auto-fix is not yet fully implemented. "
        "Please fix these items manually or wait for a future version.",
        fg="yellow",
    )
    raise SystemExit(1)


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option(
    "--update",
    "-U",
    is_flag=True,
    help="Overwrite the existing baseline file.",
)
def baseline(path: str, update: bool) -> None:
    """Save the current drift state as a baseline snapshot.

    Creates .drift/baseline.json with the current drift items.
    Use 'drift scan --baseline' to compare against this snapshot
    and only report NEW drift items not in the baseline.

    Run again with --update to refresh the baseline.
    """
    from drift.config import load_config

    scan_path = Path(path)

    # Load config (silently ignore if not found)
    try:
        load_config()
    except (FileNotFoundError, ValueError):
        pass

    scanner = DriftScanner(scan_path, strict=False)
    report = scanner.scan()

    baseline_path = save_baseline(report, scan_path)

    if update:
        click.echo(f"Updated baseline: {baseline_path}")
    else:
        click.echo(f"Created baseline: {baseline_path}")
    click.echo(f"  {len(report.drift_items)} drift item(s) snapshot")
    click.echo(f"  Run 'drift scan --baseline' to compare against this snapshot.")


def _filter_by_severity(items: list[DriftItem], min_severity: str) -> list[DriftItem]:
    """Filter drift items to only those >= min_severity.

    Ordering: error > warning > info
    """
    order = {"error": 0, "warning": 1, "info": 2}
    min_level = order.get(min_severity, 2)
    return [item for item in items if order.get(item.severity.value, 3) <= min_level]


def _is_severity_keyword(fail_on: str) -> bool:
    """Return True if fail_on is a legacy severity keyword."""
    return fail_on in ("error", "warning", "info", "none")


def _is_category_name(fail_on: str) -> bool:
    """Return True if fail_on is a known category name."""
    KNOWN_CATEGORIES = {
        "undocumented",
        "missing_param",
        "renamed",
        "fuzzy_renamed",
        "wrong_default",
        "wrong_type",
        "wrong_return_type",
        "documented_but_missing",
        "extra_param",
        "signature_mismatch",
        # aliases
        "missing",
        "signature_changed",
    }
    return fail_on in KNOWN_CATEGORIES


def _expand_fail_on_to_categories(fail_on: str) -> set[str]:
    """Expand a fail_on value to a set of category names.

    For severity keywords (error, warning, info, none): returns None to indicate
    that severity-based logic should be used instead.
    For category names and comma-separated lists: returns the set of categories.
    """
    # Handle comma-separated list
    if "," in fail_on:
        result: set[str] = set()
        for part in fail_on.split(","):
            part = part.strip()
            if part:
                expanded = _expand_fail_on_to_categories(part)
                if expanded is None:
                    # Severity keyword in comma-list - fall back to severity check
                    return None
                result |= expanded
        return result if result else set()

    # Severity keywords: use severity-based logic
    if fail_on == "none":
        return set()  # empty = no categories = never fail
    if fail_on in ("error", "warning", "info"):
        return None  # None = use severity-based logic
    if fail_on == "all":
        return {
            "undocumented",
            "missing_param",
            "renamed",
            "fuzzy_renamed",
            "wrong_default",
            "wrong_type",
            "wrong_return_type",
            "documented_but_missing",
            "extra_param",
            "signature_mismatch",
        }

    # Category aliases
    if fail_on == "missing":
        return {"missing_param"}
    if fail_on == "signature_changed":
        return {"signature_mismatch"}

    # Assume it's a category name
    return {fail_on}


def _should_fail_on_items(items: list[DriftItem], fail_on: str) -> bool:
    """Check if any drift item should trigger non-zero exit based on fail_on.

    For legacy severity keywords (error, warning, info): uses severity comparison.
    For category names (including 'all', 'none', category aliases):
        uses category membership.
    """
    if fail_on == "none":
        return False

    if _is_severity_keyword(fail_on):
        # Legacy severity-based behavior
        return _should_fail_on_severity(items, fail_on)

    # Category-based behavior
    categories = _expand_fail_on_to_categories(fail_on)
    if categories is None:
        # Shouldn't happen, but handle gracefully
        return False
    if not categories:
        return False
    return any(item.category in categories for item in items)


def _should_fail_on_severity(items: list[DriftItem], fail_on: str) -> bool:
    """Check if any drift item reaches the fail_on severity level.

    Ordering: error > warning > info
    Returns True if any item has severity >= fail_on level.
    """
    order = {"error": 0, "warning": 1, "info": 2}
    fail_level = order.get(fail_on, 3)
    return any(order.get(item.severity.value, 3) <= fail_level for item in items)


def _get_watch_files(scan_path: Path) -> list[Path]:
    """Get all watchable files (py, md, rst, toml, yaml) under scan_path."""
    if scan_path.is_file():
        return [scan_path]
    exclude_dirs = {
        ".git",
        "__pycache__",
        ".venv",
        "node_modules",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
    }
    files: list[Path] = []
    for pattern in ["*.py", "*.md", "*.rst", "*.toml", "*.yaml", "*.yml"]:
        for f in scan_path.rglob(pattern):
            if not any(part in exclude_dirs for part in f.parts):
                files.append(f)
    return files


def _file_mtimes(paths: list[Path]) -> dict[Path, float]:
    """Return mtime for each file, or 0 if file doesn't exist."""
    result: dict[Path, float] = {}
    for p in paths:
        try:
            result[p] = p.stat().st_mtime
        except OSError:
            result[p] = 0
    return result


def _run_watch_scan(
    scan_path: Path,
    output_json: bool,
    output_sarif: bool,
    output_html: bool,
    output_diff: bool,
    output_patch: bool,
    output_file: str | None,
    config_path: str | None,
    strict: bool,
    severity: str,
    verbose: bool,
    fail_on: str | None,
    min_confidence: float | None,
    parallel: bool,
    include_js: bool,
    no_cache: bool,
    clear_cache: bool,
    baseline: bool,
    diff_ref: str | None,
    extractors: tuple[str, ...],
) -> None:
    """Run a single scan pass, reusing the core logic from the scan command."""
    import time

    start = time.monotonic()

    config_file = Path(config_path) if config_path else None
    try:
        config = load_config(config_file)
    except FileNotFoundError as e:
        raise click.ClickException(str(e)) from e
    except ValueError as e:
        raise click.ClickException(str(e)) from e

    flag_count = sum(1 for f in [output_json, output_sarif, output_html, output_diff, output_patch] if f)
    if flag_count > 1:
        raise click.ClickException("--json, --sarif, --html, --diff-output, and --patch cannot be used together.")
    if output_json:
        output_format = "json"
    elif output_sarif:
        output_format = "sarif"
    elif output_html:
        output_format = "html"
    elif output_diff:
        output_format = "diff"
    else:
        output_format = config.output_format

    fail_on_level = fail_on if fail_on is not None else config.fail_on

    changed_files: list[Path] | None = None
    if diff_ref is not None:
        if is_git_repo(scan_path):
            if not ref_exists(diff_ref, scan_path):
                click.secho(f"WARNING: git ref '{diff_ref}' not found.", fg="yellow", err=True)
            else:
                changed_files = get_changed_files(diff_ref, scan_path)

    if extractors:
        extractors_enabled = list(extractors)
        extractors_disabled: list[str] | None = None
    else:
        extractors_enabled = config.extractors_enabled
        extractors_disabled = config.extractors_disabled if config.extractors_disabled else None

    scanner = DriftScanner(
        scan_path,
        strict=strict,
        parallel=parallel,
        include_js=include_js,
        no_cache=no_cache,
        clear_cache=clear_cache,
        changed_files=changed_files,
        extractors_enabled=extractors_enabled,
        extractors_disabled=extractors_disabled,
    )
    report = scanner.scan()

    if baseline:
        loaded = load_baseline(scan_path)
        if loaded is None:
            raise click.ClickException("No baseline found. Run 'drift baseline' first.")
        created_at, baseline_items = loaded
        report.drift_items = filter_new_drift(report.drift_items, baseline_items)

    elapsed = time.monotonic() - start

    if severity != "all":
        report.drift_items = _filter_by_severity(report.drift_items, severity)

    if min_confidence is not None:
        report.drift_items = [
            item for item in report.drift_items if item.confidence >= min_confidence
        ]

    reporter = DriftReporter(report, verbose=verbose)

    if output_format == "json":
        output_content = reporter.report_json(verbose=verbose, elapsed=elapsed)
    elif output_format == "sarif":
        output_content = reporter.report_sarif(verbose=verbose, elapsed=elapsed)
    elif output_format == "html":
        output_content = reporter.report_html(verbose=verbose, elapsed=elapsed)
    elif output_format == "diff":
        output_content = reporter.report_diff(verbose=verbose, elapsed=elapsed)
    elif output_format == "patch":
        output_content = reporter.report_patch(verbose=verbose, elapsed=elapsed)
    else:
        import io
        from rich.console import Console
        text_buffer = io.StringIO()
        text_console = Console(file=text_buffer, force_terminal=False)
        original_console = reporter.console
        reporter.console = text_console
        reporter.report_console(verbose=verbose, elapsed=elapsed)
        reporter.console = original_console
        output_content = text_buffer.getvalue()

    click.echo(output_content)

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_content)

    if _should_fail_on_items(report.drift_items, fail_on_level):
        raise SystemExit(1)


def _merge_reports(reports: list[DriftReport]) -> DriftReport:
    """Merge multiple DriftReports into one.

    Facts, claims, and drift_items are concatenated.
    Drift items are deduplicated by (fact.source_file, fact.name, claim.name, category).
    """
    if not reports:
        return DriftReport(scanned_path=Path("."))
    if len(reports) == 1:
        return reports[0]

    # Collect all facts, claims, drift items, and errors
    all_facts: list[CodeFact] = []
    all_claims: list[DocClaim] = []
    raw_drift_items: list[DriftItem] = []
    all_errors: list[str] = []
    total_files_skipped = 0

    for report in reports:
        all_facts.extend(report.facts)
        all_claims.extend(report.claims)
        raw_drift_items.extend(report.drift_items)
        all_errors.extend(report.errors)
        total_files_skipped += report.files_skipped

    # Deduplicate drift items
    seen_items: set[tuple[str, str, str, str]] = set()
    deduped_drift_items: list[DriftItem] = []
    for item in raw_drift_items:
        key = (
            str(item.fact.source_file) if item.fact else "",
            item.fact.name if item.fact else "",
            item.claim.name if item.claim else "",
            item.category,
        )
        if key not in seen_items:
            seen_items.add(key)
            deduped_drift_items.append(item)

    return DriftReport(
        scanned_path=Path("."),
        facts=all_facts,
        claims=all_claims,
        drift_items=deduped_drift_items,
        errors=all_errors,
        files_skipped=total_files_skipped,
    )
