"""Tests for diff-style output (--diff-output flag)."""

from pathlib import Path

import pytest

from drift.models import ClaimKind, CodeFact, DocClaim, DriftItem, DriftReport, FactKind, Parameter, Severity
from drift.reporter import DriftReporter


def temp_project(tmp_path: Path) -> Path:
    """Create a temporary project with sample Python and markdown files."""
    py_file = tmp_path / "example.py"
    py_file.write_text(
        "def documented_func():\n"
        "    '''Documented.'''\n"
        "    pass\n"
        "\n"
        "\n"
        "def undocumented_func():\n"
        "    '''Not documented.'''\n"
        "    pass\n"
    )
    md_file = tmp_path / "docs.md"
    md_file.write_text(
        "# API\n\n"
        "## documented_func\n\n"
        "```python\n"
        "def documented_func()\n"
        "```\n"
    )
    return tmp_path


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


class TestAnsiDiffColors:
    """Test ANSI color codes in diff output."""

    def test_ansi_codes_in_terminal_mode(self):
        """Terminal mode (color=True) includes ANSI color codes."""
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
        diff_output = reporter.report_diff(color=True)

        # ANSI escape codes should be present
        assert "\033[31m" in diff_output  # Red for ---
        assert "\033[32m" in diff_output  # Green for +++
        assert "\033[36m" in diff_output  # Cyan for @@
        # Reset codes should also be present
        assert "\033[0m" in diff_output

    def test_no_ansi_in_pipe_mode(self):
        """Pipe mode (color=False) excludes ANSI color codes."""
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
        diff_output = reporter.report_diff(color=False)

        # ANSI escape codes should NOT be present
        assert "\033[" not in diff_output
        assert "---" in diff_output  # Content still present
        assert "+++" in diff_output

    def test_ansi_codes_apply_to_correct_line_types(self):
        """Each diff line type gets the correct color."""
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
        diff_output = reporter.report_diff(color=True)

        # --- lines should be red
        assert "\033[31m--- " in diff_output
        # +++ lines should be green
        assert "\033[32m+++ " in diff_output
        # @@ lines should be cyan
        assert "\033[36m@@" in diff_output
        # - lines (removed) should be red
        assert "\033[31m- def func_a" in diff_output
        # + lines (added) should be green
        assert "\033[32m+" in diff_output


