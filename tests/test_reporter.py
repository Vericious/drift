"""Tests for drift.reporter."""
from __future__ import annotations

import json
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
from drift.reporter import DriftReporter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fact_parse_config():
    """A CodeFact representing a parse_config function with a strict param."""
    return CodeFact(
        name="parse_config",
        kind=FactKind.FUNCTION,
        source_file=Path("src/parser.py"),
        line_number=42,
        parameters=[
            Parameter(name="strict", type_annotation="bool", default="False"),
        ],
        return_type="dict",
    )


@pytest.fixture
def claim_parse_config():
    """A DocClaim claiming parse_config without the strict param."""
    return DocClaim(
        raw_text='parse_config(config: dict) -> dict',
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path("README.md"),
        line_number=15,
        name="parse_config",
        parameters=[
            Parameter(name="config", type_annotation="dict"),
        ],
        return_type="dict",
    )


@pytest.fixture
def fact_do_something():
    """A CodeFact for do_something with flag defaulting to False."""
    return CodeFact(
        name="do_something",
        kind=FactKind.FUNCTION,
        source_file=Path("src/utils.py"),
        line_number=10,
        parameters=[
            Parameter(name="flag", type_annotation="bool", default="False"),
        ],
    )


@pytest.fixture
def claim_do_something():
    """A DocClaim claiming do_something with flag defaulting to True."""
    return DocClaim(
        raw_text='do_something(flag: bool = True)',
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path("README.md"),
        line_number=15,
        name="do_something",
        parameters=[
            Parameter(name="flag", type_annotation="bool", default="True"),
        ],
    )


@pytest.fixture
def populated_report(fact_parse_config, claim_parse_config, fact_do_something, claim_do_something):
    """A DriftReport with 2 errors and 1 warning."""
    items = [
        # Error: missing param
        DriftItem(
            fact=fact_parse_config,
            claim=claim_parse_config,
            severity=Severity.ERROR,
            category="missing_param",
            message="parse_config is missing parameter 'strict' documented in docs",
            suggestion="Update docs to include `strict` parameter",
        ),
        # Error: documented but missing (no matching code fact)
        DriftItem(
            fact=None,
            claim=DocClaim(
                raw_text="old_function(a, b, c)",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path("README.md"),
                line_number=23,
                name="old_function",
            ),
            severity=Severity.ERROR,
            category="documented_but_missing",
            message="Documented function old_function not found in scanned code",
        ),
        # Warning: wrong default
        DriftItem(
            fact=fact_do_something,
            claim=claim_do_something,
            severity=Severity.WARNING,
            category="wrong_default",
            message="Parameter 'flag' has different default: True (docs) vs False (code)",
        ),
    ]
    return DriftReport(
        scanned_path=Path("/path/to/project"),
        facts=[fact_parse_config, fact_do_something],
        claims=[claim_parse_config, claim_do_something],
        drift_items=items,
        errors=[],
    )


