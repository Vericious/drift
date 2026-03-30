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


# ---------------------------------------------------------------------------
# Tests for --patch output (unified git-compatible patches)
# ---------------------------------------------------------------------------

import os
import tempfile

from drift.reporter import DriftReporter


class TestPatchOutputWrongDefault:
    """Test patch output for wrong_default category."""

    def test_patch_wrong_default(self):
        """Patch fixes wrong parameter default in docs."""
        # Create a temp doc file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("line 1\n")
            f.write("line 2\n")
            f.write("line 3 - def func(x: int = 0):\n")
            f.write("line 4\n")
            f.write("line 5\n")
            f.write("line 6\n")
            doc_path = f.name

        try:
            claim = DocClaim(
                raw_text="def func(x: int = 0):",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path(doc_path),
                line_number=3,
                name="func",
                parameters=[
                    Parameter(name="x", type_annotation="int", default="0", kind="positional")
                ],
            )
            fact = CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("src/api.py"),
                line_number=10,
                parameters=[
                    Parameter(name="x", type_annotation="int", default="42", kind="positional")
                ],
            )
            item = DriftItem(
                fact=fact,
                claim=claim,
                severity=Severity.ERROR,
                category="wrong_default",
                message="func has wrong default for x",
            )
            report = DriftReport(scanned_path=Path("."), drift_items=[item])
            reporter = DriftReporter(report)
            patch = reporter.report_patch()

            # Should have git diff format
            assert "diff --git" in patch
            assert "--- a/" in patch
            assert "+++ b/" in patch
            assert "@@" in patch
            assert "[wrong_default]" in patch
            # Should show old and new defaults
            assert "= 0" in patch
            assert "= 42" in patch
            # Should have removal and addition markers
            assert "-line 3 - def func(x: int = 0):" in patch
            assert "+line 3 - def func(x: int = 42):" in patch
        finally:
            os.unlink(doc_path)


class TestPatchOutputDocumentedButMissing:
    """Test patch output for documented_but_missing category."""

    def test_patch_documented_but_missing(self):
        """Patch removes the doc entry for a function not in code."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("line 1\n")
            f.write("line 2\n")
            f.write("line 3 - documented_func description\n")
            f.write("line 4\n")
            f.write("line 5\n")
            f.write("line 6\n")
            doc_path = f.name

        try:
            claim = DocClaim(
                raw_text="documented_func description",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path(doc_path),
                line_number=3,
                name="documented_func",
                parameters=[],
            )
            fact = CodeFact(
                name="documented_func",
                kind=FactKind.FUNCTION,
                source_file=Path("src/api.py"),
                line_number=10,
                parameters=[],
            )
            item = DriftItem(
                fact=fact,
                claim=claim,
                severity=Severity.ERROR,
                category="documented_but_missing",
                message="documented_func is documented but not found in code",
            )
            report = DriftReport(scanned_path=Path("."), drift_items=[item])
            reporter = DriftReporter(report)
            patch = reporter.report_patch()

            # Should have git diff format
            assert "diff --git" in patch
            assert "--- a/" in patch
            assert "+++ b/" in patch
            assert "@@" in patch
            assert "[documented_but_missing]" in patch
            # Should show removal of the documented line
            assert "-line 3 - documented_func description" in patch
            # No addition lines (pure deletion)
            lines = patch.split("\n")
            added = [l for l in lines if l.startswith("+") and not l.startswith("+++")]
            assert len(added) == 0
        finally:
            os.unlink(doc_path)


class TestPatchOutputSkipsUndocumented:
    """Test that patch output skips non-fixable categories."""

    def test_patch_skips_undocumented(self):
        """Undocumented (and other non-fixable categories) are skipped with a comment."""
        # Create an item with a non-fixable category (undocumented)
        item = DriftItem(
            fact=CodeFact(
                name="helper_func",
                kind=FactKind.FUNCTION,
                source_file=Path("src/helper.py"),
                line_number=3,
                parameters=[
                    Parameter(name="a", type_annotation="str", default=None, kind="positional")
                ],
            ),
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="'helper_func' exists in code but is not documented",
            suggestion="Add documentation for helper_func",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        patch = reporter.report_patch()

        # Should indicate no patchable items
        assert "skipped" in patch.lower() or "not patchable" in patch.lower()
        assert "No patchable drift items found" in patch
        # Should NOT have diff --git for undocumented
        assert "diff --git" not in patch

    def test_patch_mixed_fixable_and_unfixable(self):
        """When some items are fixable and some are not, only fixable get patches."""
        # Create a temp doc file for the fixable item
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False
        ) as f:
            f.write("line 1\n")
            f.write("line 2\n")
            f.write("line 3 - def func(x: int = 0):\n")
            f.write("line 4\n")
            f.write("line 5\n")
            f.write("line 6\n")
            doc_path = f.name

        try:
            # Fixable: wrong_default
            claim = DocClaim(
                raw_text="def func(x: int = 0):",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path(doc_path),
                line_number=3,
                name="func",
                parameters=[
                    Parameter(name="x", type_annotation="int", default="0", kind="positional")
                ],
            )
            fact = CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("src/api.py"),
                line_number=10,
                parameters=[
                    Parameter(name="x", type_annotation="int", default="99", kind="positional")
                ],
            )
            fixable_item = DriftItem(
                fact=fact,
                claim=claim,
                severity=Severity.ERROR,
                category="wrong_default",
                message="func has wrong default",
            )
            # Non-fixable: undocumented
            unfixable_item = DriftItem(
                fact=CodeFact(
                    name="helper",
                    kind=FactKind.FUNCTION,
                    source_file=Path("src/helper.py"),
                    line_number=5,
                    parameters=[],
                ),
                claim=None,
                severity=Severity.WARNING,
                category="undocumented",
                message="helper not documented",
            )
            report = DriftReport(
                scanned_path=Path("."),
                drift_items=[fixable_item, unfixable_item],
            )
            reporter = DriftReporter(report)
            patch = reporter.report_patch()

            # Should have patch for fixable item
            assert "diff --git" in patch
            assert "wrong_default" in patch
            assert "= 99" in patch
            # Should mention skip count
            assert "1 item(s) skipped" in patch
            # Should not have undocumented in a patch (should be skipped)
            assert patch.count("diff --git") == 1
        finally:
            os.unlink(doc_path)
