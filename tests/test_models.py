"""Tests for Drift data models."""

from pathlib import Path

from drift.models import (
    ClaimKind,
    CodeFact,
    DocClaim,
    DriftCategory,
    DriftItem,
    DriftReport,
    FactKind,
    Parameter,
    Severity,
)


class TestParameter:
    def test_create_minimal(self):
        p = Parameter(name="path")
        assert p.name == "path"
        assert p.type_annotation is None
        assert p.default is None

    def test_create_full(self):
        p = Parameter(
            name="strict", type_annotation="bool", default="False", kind="keyword"
        )
        assert p.name == "strict"
        assert p.type_annotation == "bool"
        assert p.default == "False"
        assert p.kind == "keyword"


class TestCodeFact:
    def test_create_minimal(self):
        f = CodeFact(
            name="parse_config",
            kind=FactKind.FUNCTION,
            source_file=Path("src/parser.py"),
            line_number=10,
        )
        assert f.name == "parse_config"
        assert f.kind == FactKind.FUNCTION
        assert f.parameters == []
        assert f.return_type is None

    def test_create_with_parameters_and_return(self):
        f = CodeFact(
            name="parse_config",
            kind=FactKind.FUNCTION,
            source_file=Path("src/parser.py"),
            line_number=10,
            parameters=[
                Parameter(name="path", type_annotation="str"),
                Parameter(name="strict", type_annotation="bool", default="False"),
            ],
            return_type="dict",
            module="src.parser",
            decorators=["@cache"],
        )
        assert len(f.parameters) == 2
        assert f.return_type == "dict"
        assert "@cache" in f.decorators
        assert (
            f.signature_str() == "parse_config(path: str, strict: bool = False) -> dict"
        )

    def test_signature_str_no_params(self):
        f = CodeFact(
            name="get_version",
            kind=FactKind.FUNCTION,
            source_file=Path("__init__.py"),
            line_number=1,
        )
        assert f.signature_str() == "get_version()"


class TestDocClaim:
    def test_create_minimal(self):
        c = DocClaim(
            raw_text="Use `parse_config(path, strict=False)`",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("README.md"),
            line_number=42,
        )
        assert c.raw_text == "Use `parse_config(path, strict=False)`"
        assert c.name is None
        assert c.parameters == []

    def test_create_with_extracted_data(self):
        c = DocClaim(
            raw_text="`do_something(a: int, b: str = 'hi') -> bool`",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("README.md"),
            line_number=10,
            name="do_something",
            parameters=[
                Parameter(name="a", type_annotation="int"),
                Parameter(name="b", type_annotation="str", default="'hi'"),
            ],
            return_type="bool",
        )
        assert c.name == "do_something"
        assert len(c.parameters) == 2
        assert c.return_type == "bool"


class TestDriftItem:
    def test_create_fully_optional(self):
        """fact and claim can both be None for missing/undocumented cases."""
        item = DriftItem(
            severity=Severity.ERROR,
            category=DriftCategory.UNDOCUMENTED.value,
            message="Function `foo` exists but is not documented",
        )
        assert item.fact is None
        assert item.claim is None
        assert item.category == "undocumented"

    def test_create_with_fact_and_claim(self):
        fact = CodeFact(
            name="bar",
            kind=FactKind.FUNCTION,
            source_file=Path("src/x.py"),
            line_number=5,
        )
        claim = DocClaim(
            raw_text="`bar()`",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("README.md"),
            line_number=20,
            name="bar",
        )
        item = DriftItem(
            fact=fact,
            claim=claim,
            severity=Severity.WARNING,
            category=DriftCategory.SIGNATURE_MISMATCH.value,
            message="Signature mismatch",
            suggestion="Update docs to match current signature",
        )
        assert item.fact is fact
        assert item.claim is claim
        assert item.suggestion is not None


class TestDriftReport:
    def test_empty_report_has_no_drift(self):
        r = DriftReport(scanned_path=Path("."))
        assert not r.has_drift
        assert r.errors_count == 0
        assert r.warnings_count == 0

    def test_errors_only_has_drift(self):
        """Only ERROR-severity items make has_drift True (per plan)."""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/x.py"),
            line_number=1,
        )
        item = DriftItem(
            fact=fact,
            severity=Severity.ERROR,
            category=DriftCategory.UNDOCUMENTED.value,
            message="Undocumented",
        )
        r = DriftReport(scanned_path=Path("."), drift_items=[item])
        assert r.has_drift

    def test_warnings_only_no_drift(self):
        """WARNING items don't count as drift for has_drift (per plan)."""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/x.py"),
            line_number=1,
        )
        item = DriftItem(
            fact=fact,
            severity=Severity.WARNING,
            category="minor_drift",
            message="Minor drift",
        )
        r = DriftReport(scanned_path=Path("."), drift_items=[item])
        assert not r.has_drift

    def test_summary_empty(self):
        r = DriftReport(scanned_path=Path("src"))
        assert r.summary() == "0 facts, 0 claims, 0 drift items (0 errors, 0 warnings)"

    def test_summary_with_data(self):
        fact = CodeFact(
            name="x",
            kind=FactKind.FUNCTION,
            source_file=Path("f.py"),
            line_number=1,
        )
        claim = DocClaim(
            raw_text="...",
            kind=ClaimKind.CODE_EXAMPLE,
            doc_file=Path("README.md"),
            line_number=1,
        )
        item = DriftItem(
            fact=fact,
            claim=claim,
            severity=Severity.ERROR,
            category=DriftCategory.MISSING_PARAM.value,
            message="Missing param",
        )
        r = DriftReport(
            scanned_path=Path("."),
            facts=[fact],
            claims=[claim],
            drift_items=[item],
        )
        summary = r.summary()
        assert "1 facts" in summary
        assert "1 claims" in summary
        assert "1 drift items" in summary
        assert "1 errors" in summary

    def test_has_drift_true_when_items_exist(self):
        item = DriftItem(
            severity=Severity.ERROR,
            category=DriftCategory.SIGNATURE_MISMATCH.value,
            message="mismatch",
        )
        r = DriftReport(scanned_path=Path("."), drift_items=[item])
        assert r.has_drift