@pytest.fixture
def empty_report():
    """A DriftReport with no drift."""
    return DriftReport(
        scanned_path=Path("."),
        facts=[],
        claims=[],
        drift_items=[],
        errors=[],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestReportJson:
    """Tests for report_json()."""

    def test_returns_valid_json(self, populated_report):
        """report_json() returns a string that parses as JSON."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_json()
        # Should not raise
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_json_has_all_expected_fields(self, populated_report):
        """JSON output contains scanned_path, summary, has_drift, drift_items."""
        reporter = DriftReporter(populated_report)
        parsed = json.loads(reporter.report_json())

        assert "scanned_path" in parsed
        assert "summary" in parsed
        assert "has_drift" in parsed
        assert "drift_items" in parsed

        summary = parsed["summary"]
        assert "facts" in summary
        assert "claims" in summary
        assert "drift_items" in summary
        assert "errors" in summary
        assert "warnings" in summary

    def test_json_summary_counts(self, populated_report):
        """summary counts match the report's actual counts."""
        reporter = DriftReporter(populated_report)
        parsed = json.loads(reporter.report_json())
        summary = parsed["summary"]

        assert summary["facts"] == 2
        assert summary["claims"] == 2
        assert summary["drift_items"] == 3
        assert summary["errors"] == 2
        assert summary["warnings"] == 1

    def test_json_has_drift_true_when_errors_present(self, populated_report):
        """has_drift is True when the report has error-severity items."""
        reporter = DriftReporter(populated_report)
        parsed = json.loads(reporter.report_json())
        assert parsed["has_drift"] is True

    def test_json_has_drift_false_on_empty_report(self, empty_report):
        """has_drift is False on an empty report."""
        reporter = DriftReporter(empty_report)
        parsed = json.loads(reporter.report_json())
        assert parsed["has_drift"] is False

    def test_json_empty_report_summary(self, empty_report):
        """Empty report JSON has zero counts."""
        reporter = DriftReporter(empty_report)
        parsed = json.loads(reporter.report_json())
        summary = parsed["summary"]

        assert summary["facts"] == 0
        assert summary["claims"] == 0
        assert summary["drift_items"] == 0
        assert summary["errors"] == 0
        assert summary["warnings"] == 0

    def test_drift_items_have_severity_and_category(self, populated_report):
        """Each drift item in JSON has severity, category, message."""
        reporter = DriftReporter(populated_report)
        parsed = json.loads(reporter.report_json())

        for item in parsed["drift_items"]:
            assert "severity" in item
            assert "category" in item
            assert "message" in item

    def test_drift_items_fact_and_claim_serialized(self, populated_report):
        """fact and claim are serialized as dicts, not Path objects."""
        reporter = DriftReporter(populated_report)
        parsed = json.loads(reporter.report_json())

        for item in parsed["drift_items"]:
            if item["fact"] is not None:
                assert isinstance(item["fact"], dict)
                assert "source_file" in item["fact"]
                # Path should be string, not list
                assert isinstance(item["fact"]["source_file"], str)
            if item["claim"] is not None:
                assert isinstance(item["claim"], dict)
                assert "doc_file" in item["claim"]
                assert isinstance(item["claim"]["doc_file"], str)


class TestReportConsole:
    """Tests for report_console()."""

    def test_console_runs_without_error_on_populated_report(self, populated_report):
        """report_console() does not raise on a report with drift."""
        reporter = DriftReporter(populated_report)
        # Should not raise
        reporter.report_console()

    def test_console_runs_without_error_on_empty_report(self, empty_report):
        """report_console() does not raise on an empty report."""
        reporter = DriftReporter(empty_report)
        reporter.report_console()

    def test_console_shows_no_drift_on_empty_report(self, empty_report, capsys):
        """report_console() prints the no-drift message on an empty report."""
        reporter = DriftReporter(empty_report)
        reporter.report_console()
        captured = capsys.readouterr()
        assert "No drift detected" in captured.out

    def test_console_shows_summary(self, populated_report, capsys):
        """report_console() prints a summary line."""
        reporter = DriftReporter(populated_report)
        reporter.report_console()
        captured = capsys.readouterr()
        assert "facts" in captured.out
        assert "claims" in captured.out

    def test_console_shows_errors_section(self, populated_report, capsys):
        """report_console() prints an Errors section when errors are present."""
        reporter = DriftReporter(populated_report)
        reporter.report_console()
        captured = capsys.readouterr()
        assert "Errors" in captured.out

    def test_console_shows_warnings_section(self, populated_report, capsys):
        """report_console() prints a Warnings section when warnings are present."""
        reporter = DriftReporter(populated_report)
        reporter.report_console()
        captured = capsys.readouterr()
        assert "Warnings" in captured.out

    def test_console_shows_suggestion_when_present(self, populated_report, capsys):
        """Console output includes suggestion text when available."""
        reporter = DriftReporter(populated_report)
        reporter.report_console()
        captured = capsys.readouterr()
        assert "Update docs" in captured.out

    def test_console_shows_path(self, populated_report, capsys):
        """Console output includes the scanned path."""
        reporter = DriftReporter(populated_report)
        reporter.report_console()
        captured = capsys.readouterr()
        assert "/path/to/project" in captured.out


class TestCodeFactToDict:
    """Tests for CodeFact.to_dict()."""

    def test_to_dict_returns_dict(self):
        fact = CodeFact(
            name="my_func",
            kind=FactKind.FUNCTION,
            source_file=Path("src/foo.py"),
            line_number=5,
            parameters=[Parameter(name="x", type_annotation="int")],
        )
        d = fact.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "my_func"
        assert d["source_file"] == "src/foo.py"
        assert d["line_number"] == 5

    def test_to_dict_converts_path_to_string(self):
        fact = CodeFact(
            name="func",
            kind=FactKind.FUNCTION,
            source_file=Path("a/b.py"),
            line_number=1,
        )
        assert isinstance(fact.to_dict()["source_file"], str)


class TestDocClaimToDict:
    """Tests for DocClaim.to_dict()."""

    def test_to_dict_returns_dict(self):
        claim = DocClaim(
            raw_text="my_func(x: int)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/readme.md"),
            line_number=10,
            name="my_func",
            parameters=[Parameter(name="x", type_annotation="int")],
        )
        d = claim.to_dict()
        assert isinstance(d, dict)
        assert d["name"] == "my_func"
        assert d["doc_file"] == "docs/readme.md"
        assert d["line_number"] == 10

    def test_to_dict_converts_path_to_string(self):
        claim = DocClaim(
            raw_text="func()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("README.md"),
            line_number=1,
        )
        assert isinstance(claim.to_dict()["doc_file"], str)
