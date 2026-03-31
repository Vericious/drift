"""Tests for drift.reporter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from drift.models import (
    ClaimKind,
    CodeFact,
    ConfidenceSignals,
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
        raw_text="parse_config(config: dict) -> dict",
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
        raw_text="do_something(flag: bool = True)",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path("README.md"),
        line_number=15,
        name="do_something",
        parameters=[
            Parameter(name="flag", type_annotation="bool", default="True"),
        ],
    )


@pytest.fixture
def populated_report(
    fact_parse_config, claim_parse_config, fact_do_something, claim_do_something
):
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

    def test_json_includes_signals_object(self):
        """JSON output includes 'signals' object with all 5 fields when signals are present."""
        signals = ConfidenceSignals(
            name_similarity=0.9,
            param_overlap=1.0,
            type_match=0.8,
            location_proximity=0.5,
            context_match=0.7,
        )
        item = DriftItem(
            fact=CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("a.py"),
                line_number=1,
            ),
            severity=Severity.WARNING,
            category="missing_param",
            message="test",
            confidence=0.85,
            signals=signals,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_json())

        drift_items = parsed["drift_items"]
        assert len(drift_items) == 1
        sig = drift_items[0]["signals"]
        assert sig["name_similarity"] == 0.9
        assert sig["param_overlap"] == 1.0
        assert sig["type_match"] == 0.8
        assert sig["location_proximity"] == 0.5
        assert sig["context_match"] == 0.7

    def test_json_omits_signals_when_none(self):
        """JSON output omits 'signals' field when item.signals is None."""
        item = DriftItem(
            fact=CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("a.py"),
                line_number=1,
            ),
            severity=Severity.WARNING,
            category="missing_param",
            message="test",
            confidence=0.5,
            signals=None,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_json())

        assert "signals" not in parsed["drift_items"][0]


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

    def test_console_shows_confidence_pct(self, populated_report, capsys):
        """Console output includes 'Confidence: N%' inline per drift item."""
        reporter = DriftReporter(populated_report)
        reporter.report_console()
        captured = capsys.readouterr()
        # The populated_report has 3 drift items with various confidences
        # (1.0, 0.0, 1.0) — we just check the format appears
        assert "Confidence:" in captured.out
        assert "%" in captured.out


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


# ---------------------------------------------------------------------------
# JSON Schema validation
# ---------------------------------------------------------------------------

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent / "schemas" / "drift-report.schema.json"
)


class TestJsonSchema:
    """Validate that report_json() output conforms to drift-report.schema.json."""

    @pytest.fixture
    def schema(self):
        import jsonschema  # noqa: F811

        raw = json.loads(SCHEMA_PATH.read_text())
        jsonschema.Draft202012Validator.check_schema(raw)  # schema itself is valid
        return raw

    @pytest.fixture
    def validator(self, schema):
        import jsonschema

        return jsonschema.Draft202012Validator(schema)

    def test_schema_file_exists(self):
        assert SCHEMA_PATH.exists(), f"Schema not found at {SCHEMA_PATH}"

    def test_schema_validates_empty_report(self, validator):
        """A scan with no drift should still validate."""
        report = DriftReport(scanned_path=Path("."))
        reporter = DriftReporter(report)
        data = json.loads(reporter.report_json())
        validator.validate(data)

    def test_schema_validates_report_with_drift(self, validator):
        """A report containing drift items should validate."""
        fact = CodeFact(
            name="serve",
            kind=FactKind.FUNCTION,
            source_file=Path("app.py"),
            line_number=10,
            parameters=[
                Parameter(name="host", type_annotation="str", default='"0.0.0.0"')
            ],
            return_type="None",
        )
        claim = DocClaim(
            raw_text="serve(port)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("README.md"),
            line_number=5,
            name="serve",
            parameters=[Parameter(name="port", type_annotation="int")],
        )
        item = DriftItem(
            fact=fact,
            claim=claim,
            severity=Severity.ERROR,
            category="missing_param",
            message="Parameter 'host' not documented",
            suggestion="Add 'host' parameter to docs",
        )
        report = DriftReport(
            scanned_path=Path("/tmp/project"),
            facts=[fact],
            claims=[claim],
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        data = json.loads(reporter.report_json())
        validator.validate(data)

    def test_schema_validates_verbose_report(self, validator):
        """Verbose output includes scan_time_seconds — should still validate."""
        report = DriftReport(scanned_path=Path("."))
        reporter = DriftReporter(report, verbose=True)
        data = json.loads(reporter.report_json(verbose=True, elapsed=1.234))
        validator.validate(data)
        assert data["scan_time_seconds"] == 1.234

    def test_schema_validates_null_fact_and_claim(self, validator):
        """Drift items with null fact or claim should validate."""
        item = DriftItem(
            fact=None,
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="Something undocumented",
            suggestion=None,
        )
        report = DriftReport(
            scanned_path=Path("."),
            drift_items=[item],
        )
        reporter = DriftReporter(report)
        data = json.loads(reporter.report_json())
        validator.validate(data)


# ---------------------------------------------------------------------------
# SARIF output tests
# ---------------------------------------------------------------------------


class TestReportSarif:
    """Tests for report_sarif()."""

    def test_sarif_returns_valid_json(self, populated_report):
        """report_sarif() returns a string that parses as JSON."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_sarif()
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_sarif_has_required_fields(self, populated_report):
        """SARIF output has version, $schema, and runs."""
        reporter = DriftReporter(populated_report)
        parsed = json.loads(reporter.report_sarif())
        assert parsed["version"] == "2.1.0"
        assert "$schema" in parsed
        assert "runs" in parsed
        assert len(parsed["runs"]) == 1

    def test_sarif_rule_id_format(self, populated_report):
        """Rule IDs follow drift/{category} format."""
        reporter = DriftReporter(populated_report)
        parsed = json.loads(reporter.report_sarif())
        rules = parsed["runs"][0]["tool"]["driver"]["rules"]
        for rule in rules:
            assert rule["id"].startswith("drift/")

    def test_sarif_severity_mapping_error(self):
        """ERROR severity maps to SARIF level 'error'."""
        item = DriftItem(
            fact=CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("a.py"),
                line_number=1,
            ),
            severity=Severity.ERROR,
            category="missing_param",
            message="Missing param",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_sarif())
        assert parsed["runs"][0]["results"][0]["level"] == "error"

    def test_sarif_severity_mapping_warning(self):
        """WARNING severity maps to SARIF level 'warning'."""
        item = DriftItem(
            fact=CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("a.py"),
                line_number=1,
            ),
            severity=Severity.WARNING,
            category="wrong_default",
            message="Wrong default",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_sarif())
        assert parsed["runs"][0]["results"][0]["level"] == "warning"

    def test_sarif_severity_mapping_info(self):
        """INFO severity maps to SARIF level 'note'."""
        item = DriftItem(
            fact=CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("a.py"),
                line_number=1,
            ),
            severity=Severity.INFO,
            category="undocumented",
            message="Undocumented",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_sarif())
        assert parsed["runs"][0]["results"][0]["level"] == "note"

    def test_sarif_includes_code_location(self):
        """SARIF result includes physicalLocation with artifactLocation for fact."""
        fact = CodeFact(
            name="my_func",
            kind=FactKind.FUNCTION,
            source_file=Path("src/utils.py"),
            line_number=42,
        )
        item = DriftItem(
            fact=fact,
            severity=Severity.ERROR,
            category="missing_param",
            message="Missing param",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_sarif())
        locs = parsed["runs"][0]["results"][0]["locations"]
        assert any(
            loc["physicalLocation"]["artifactLocation"]["uri"] == "src/utils.py"
            for loc in locs
        )

    def test_sarif_includes_doc_location(self):
        """SARIF result includes physicalLocation for claim doc file."""
        claim = DocClaim(
            raw_text="my_func()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/README.md"),
            line_number=10,
            name="my_func",
        )
        item = DriftItem(
            claim=claim,
            severity=Severity.WARNING,
            category="documented_but_missing",
            message="Documented but missing",
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_sarif())
        locs = parsed["runs"][0]["results"][0]["locations"]
        assert any(
            loc["physicalLocation"]["artifactLocation"]["uri"] == "docs/README.md"
            for loc in locs
        )

    def test_sarif_empty_report_has_no_results(self, empty_report):
        """Empty report produces SARIF with empty results array."""
        reporter = DriftReporter(empty_report)
        parsed = json.loads(reporter.report_sarif())
        assert parsed["runs"][0]["results"] == []

    def test_sarif_verbose_includes_scan_time(self):
        """Verbose SARIF output includes scan time in properties."""
        report = DriftReport(scanned_path=Path("."))
        reporter = DriftReporter(report, verbose=True)
        parsed = json.loads(reporter.report_sarif(verbose=True, elapsed=2.5))
        assert parsed["runs"][0]["properties"]["scanTimeSeconds"] == 2.5

    def test_sarif_rank_equals_confidence_times_100(self):
        """SARIF result 'rank' equals confidence * 100."""
        item = DriftItem(
            fact=CodeFact(
                name="func",
                kind=FactKind.FUNCTION,
                source_file=Path("a.py"),
                line_number=1,
            ),
            severity=Severity.WARNING,
            category="missing_param",
            message="test",
            confidence=0.75,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_sarif())
        assert parsed["runs"][0]["results"][0]["rank"] == 75.0


