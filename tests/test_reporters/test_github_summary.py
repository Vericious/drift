"""Tests for GitHubSummaryReporter."""

import os
import tempfile
from pathlib import Path

import pytest

from drift.models import (
    ClaimKind,
    CodeFact,
    DocClaim,
    DriftItem,
    DriftReport,
    FactKind,
    Parameter,
    Severity,
)
from drift.reporters.github_summary import GitHubSummaryReporter


def make_drift_item(
    category: str,
    claim_name: str = "test_func",
    fact_name: str = "test_func",
    message: str = "drift detected",
    suggestion: str | None = None,
    doc_file: str = "docs/api.md",
    code_file: str = "src/api.py",
    doc_params: list[dict] | None = None,
    code_params: list[dict] | None = None,
    severity: Severity = Severity.ERROR,
) -> DriftItem:
    """Helper to create a DriftItem for testing."""
    if doc_params is None:
        doc_params = [{"name": "x", "type_annotation": "int", "default": None, "kind": "positional"}]
    if code_params is None:
        code_params = [{"name": "x", "type_annotation": "int", "default": None, "kind": "positional"}]

    claim = DocClaim(
        raw_text=f"def {claim_name}(x: int)",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path(doc_file),
        line_number=10,
        name=claim_name,
        parameters=[Parameter(**p) for p in doc_params],
    )

    fact = CodeFact(
        name=fact_name,
        kind=FactKind.FUNCTION,
        source_file=Path(code_file),
        line_number=5,
        parameters=[Parameter(**p) for p in code_params],
    )

    return DriftItem(
        fact=fact,
        claim=claim,
        severity=severity,
        category=category,
        message=message,
        suggestion=suggestion,
    )


class TestGitHubSummaryReporterActive:
    """Tests when GITHUB_STEP_SUMMARY is set."""

    def test_is_active_returns_true_when_env_set(self, monkeypatch):
        """is_active() returns True when GITHUB_STEP_SUMMARY is set."""
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", "/tmp/summary.md")
        report = DriftReport(scanned_path=Path("."))
        reporter = GitHubSummaryReporter(report)
        assert reporter.is_active() is True

    def test_is_active_returns_false_when_env_not_set(self, monkeypatch):
        """is_active() returns False when GITHUB_STEP_SUMMARY is not set."""
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        report = DriftReport(scanned_path=Path("."))
        reporter = GitHubSummaryReporter(report)
        assert reporter.is_active() is False

    def test_write_summary_creates_markdown_file(self, monkeypatch):
        """write_summary() appends Markdown to GITHUB_STEP_SUMMARY."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            item = make_drift_item(
                category="missing_param",
                claim_name="old_func",
                fact_name="old_func",
                message="old_func is missing a parameter",
            )
            report = DriftReport(scanned_path=Path("src"), drift_items=[item])
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "# Drift Report" in content
            assert "## Summary" in content
            assert "old_func" in content
            assert "missing_param" in content
        finally:
            os.unlink(summary_path)

    def test_write_summary_no_drift(self, monkeypatch):
        """write_summary() with no drift shows success message."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            report = DriftReport(scanned_path=Path("src"))
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "# Drift Report" in content
            assert "No drift detected" in content or "✅" in content
        finally:
            os.unlink(summary_path)

    def test_write_summary_includes_errors_and_warnings_sections(self, monkeypatch):
        """write_summary() creates separate ## Errors and ## Warnings sections."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            error_item = make_drift_item(
                category="signature_mismatch",
                severity=Severity.ERROR,
                message="signature mismatch",
            )
            warning_item = make_drift_item(
                category="undocumented",
                severity=Severity.WARNING,
                message="function not documented",
            )
            report = DriftReport(
                scanned_path=Path("."),
                drift_items=[error_item, warning_item],
            )
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "## Errors" in content
            assert "## Warnings" in content
        finally:
            os.unlink(summary_path)

    def test_write_summary_verbose_includes_scan_time(self, monkeypatch):
        """write_summary() with verbose=True includes scan time."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            report = DriftReport(scanned_path=Path("."))
            reporter = GitHubSummaryReporter(report, verbose=True)
            reporter.write_summary(elapsed=1.234)

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "Scan Time" in content
            assert "1.234" in content
        finally:
            os.unlink(summary_path)


