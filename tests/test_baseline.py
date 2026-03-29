"""Tests for the baseline functionality."""

import json
import time
from pathlib import Path

import pytest


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temp directory with a .py file and a .md file for testing."""
    # Python file: one documented function, one undocumented
    py_file = tmp_path / "example.py"
    py_file.write_text(
        "def documented_func(x: int, y: str = 'hello') -> bool:\n"
        "    '''Docstring.'''\n"
        "    pass\n"
        "\n"
        "def undocumented_func(a: int, b: int) -> None:\n"
        "    pass\n"
    )

    # Markdown file: one signature matching documented_func, one fake
    md_file = tmp_path / "docs.md"
    md_file.write_text(
        "# API Reference\n"
        "\n"
        "## documented_func\n"
        "\n"
        "```python\n"
        "def documented_func(x: int, y: str = 'hello') -> bool\n"
        "```\n"
        "\n"
        "## fake_function\n"
        "\n"
        "```python\n"
        "def fake_function(a: int, b: int) -> None\n"
        "```\n"
    )

    return tmp_path


from drift.baseline import (
    BASELINE_FILENAME,
    filter_new_drift,
    filter_resolved_drift,
    load_baseline,
    save_baseline,
)
from drift.models import CodeFact, ClaimKind, DocClaim, DriftItem, FactKind, Severity
from drift.scanner import DriftScanner


def make_drift_item(name: str, category: str, severity: Severity = Severity.ERROR) -> DriftItem:
    """Create a DriftItem for testing."""
    fact = CodeFact(
        name=name,
        kind=FactKind.FUNCTION,
        source_file=Path("src/foo.py"),
        line_number=10,
    )
    claim = DocClaim(
        raw_text=f"def {name}()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path("docs/foo.md"),
        line_number=5,
        name=name,
    )
    return DriftItem(
        fact=fact,
        claim=claim,
        severity=severity,
        category=category,
        message=f"{name} has drifted",
    )


def test_baseline_create(tmp_path: Path) -> None:
    """Creates .drift/baseline.json with correct format."""
    # Create a minimal project with some drift
    py_file = tmp_path / "example.py"
    py_file.write_text(
        "def old_func(x: int) -> None:\n"
        "    '''Documented.'''\n"
        "    pass\n"
    )
    md_file = tmp_path / "docs.md"
    md_file.write_text(
        "# API\n\n"
        "## old_func\n\n"
        "```python\n"
        "def old_func(x: int) -> None\n"
        "```\n"
    )

    scanner = DriftScanner(tmp_path)
    report = scanner.scan()

    baseline_path = save_baseline(report, tmp_path)

    assert baseline_path == tmp_path / BASELINE_FILENAME
    assert baseline_path.exists()

    data = json.loads(baseline_path.read_text())
    assert "created_at" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_baseline_scan_filters(temp_project: Path) -> None:
    """Scan with --baseline only shows new items not in baseline."""
    # Create baseline from current state
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    save_baseline(report, temp_project)

    # Verify baseline was saved
    loaded = load_baseline(temp_project)
    assert loaded is not None
    created_at, baseline_items = loaded
    assert len(baseline_items) == len(report.drift_items)

    # Now add a new item to the current report (simulating new drift)
    new_item = make_drift_item("newly_added", "undocumented")
    current_items = list(report.drift_items) + [new_item]

    # Filter against baseline
    filtered = filter_new_drift(current_items, baseline_items)

    # Should only have the new item
    assert len(filtered) == 1
    assert filtered[0].fact.name == "newly_added"


def test_baseline_update(tmp_path: Path) -> None:
    """--update overwrites existing baseline."""
    py_file = tmp_path / "example.py"
    py_file.write_text(
        "def func_a() -> None:\n"
        "    '''Doc.'''\n"
        "    pass\n"
    )
    md_file = tmp_path / "docs.md"
    md_file.write_text(
        "# API\n\n"
        "## func_a\n\n"
        "```python\n"
        "def func_a()\n"
        "```\n"
    )

    scanner = DriftScanner(tmp_path)
    report = scanner.scan()
    save_baseline(report, tmp_path)

    baseline_path = tmp_path / BASELINE_FILENAME
    first_mtime = baseline_path.stat().st_mtime

    # Wait a tiny bit so mtime differs
    time.sleep(0.01)

    # Update baseline
    save_baseline(report, tmp_path)

    assert baseline_path.exists()
    assert baseline_path.stat().st_mtime >= first_mtime


def test_no_baseline_scan_shows_all(temp_project: Path) -> None:
    """Without a baseline, scan shows all items (filtering is a no-op when no baseline exists)."""
    # Ensure no baseline exists
    baseline_path = temp_project / BASELINE_FILENAME
    if baseline_path.exists():
        baseline_path.unlink()

    loaded = load_baseline(temp_project)
    assert loaded is None


def test_filter_new_drift_removes_baseline_items(temp_project: Path) -> None:
    """Items that exist in baseline are filtered out."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    baseline_items_data = [
        {
            "fact": item.fact.to_dict() if item.fact else None,
            "claim": item.claim.to_dict() if item.claim else None,
            "severity": item.severity.value,
            "category": item.category,
            "message": item.message,
            "suggestion": None,
            "metadata": {},
        }
        for item in report.drift_items
    ]

    # Filter the same items against themselves (all should be removed)
    filtered = filter_new_drift(report.drift_items, baseline_items_data)
    assert len(filtered) == 0