class TestReportHtml:
    """Tests for report_html()."""

    def test_html_returns_string(self, populated_report):
        """report_html() returns a string containing HTML."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_html()
        assert isinstance(output, str)
        assert "<html" in output
        assert "</html>" in output

    def test_html_has_doctype(self, populated_report):
        """HTML output starts with <!DOCTYPE html>."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_html()
        assert output.startswith("<!DOCTYPE html>")

    def test_html_has_title(self, populated_report):
        """HTML output has a Drift Report title."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_html()
        assert "<title>Drift Report" in output

    def test_html_contains_css_inline(self, populated_report):
        """HTML output has inline CSS, no external dependencies."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_html()
        assert "<style>" in output
        assert "font-family:" in output
        # No external CSS links
        assert 'rel="stylesheet"' not in output
        assert 'href="http' not in output

    def test_html_shows_errors_when_present(self, populated_report):
        """HTML shows errors section when drift items have ERROR severity."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_html()
        assert "Errors" in output or "error" in output.lower()

    def test_html_shows_no_drift_on_empty_report(self, empty_report):
        """Empty report shows 'No drift detected' message."""
        reporter = DriftReporter(empty_report)
        output = reporter.report_html()
        assert "No drift detected" in output

    def test_html_empty_report_no_tables(self, empty_report):
        """Empty report has no table elements."""
        reporter = DriftReporter(empty_report)
        output = reporter.report_html()
        assert "<table" not in output

    def test_html_has_drift_version(self, populated_report):
        """HTML footer mentions Drift version."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_html()
        assert "Drift v0.5.0-dev" in output

    def test_html_output_has_exactly_one_closing_tag(self, populated_report):
        """HTML output contains exactly one </html> closing tag (no duplicates)."""
        reporter = DriftReporter(populated_report)
        output = reporter.report_html()
        assert output.count("</html>") == 1
