"""Tests for diff-style output (--diff-output flag)."""

from pathlib import Path

import pytest

from drift.models import ClaimKind, CodeFact, DocClaim, DriftItem, DriftReport, FactKind, Parameter, Severity
from drift.reporter import DriftReporter


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
    docstring: str | None = None,
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
        docstring=docstring,
    )

    return DriftItem(
        fact=fact,
        claim=claim,
        severity=Severity.ERROR,
        category=category,
        message=message,
        suggestion=suggestion,
    )


class TestDiffOutputMissing:
    """Test diff output for documented_but_missing items."""

    def test_diff_output_missing(self):
        """Shows doc claim vs empty (not found in code)."""
        item = make_drift_item(
            category="documented_but_missing",
            claim_name="old_func",
            fact_name="old_func",
            message="old_func is documented but not found in code",
            suggestion="Add the implementation or remove from docs",
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        # Should have unified diff format
        assert "---" in diff_output
        assert "+++" in diff_output
        assert "@@" in diff_output
        assert "documented_but_missing" in diff_output
        assert "old_func" in diff_output


class TestDiffOutputRenamed:
    """Test diff output for fuzzy_renamed items."""

    def test_diff_output_renamed(self):
        """Shows old name vs new name."""
        item = make_drift_item(
            category="fuzzy_renamed",
            claim_name="old_name",
            fact_name="new_name",
            message="'old_name' may have been renamed to 'new_name'",
            suggestion="Update docs to reference 'new_name'",
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        assert "---" in diff_output
        assert "+++" in diff_output
        assert "old_name" in diff_output
        assert "new_name" in diff_output
        assert "fuzzy_renamed" in diff_output


class TestDiffOutputUndocumented:
    """Test diff output for undocumented items."""

    def test_diff_output_undocumented(self):
        """Shows suggested doc snippet to add."""
        item = make_drift_item(
            category="undocumented",
            claim_name="helper_func",
            fact_name="helper_func",
            code_params=[{"name": "a", "type_annotation": "str", "default": None, "kind": "positional"}],
            message="'helper_func' exists in code but is not documented",
            suggestion="Add documentation for helper_func",
            doc_file="docs",
        )
        # Override: for undocumented, fact exists but no claim
        item2 = DriftItem(
            fact=CodeFact(
                name="helper_func",
                kind=FactKind.FUNCTION,
                source_file=Path("src/helper.py"),
                line_number=3,
                parameters=[Parameter(name="a", type_annotation="str", default=None, kind="positional")],
            ),
            claim=None,  # No claim = undocumented
            severity=Severity.WARNING,
            category="undocumented",
            message="'helper_func' exists in code but is not documented",
            suggestion="Add documentation for helper_func",
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item2],
        )
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        assert "---" in diff_output
        assert "+++" in diff_output
        assert "undocumented" in diff_output
        assert "helper_func" in diff_output


class TestDiffOutputNoDrift:
    """Test diff output when there's no drift."""

    def test_diff_no_drift(self):
        """No drift items -> helpful message."""
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[],
        )
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        assert "No drift" in diff_output or "no drift" in diff_output.lower()


class TestDiffOutputFormat:
    """Test unified diff format structure."""

    def test_has_required_headers(self):
        """Each drift item shows --- and +++ headers."""
        item = make_drift_item(
            category="documented_but_missing",
            claim_name="func_a",
            fact_name="func_a",
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        # Should contain unified diff format headers
        assert "---" in diff_output
        assert "+++" in diff_output


class TestAnsiColorOutput:
    """Test ANSI color codes in diff output."""

    def test_ansi_codes_in_terminal_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When color_mode=True, output contains ANSI escape codes."""
        from drift.reporter import DriftReporter
        from drift.models import Severity

        # Mock Console.is_terminal to return True (terminal mode)
        import drift.reporter as reporter_module
        class MockConsole:
            is_terminal = True
        monkeypatch.setattr(reporter_module, "Console", MockConsole)

        item = make_drift_item(
            category="undocumented",
            claim_name="helper_func",
            fact_name="helper_func",
        )
        # Override to have no claim (undocumented)
        from drift.models import CodeFact, DriftItem, FactKind, Parameter
        item2 = DriftItem(
            fact=CodeFact(
                name="helper_func",
                kind=FactKind.FUNCTION,
                source_file=Path("src/helper.py"),
                line_number=3,
                parameters=[Parameter(name="a", type_annotation="str", default=None, kind="positional")],
            ),
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="'helper_func' exists in code but is not documented",
            suggestion="Add documentation for helper_func",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item2])
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff(color_mode=True)

        # ANSI codes should be present
        assert "\033[" in diff_output  # ANSI escape sequence
        # Specific color codes for diff markers
        assert "\033[31m" in diff_output  # red for --- and - lines
        assert "\033[32m" in diff_output  # green for +++ and + lines
        assert "\033[36m" in diff_output  # cyan for @@

    def test_no_ansi_in_pipe_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When color_mode=False, output contains no ANSI escape codes."""
        from drift.reporter import DriftReporter
        import drift.reporter as reporter_module

        # Mock Console.is_terminal to return False (pipe mode)
        class MockConsole:
            is_terminal = False
        monkeypatch.setattr(reporter_module, "Console", MockConsole)

        item = make_drift_item(
            category="undocumented",
            claim_name="helper_func",
            fact_name="helper_func",
        )
        from drift.models import CodeFact, DriftItem, FactKind, Parameter, Severity
        item2 = DriftItem(
            fact=CodeFact(
                name="helper_func",
                kind=FactKind.FUNCTION,
                source_file=Path("src/helper.py"),
                line_number=3,
                parameters=[Parameter(name="a", type_annotation="str", default=None, kind="positional")],
            ),
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="'helper_func' exists in code but is not documented",
            suggestion="Add documentation for helper_func",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item2])
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff(color_mode=False)

        # No ANSI escape sequences in pipe mode
        assert "\033[" not in diff_output
        # Plain text markers should still be present
        assert "---" in diff_output
        assert "+++" in diff_output

    def test_colorize_diff_exact_codes(self) -> None:
        """_colorize_diff applies correct ANSI codes to diff lines."""
        from drift.reporter import DriftReporter
        from drift.models import Severity, DriftReport

        diff_text = (
            "--- docs/api.md\n"
            "+++ code/api.py\n"
            "@@ -1 +1 @@\n"
            "- def old_func():\n"
            "+ def new_func():\n"
            "  unchanged line\n"
        )
        # _colorize_diff is a method on DriftReporter; use a minimal reporter instance
        report = DriftReport(scanned_path=Path("."), drift_items=[])
        reporter = DriftReporter(report)
        colored = reporter._colorize_diff(diff_text)

        # Check ANSI codes are applied correctly
        assert "\033[31m--- docs/api.md\033[0m" in colored
        assert "\033[32m+++ code/api.py\033[0m" in colored
        assert "\033[36m@@ -1 +1 @@\033[0m" in colored
        assert "\033[31m- def old_func():\033[0m" in colored
        assert "\033[32m+ def new_func():\033[0m" in colored
        # Unchanged line should not have ANSI codes
        assert "  unchanged line\n" in colored