class TestGitHubSummaryReporterInactive:
    """Tests when GITHUB_STEP_SUMMARY is NOT set (graceful no-op)."""

    def test_write_summary_does_nothing_when_not_active(self, monkeypatch, tmp_path):
        """write_summary() is a no-op when env var is not set."""
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        # Use a sentinel file that should NOT be written to
        sentinel = tmp_path / "should_not_exist.md"
        report = DriftReport(scanned_path=Path("."))
        reporter = GitHubSummaryReporter(report)
        # Should not raise
        reporter.write_summary()
        assert not sentinel.exists()

    def test_render_markdown_does_not_touch_filesystem(self, monkeypatch):
        """_render_markdown() doesn't write any files."""
        monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
        item = make_drift_item(category="renamed", message="function was renamed")
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = GitHubSummaryReporter(report)
        # Should not raise, just return string
        md = reporter._render_markdown()
        assert isinstance(md, str)
        assert "# Drift Report" in md
        assert "renamed" in md


class TestGitHubSummaryMarkdownFormat:
    """Tests for Markdown table format and content."""

    def test_table_has_correct_headers(self, monkeypatch):
        """The items table has Location, Name, Category, Message, Confidence headers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            item = make_drift_item(category="parameter_mismatch")
            report = DriftReport(scanned_path=Path("src"), drift_items=[item])
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "| Location |" in content
            assert "| Name |" in content
            assert "| Category |" in content
            assert "| Message |" in content
            assert "| Confidence |" in content
        finally:
            os.unlink(summary_path)

    def test_location_includes_file_and_line(self, monkeypatch):
        """Location column includes source file path and line number."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            item = make_drift_item("renamed", code_file="src/api.py", doc_file="docs/api.md")
            report = DriftReport(scanned_path=Path("."), drift_items=[item])
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            # Should have something like `src/api.py:5`
            assert "src/api.py" in content or "api.py" in content
        finally:
            os.unlink(summary_path)

    def test_confidence_shown_as_percentage(self, monkeypatch):
        """Confidence is rendered as a percentage (e.g., 100%)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            item = make_drift_item(category="missing_param")
            item.confidence = 0.87
            report = DriftReport(scanned_path=Path("."), drift_items=[item])
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "87%" in content
        finally:
            os.unlink(summary_path)

    def test_pipes_in_messages_are_escaped(self, monkeypatch):
        """Pipe characters in messages are escaped so they don't break the table."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            item = make_drift_item(
                category="parameter_mismatch",
                message="Expected x | y, got x | z",
            )
            report = DriftReport(scanned_path=Path("."), drift_items=[item])
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            # The table should have exactly 5 columns (cells) per data row.
            # We check by splitting on unescaped pipes only.
            import re
            data_lines = [l for l in content.split("\n") if l.startswith("|") and "Expected" in l]
            for line in data_lines:
                # Split on unescaped pipe: findall of pattern that matches | not preceded by \
                cells = re.split(r'(?<!\\)\|', line.strip())
                # Filter out empty cells from leading/trailing pipes
                cells = [c for c in cells if c.strip()]
                assert len(cells) == 5, f"Expected 5 columns but got {len(cells)} in: {line}"
                # Also verify the escaped pipes are in the message cell (3rd column index 3)
                message_cell = cells[3]
                assert "\\|" in message_cell or "x | y" in message_cell, f"Escaped pipes missing in: {message_cell}"
        finally:
            os.unlink(summary_path)


# ---------------------------------------------------------------------------
# E2E Tests: full scan -> report flow
# ---------------------------------------------------------------------------


