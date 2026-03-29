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
    BASELINE_MAX_AGE_DAYS,
    check_baseline_age,
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


def test_age_warning_triggered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Warning is printed when baseline is older than 30 days."""
    from datetime import datetime, timedelta, timezone
    import io
    import sys
    from drift import baseline as baseline_module

    # Mock datetime.now() to return a date 31 days after the baseline
    baseline_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    future_date = baseline_date + timedelta(days=31)

    class MockDatetime(baseline_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return future_date

    monkeypatch.setattr(baseline_module, "datetime", MockDatetime)

    captured_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured_stderr)

    created_at = baseline_date.isoformat()
    check_baseline_age(created_at)

    warning = captured_stderr.getvalue()
    assert "⚠ Baseline is 31 days old (created 2024-01-01)" in warning
    assert "Consider running drift baseline --update" in warning


def test_age_no_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """No warning is printed when baseline is younger than 30 days."""
    from datetime import datetime, timedelta, timezone
    import io
    import sys
    from drift import baseline as baseline_module

    # Mock datetime.now() to return a date 29 days after the baseline
    baseline_date = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    future_date = baseline_date + timedelta(days=29)

    class MockDatetime(baseline_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return future_date

    monkeypatch.setattr(baseline_module, "datetime", MockDatetime)

    captured_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured_stderr)

    created_at = baseline_date.isoformat()
    check_baseline_age(created_at)

    assert captured_stderr.getvalue() == ""


def test_age_warning_exact_message_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Warning message exactly matches the specified format."""
    from datetime import datetime, timedelta, timezone
    import io
    import sys
    from drift import baseline as baseline_module

    baseline_date = datetime(2024, 6, 15, 0, 0, 0, tzinfo=timezone.utc)
    future_date = baseline_date + timedelta(days=45)

    class MockDatetime(baseline_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return future_date

    monkeypatch.setattr(baseline_module, "datetime", MockDatetime)

    captured_stderr = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured_stderr)

    check_baseline_age(baseline_date.isoformat())

    expected = (
        f"⚠ Baseline is 45 days old (created 2024-06-15). "
        f"Consider running drift baseline --update\n"
    )
    assert captured_stderr.getvalue() == expected