def test_filter_new_drift_keeps_non_baseline_items(temp_project: Path) -> None:
    """Items NOT in baseline are kept."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    baseline_items_data = [
        {
            "fact": item.fact.to_dict() if item.fact else None,
            "claim": item.claim.to_dict() if item.claim else None,
            "severity": item.severity.value,
            "category": item.category,
            "message": item.message,
            "suggestion": None,
            "metadata": {},
        }
        for item in report.drift_items[:1]  # Only baseline the first item
    ]

    # Filter — should keep all items except the first one
    filtered = filter_new_drift(report.drift_items, baseline_items_data)
    assert len(filtered) == len(report.drift_items) - 1


def test_resolved_items_detected(temp_project: Path) -> None:
    """Baseline items not in current scan are returned as resolved."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    assert len(report.drift_items) >= 1, "need at least one drift item"

    baseline_items_data = [
        {
            "fact": item.fact.to_dict() if item.fact else None,
            "claim": item.claim.to_dict() if item.claim else None,
            "severity": item.severity.value,
            "category": item.category,
            "message": item.message,
            "suggestion": None,
            "metadata": {},
        }
        for item in report.drift_items
    ]

    # Current scan has no items — all baseline items are "resolved"
    resolved = filter_resolved_drift([], baseline_items_data)
    assert len(resolved) == len(baseline_items_data)


def test_unchanged_items_excluded(temp_project: Path) -> None:
    """Baseline items also present in current scan are NOT returned."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    assert len(report.drift_items) >= 1

    baseline_items_data = [
        {
            "fact": item.fact.to_dict() if item.fact else None,
            "claim": item.claim.to_dict() if item.claim else None,
            "severity": item.severity.value,
            "category": item.category,
            "message": item.message,
            "suggestion": None,
            "metadata": {},
        }
        for item in report.drift_items
    ]

    # Current scan matches baseline exactly — nothing is resolved
    resolved = filter_resolved_drift(report.drift_items, baseline_items_data)
    assert len(resolved) == 0


def test_empty_baseline_returns_empty(temp_project: Path) -> None:
    """With no baseline items, resolved list is always empty."""
    resolved = filter_resolved_drift([], [])
    assert resolved == []

    # Even with current items, empty baseline returns nothing
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    resolved = filter_resolved_drift(list(report.drift_items), [])
    assert resolved == []


# --- Baseline diff tests (DRIFT-146) ---


def test_baseline_diff_new_items(temp_project: Path) -> None:
    """filter_new_drift returns only items NOT in baseline (new drift)."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    save_baseline(report, temp_project)

    loaded = load_baseline(temp_project)
    assert loaded is not None
    created_at, baseline_items = loaded

    # Add a new drift item to current scan
    new_item = make_drift_item("brand_new_func", "undocumented")
    current_items = list(report.drift_items) + [new_item]

    # Diff should show only the new item
    diff_new = filter_new_drift(current_items, baseline_items)
    assert len(diff_new) == 1
    assert diff_new[0].fact.name == "brand_new_func"


def test_baseline_diff_resolved_items(temp_project: Path) -> None:
    """filter_resolved_drift returns baseline items NOT in current scan (resolved)."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    assert len(report.drift_items) >= 1

    baseline_items_data = [
        {
            "fact": item.fact.to_dict() if item.fact else None,
            "claim": item.claim.to_dict() if item.claim else None,
            "severity": item.severity.value,
            "category": item.category,
            "message": item.message,
            "suggestion": None,
            "metadata": {},
        }
        for item in report.drift_items
    ]

    # Current scan is empty — all baseline items are "resolved"
    resolved = filter_resolved_drift([], baseline_items_data)
    assert len(resolved) == len(baseline_items_data)
    assert resolved[0].get("fact", {}).get("name") == report.drift_items[0].fact.name


def test_baseline_diff_unchanged(temp_project: Path) -> None:
    """Items in both baseline and current scan are "unchanged" (not in new or resolved)."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    assert len(report.drift_items) >= 1

    baseline_items_data = [
        {
            "fact": item.fact.to_dict() if item.fact else None,
            "claim": item.claim.to_dict() if item.claim else None,
            "severity": item.severity.value,
            "category": item.category,
            "message": item.message,
            "suggestion": None,
            "metadata": {},
        }
        for item in report.drift_items
    ]

    # Current scan exactly matches baseline
    new_items = filter_new_drift(report.drift_items, baseline_items_data)
    resolved_items = filter_resolved_drift(report.drift_items, baseline_items_data)

    # Nothing is new or resolved — everything is unchanged
    assert len(new_items) == 0
    assert len(resolved_items) == 0


