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
