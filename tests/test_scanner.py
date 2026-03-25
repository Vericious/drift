"""Tests for the DriftScanner orchestrator."""
import tempfile
from pathlib import Path

import pytest

from drift.models import DriftReport
from drift.scanner import DriftScanner


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


def test_scan_returns_driftreport(temp_project: Path) -> None:
    """scan() on a directory returns a DriftReport."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    assert isinstance(report, DriftReport)


def test_scan_file_path_returns_driftreport(temp_project: Path) -> None:
    """scan() on a file path also returns a DriftReport."""
    scanner = DriftScanner(temp_project / "example.py")
    report = scanner.scan()
    assert isinstance(report, DriftReport)


def test_facts_extracted_from_python_file(temp_project: Path) -> None:
    """Facts are extracted from the Python file."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    fact_names = {f.name for f in report.facts}
    assert "documented_func" in fact_names
    assert "undocumented_func" in fact_names
    assert len(report.facts) == 2


def test_claims_extracted_from_markdown_file(temp_project: Path) -> None:
    """Claims are extracted from the Markdown file."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    claim_names = {c.name for c in report.claims if c.name is not None}
    assert "documented_func" in claim_names
    assert "fake_function" in claim_names


def test_drift_items_detected(temp_project: Path) -> None:
    """Drift items are detected for the fake function (renamed match)."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    categories = {item.category for item in report.drift_items}

    # fake_function is documented but not in code — the renamed matcher
    # finds undocumented_func has same params and marks it as "renamed"
    assert "renamed" in categories
    # At least 1 drift item should exist
    assert len(report.drift_items) >= 1


def test_has_drift_true_when_drift_exists(temp_project: Path) -> None:
    """has_drift is True when drift (error-severity items) exists."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    # fake_function creates an error-severity "documented_but_missing" item
    assert report.has_drift is True


def test_scanner_empty_dir() -> None:
    """Scanner handles an empty directory gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        scanner = DriftScanner(Path(tmp))
        report = scanner.scan()
        assert isinstance(report, DriftReport)
        assert report.has_drift is False