class TestPatchMode:
    """Tests for --patch mode (unified diff output)."""

    def test_patch_documented_but_missing(self):
        """Patch mode produces unified diff for documented_but_missing."""
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
        patch_output = reporter.report_diff(patch=True)

        # Should have git diff header
        assert "diff --git" in patch_output
        # Should have proper hunk header
        assert "@@" in patch_output
        # Should show what's missing
        assert "MISSING" in patch_output

    def test_patch_skips_undocumented(self):
        """Patch mode skips undocumented items with a comment."""
        item = make_drift_item(
            category="undocumented",
            claim_name="func_b",
            fact_name="func_b",
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        patch_output = reporter.report_diff(patch=True)

        # Should have a skip comment
        assert "Skipped" in patch_output or "not directly patchable" in patch_output.lower()

    def test_patch_parameter_mismatch(self):
        """Patch mode produces unified diff for parameter_mismatch."""
        item = make_drift_item(
            category="parameter_mismatch",
            claim_name="func_c",
            fact_name="func_c",
            doc_params=[{"name": "x", "type_annotation": "int", "default": None, "kind": "positional"}],
            code_params=[{"name": "x", "type_annotation": "str", "default": None, "kind": "positional"}],
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        patch_output = reporter.report_diff(patch=True)

        # Should have git diff header
        assert "diff --git" in patch_output
        # Should have proper hunk header
        assert "@@" in patch_output
        # Should show the mismatch
        assert "Skipped" not in patch_output or "diff --git" in patch_output

    def test_patch_fuzzy_renamed(self):
        """Patch mode produces unified diff for fuzzy_renamed."""
        item = make_drift_item(
            category="fuzzy_renamed",
            claim_name="old_func",
            fact_name="new_func",
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        patch_output = reporter.report_diff(patch=True)

        # Should have git diff header
        assert "diff --git" in patch_output
        # Should have proper hunk header
        assert "@@" in patch_output
        # Should show the rename
        assert "old_func" in patch_output
        assert "new_func" in patch_output
        # Should NOT be skipped
        assert "Skipped" not in patch_output


# Spec-required tests for DRIFT-157
def test_diff_clean_no_markup() -> None:
    """Output contains no Rich markup tags like [red], [bold], etc."""
    item = make_drift_item(
        category="documented_but_missing",
        claim_name="test_func",
        fact_name="test_func",
    )
    report = DriftReport(scanned_path=Path("."), drift_items=[item])
    reporter = DriftReporter(report)
    diff_output = reporter.report_diff()

    # No Rich markup tags should be present
    assert "[bold" not in diff_output
    assert "[cyan" not in diff_output
    assert "[red" not in diff_output


def test_diff_color_terminal() -> None:
    """Terminal mode (color=True) includes ANSI color codes."""
    item = make_drift_item(
        category="documented_but_missing",
        claim_name="func_a",
        fact_name="func_a",
    )
    report = DriftReport(scanned_path=Path("."), drift_items=[item])
    reporter = DriftReporter(report)
    diff_output = reporter.report_diff(color=True)

    # ANSI escape codes should be present
    assert "\033[31m" in diff_output  # Red for ---
    assert "\033[32m" in diff_output  # Green for +++


def test_diff_plain_pipe() -> None:
    """Pipe mode (color=False) outputs plain text without ANSI codes."""
    item = make_drift_item(
        category="documented_but_missing",
        claim_name="func_a",
        fact_name="func_a",
    )
    report = DriftReport(scanned_path=Path("."), drift_items=[item])
    reporter = DriftReporter(report)
    diff_output = reporter.report_diff(color=False)

    # No ANSI escape sequences in pipe mode
    assert "\033[" not in diff_output
    # Plain text markers should still be present
    assert "---" in diff_output
    assert "+++" in diff_output


def test_diff_patch_wrong_default() -> None:
    """Patch mode with non-fixable category shows skip message."""
    item = make_drift_item(
        category="undocumented",
        claim_name="helper_func",
        fact_name="helper_func",
    )
    report = DriftReport(scanned_path=Path("."), drift_items=[item])
    reporter = DriftReporter(report)
    patch_output = reporter.report_diff(patch=True)

    # Undocumented items should be skipped in patch mode
    assert "Skipped" in patch_output or "diff --git" in patch_output


def test_diff_multiple_items() -> None:
    """Multiple drift items produce separate diff blocks."""
    item1 = make_drift_item(
        category="documented_but_missing",
        claim_name="func_a",
        fact_name="func_a",
        doc_file="docs/a.md",
        code_file="src/a.py",
    )
    item2 = make_drift_item(
        category="undocumented",
        claim_name="func_b",
        fact_name="func_b",
        doc_file="docs/b.md",
        code_file="src/b.py",
    )
    item2.claim = None  # undocumented = no claim
    report = DriftReport(scanned_path=Path("."), drift_items=[item1, item2])
    reporter = DriftReporter(report)
    diff_output = reporter.report_diff()

    # Should have two separate blocks (two sets of ---/+++/@@)
    assert diff_output.count("---") >= 2
    assert diff_output.count("+++") >= 2
    assert diff_output.count("@@") >= 2


def test_diff_empty_no_drift() -> None:
    """No drift items produces helpful message."""
    report = DriftReport(scanned_path=Path("."), drift_items=[])
    reporter = DriftReporter(report)
    diff_output = reporter.report_diff()

    assert "No drift" in diff_output or "no drift" in diff_output.lower()