def test_baseline_diff_json_output(temp_project: Path, capsys) -> None:
    """drift baseline-diff --json outputs correct JSON structure."""
    from click.testing import CliRunner
    from drift.cli import main

    # Create baseline
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    save_baseline(report, temp_project)

    runner = CliRunner()
    result = runner.invoke(main, ["baseline-diff", "--json", str(temp_project)])
    assert result.exit_code == 0, result.output

    data = json.loads(result.output)
    assert "baseline_created_at" in data
    assert "new" in data
    assert "resolved" in data
    assert "unchanged" in data
    assert "summary" in data
    assert "new_count" in data["summary"]
    assert "resolved_count" in data["summary"]
    assert "unchanged_count" in data["summary"]


def test_baseline_diff_empty_message(temp_project: Path, capsys) -> None:
    """drift baseline-diff shows correct counts when nothing changed."""
    from click.testing import CliRunner
    from drift.cli import main

    # Create baseline and scan (identical state — nothing changed)
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    save_baseline(report, temp_project)

    runner = CliRunner()
    result = runner.invoke(main, ["baseline-diff", str(temp_project)])
    assert result.exit_code == 0, result.output
    assert "+ 0 new drift item(s)" in result.output
    assert "- 0 resolved drift item(s)" in result.output


# --- Update baseline tests (DRIFT-147) ---


def test_update_baseline_requires_baseline_flag(temp_project: Path) -> None:
    """--update-baseline without --baseline exits with error."""
    from click.testing import CliRunner
    from drift.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--update-baseline", str(temp_project)])
    assert result.exit_code != 0
    assert "--update-baseline requires --baseline" in result.output


def test_update_baseline_saves_file(temp_project: Path) -> None:
    """--baseline --update-baseline saves new baseline after filtering."""
    from click.testing import CliRunner
    from drift.cli import main

    # Create initial baseline
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    save_baseline(report, temp_project)

    baseline_path = temp_project / BASELINE_FILENAME
    first_mtime = baseline_path.stat().st_mtime

    time.sleep(0.01)

    # Run scan with --baseline --update-baseline
    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--baseline", "--update-baseline", str(temp_project)])
    assert result.exit_code == 0, result.output
    assert "Baseline updated:" in result.output
    assert baseline_path.stat().st_mtime >= first_mtime


def test_update_baseline_prints_item_count(temp_project: Path) -> None:
    """--baseline --update-baseline prints item count in output."""
    from click.testing import CliRunner
    from drift.cli import main

    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    save_baseline(report, temp_project)

    runner = CliRunner()
    result = runner.invoke(main, ["scan", "--baseline", "--update-baseline", str(temp_project)])
    assert result.exit_code == 0
    assert "Baseline updated:" in result.output
    assert "items" in result.output.lower()


# --- Age warning tests (DRIFT-148) ---


def test_age_warning_triggered(temp_project: Path, capsys) -> None:
    """Warning is printed to stderr when baseline is older than 30 days."""
    import sys
    from datetime import datetime, timedelta, timezone

    # Create a baseline file with an old timestamp
    old_date = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    baseline_path = temp_project / BASELINE_FILENAME
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps({
        "created_at": old_date,
        "items": [],
    }))

    # Load baseline — should trigger warning
    result = load_baseline(temp_project)
    assert result is not None

    captured = capsys.readouterr()
    assert "⚠ Baseline is 31 days old" in captured.err


def test_age_no_warning(temp_project: Path, capsys) -> None:
    """No warning is printed when baseline is younger than 30 days."""
    from datetime import datetime, timedelta, timezone

    # Create a baseline file with a recent timestamp
    recent_date = (datetime.now(timezone.utc) - timedelta(days=29)).isoformat()
    baseline_path = temp_project / BASELINE_FILENAME
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps({
        "created_at": recent_date,
        "items": [],
    }))

    # Load baseline — should NOT trigger warning
    result = load_baseline(temp_project)
    assert result is not None

    captured = capsys.readouterr()
    assert "days old" not in captured.err


def test_age_warning_exact_message_format(temp_project: Path, capsys) -> None:
    """Age warning message matches the expected format exactly."""
    import sys
    from datetime import datetime, timedelta, timezone

    old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    baseline_path = temp_project / BASELINE_FILENAME
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps({
        "created_at": old_date,
        "items": [],
    }))

    result = load_baseline(temp_project)
    assert result is not None

    captured = capsys.readouterr()
    assert "⚠ Baseline is 45 days old (created " in captured.err
    assert "). Consider running drift baseline --update" in captured.err