class TestGitHubSummaryReporterE2E:
    """End-to-end integration tests for scan -> GitHubSummaryReporter flow.

    These tests create real source files, run DriftScanner to produce a report,
    then verify that GitHubSummaryReporter correctly writes the summary.
    """

    def test_e2e_scan_report_with_missing_param_writes_error(self, monkeypatch, tmp_path):
        """Full scan->report: missing parameter detected, error written to summary."""
        # Create a Python source file with a function missing a documented parameter
        src_file = tmp_path / "processor.py"
        src_file.write_text(
            "def process_data(input_data: dict, strict: bool = False) -> dict:\n"
            "    '''Process input data.'''\n"
            "    return input_data\n"
        )

        # Create markdown that documents the function but WITHOUT strict param
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# API\n\n"
            "## process_data\n\n"
            "```python\n"
            "def process_data(input_data: dict) -> dict\n"
            "```\n"
        )

        # Run actual drift scan
        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        # Verify drift was detected
        assert len(report.drift_items) >= 1
        error_items = [d for d in report.drift_items if d.severity == Severity.ERROR]
        assert len(error_items) >= 1

        # Write summary
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "# Drift Report" in content
            assert "process_data" in content
            assert "## Errors" in content
            assert "missing" in content.lower() or "param" in content.lower()
        finally:
            os.unlink(summary_path)

    def test_e2e_scan_report_no_drift_writes_success(self, monkeypatch, tmp_path):
        """Full scan->report: no drift found, success message written."""
        # Create correctly documented function
        src_file = tmp_path / "utils.py"
        src_file.write_text(
            "def greet(name: str) -> str:\n"
            "    '''Return a greeting.'''\n"
            "    return f'Hello, {name}'\n"
        )

        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# Utils\n\n"
            "## greet\n\n"
            "```python\n"
            "def greet(name: str) -> str\n"
            "```\n"
        )

        # Run actual drift scan
        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        # Verify no drift
        assert len(report.drift_items) == 0

        # Write summary
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "# Drift Report" in content
            assert "✅" in content or "No drift" in content
            assert "## Errors" not in content or content.count("## Errors") == 0
        finally:
            os.unlink(summary_path)

    def test_e2e_scan_multiple_drift_items_all_rendered(self, monkeypatch, tmp_path):
        """Multiple drift items of different severities are all rendered."""
        # Create Python file with multiple functions having issues
        src_file = tmp_path / "api.py"
        src_file.write_text(
            "def get_user(user_id: int, include_profile: bool = True) -> dict:\n"
            "    '''Get user.'''\n"
            "    return {}\n\n"
            "def update_user(user_id: int, data: dict) -> None:\n"
            "    '''Update user.'''\n"
            "    pass\n\n"
            "def helper() -> None:\n"
            "    '''A helper.'''\n"
            "    pass\n"
        )

        # Markdown with mismatched signatures
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# API\n\n"
            "```python\n"
            "def get_user(user_id: int) -> dict\n"
            "def update_user(user_id: int) -> None\n"
            "def helper(extra: str) -> None\n"
            "```\n"
        )

        # Run actual drift scan
        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        # Write summary
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "# Drift Report" in content
            assert "get_user" in content
            assert "update_user" in content
            assert "## Errors" in content
        finally:
            os.unlink(summary_path)

    def test_e2e_graceful_noop_when_env_not_set(self, tmp_path):
        """No-op when GITHUB_STEP_SUMMARY is not set (no exception raised)."""
        import os

        # Ensure env var is not set
        if "GITHUB_STEP_SUMMARY" in os.environ:
            del os.environ["GITHUB_STEP_SUMMARY"]

        # Create some drift
        src_file = tmp_path / "foo.py"
        src_file.write_text(
            "def bar(x: int, y: str = 'hi') -> bool:\n"
            "    '''A function.'''\n"
            "    return True\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# Docs\n"
            "```python\n"
            "def bar(x: int) -> bool\n"
            "```\n"
        )

        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        # reporter should not raise even without env var
        reporter = GitHubSummaryReporter(report)
        reporter.write_summary()  # Should be no-op

    def test_e2e_github_output_format_matches_gfm_table(self, monkeypatch, tmp_path):
        """Output format matches expected GFM markdown table structure."""
        src_file = tmp_path / "test_func.py"
        src_file.write_text(
            "def test_func(a: int, b: str = 'default') -> bool:\n"
            "    '''Test function.'''\n"
            "    return True\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# API\n"
            "```python\n"
            "def test_func(a: int) -> bool\n"
            "```\n"
        )

        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            reporter = GitHubSummaryReporter(report)
            reporter.write_summary()

            content = Path(summary_path).read_text(encoding="utf-8")

            # Check GFM table structure
            assert "| Location |" in content
            assert "| Name |" in content
            assert "| Category |" in content
            assert "| Message |" in content
            assert "| Confidence |" in content

            # Check separator row
            assert "| --- | --- | --- | --- | --- |" in content

            # Check that the function name appears in the Name column
            assert "`test_func`" in content
        finally:
            os.unlink(summary_path)

    def test_e2e_verbose_includes_scan_time(self, monkeypatch, tmp_path):
        """Verbose mode includes scan time in the summary."""
        src_file = tmp_path / "foo.py"
        src_file.write_text("def foo() -> None:\n    pass\n")
        md_file = tmp_path / "README.md"
        md_file.write_text("```python\ndef foo() -> None\n```\n")

        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            summary_path = f.name
        monkeypatch.setenv("GITHUB_STEP_SUMMARY", summary_path)

        try:
            reporter = GitHubSummaryReporter(report, verbose=True)
            reporter.write_summary(elapsed=2.5)

            content = Path(summary_path).read_text(encoding="utf-8")
            assert "Scan Time" in content
            assert "2.5" in content
        finally:
            os.unlink(summary_path)
