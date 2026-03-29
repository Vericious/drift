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


class TestDiffCleanOutput:
    """Test clean diff output without Rich markup."""

    def test_diff_clean_no_markup(self):
        """Diff output should not contain Rich markup tags."""
        item = make_drift_item(
            category="documented_but_missing",
            claim_name="old_func",
            fact_name="old_func",
            message="old_func is documented but not found in code",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        # Rich markup tags should not appear in the actual diff content
        # The headers may have markup but diff lines should be clean
        lines = diff_output.split("\n")
        for line in lines:
            if line.startswith("- ") or line.startswith("+ "):
                assert "[" not in line or "]" not in line, f"Markup found in diff line: {line}"


class TestDiffColorTerminal:
    """Test colored output for terminal display."""

    def test_diff_color_terminal(self):
        """Diff output contains ANSI color codes for terminal."""
        item = make_drift_item(
            category="fuzzy_renamed",
            claim_name="old_name",
            fact_name="new_name",
            message="'old_name' may have been renamed to 'new_name'",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        # Output should contain Rich markup indicating color styling
        assert "[" in diff_output and "]" in diff_output
        # Should still contain the actual content
        assert "old_name" in diff_output
        assert "new_name" in diff_output


class TestDiffPlainPipe:
    """Test plain output for piped usage."""

    def test_diff_plain_pipe(self):
        """Plain diff output should be suitable for piping to other tools."""
        item = make_drift_item(
            category="undocumented",
            claim_name="helper_func",
            fact_name="helper_func",
            code_params=[{"name": "a", "type_annotation": "str", "default": None, "kind": "positional"}],
            message="'helper_func' exists in code but is not documented",
        )
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
        diff_output = reporter.report_diff()

        # Should contain unified diff markers
        assert "---" in diff_output
        assert "+++" in diff_output
        # Should be parseable (not full of markup noise)
        assert "helper_func" in diff_output


class TestDiffPatchWrongDefault:
    """Test diff output for wrong_default parameter category."""

    def test_diff_patch_wrong_default(self):
        """Shows wrong default value in parameter."""
        doc_params = [{"name": "x", "type_annotation": "int", "default": "5", "kind": "positional"}]
        code_params = [{"name": "x", "type_annotation": "int", "default": "10", "kind": "positional"}]
        item = make_drift_item(
            category="wrong_default",
            claim_name="config_value",
            fact_name="config_value",
            doc_params=doc_params,
            code_params=code_params,
            message="'config_value' has wrong default: docs say 5, code has 10",
            suggestion="Update docs to match code default (10)",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        # Should show the mismatch
        assert "---" in diff_output
        assert "+++" in diff_output
        assert "config_value" in diff_output
        assert "wrong_default" in diff_output or "5" in diff_output or "10" in diff_output


class TestDiffMultipleItems:
    """Test diff output with multiple drift items."""

    def test_diff_multiple_items(self):
        """Shows diff for multiple drift items."""
        item1 = make_drift_item(
            category="documented_but_missing",
            claim_name="func_a",
            fact_name="func_a",
            message="func_a is documented but not found",
        )
        item2 = make_drift_item(
            category="undocumented",
            claim_name="func_b",
            fact_name="func_b",
            code_params=[{"name": "b", "type_annotation": "str", "default": None, "kind": "positional"}],
            message="func_b exists in code but is not documented",
            doc_file="docs/api.md",
            code_file="src/api.py",
        )
        item2_drift = DriftItem(
            fact=CodeFact(
                name="func_b",
                kind=FactKind.FUNCTION,
                source_file=Path("src/api.py"),
                line_number=10,
                parameters=[Parameter(name="b", type_annotation="str", default=None, kind="positional")],
            ),
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="func_b exists in code but is not documented",
            suggestion="Add documentation for func_b",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item1, item2_drift])
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        # Should show both items
        assert "func_a" in diff_output
        assert "func_b" in diff_output
        assert diff_output.count("---") >= 2  # At least 2 diff blocks
        assert diff_output.count("+++") >= 2


class TestDiffEmptyNoDrift:
    """Test diff output when there is no drift."""

    def test_diff_empty_no_drift(self):
        """Empty drift list produces helpful no-drift message."""
        report = DriftReport(scanned_path=Path("."), drift_items=[])
        reporter = DriftReporter(report)
        diff_output = reporter.report_diff()

        # Should indicate no drift
        assert "No drift" in diff_output or "no drift" in diff_output.lower()
