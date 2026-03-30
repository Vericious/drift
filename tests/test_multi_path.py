"""Tests for multi-path scan deduplication via _merge_reports()."""

from pathlib import Path

import pytest

from drift.cli import _merge_reports
from drift.models import (
    CodeFact,
    DocClaim,
    DriftItem,
    DriftReport,
    FactKind,
    ClaimKind,
    Severity,
)


@pytest.fixture
def fact_foo_a(tmp_path: Path) -> CodeFact:
    """A CodeFact for function foo in file a.py."""
    return CodeFact(
        name="foo",
        kind=FactKind.FUNCTION,
        source_file=tmp_path / "a.py",
        line_number=10,
        parameters=[],
        return_type=None,
        decorators=[],
        module="a",
    )


@pytest.fixture
def fact_foo_b(tmp_path: Path) -> CodeFact:
    """A CodeFact for function foo in file b.py."""
    return CodeFact(
        name="foo",
        kind=FactKind.FUNCTION,
        source_file=tmp_path / "b.py",
        line_number=20,
        parameters=[],
        return_type=None,
        decorators=[],
        module="b",
    )


@pytest.fixture
def claim_foo_a(tmp_path: Path) -> DocClaim:
    """A DocClaim for function foo in a.md."""
    return DocClaim(
        raw_text="def foo()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=tmp_path / "a.md",
        line_number=5,
        name="foo",
        metadata={},
    )


@pytest.fixture
def claim_foo_b(tmp_path: Path) -> DocClaim:
    """A DocClaim for function foo in b.md."""
    return DocClaim(
        raw_text="def foo()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=tmp_path / "b.md",
        line_number=5,
        name="foo",
        metadata={},
    )


def make_drift_item(
    fact: CodeFact, claim: DocClaim, category: str, severity: Severity = Severity.WARNING
) -> DriftItem:
    """Helper to create a DriftItem."""
    return DriftItem(
        fact=fact,
        claim=claim,
        severity=severity,
        category=category,
        message=f"{fact.name} is undocumented",
    )


def test_no_duplicates_same_file_two_paths(tmp_path: Path) -> None:
    """Same file appearing in two scan paths produces no duplicate drift items."""
    fact_foo = CodeFact(
        name="foo",
        kind=FactKind.FUNCTION,
        source_file=tmp_path / "a.py",
        line_number=10,
        parameters=[],
        return_type=None,
        decorators=[],
        module="a",
    )
    claim_foo = DocClaim(
        raw_text="def foo()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=tmp_path / "a.md",
        line_number=5,
        name="foo",
        metadata={},
    )

    item = make_drift_item(fact_foo, claim_foo, "undocumented")

    # Report 1: scan of path /first
    report1 = DriftReport(
        scanned_path=Path("/first"),
        facts=[fact_foo],
        claims=[claim_foo],
        drift_items=[item],
    )

    # Report 2: scan of path /second (same file, same fact+claim)
    report2 = DriftReport(
        scanned_path=Path("/second"),
        facts=[fact_foo],
        claims=[claim_foo],
        drift_items=[item],
    )

    merged = _merge_reports([report1, report2])

    # Should have only ONE drift item (deduplicated)
    assert len(merged.drift_items) == 1
    assert merged.drift_items[0].fact == fact_foo
    assert merged.drift_items[0].claim == claim_foo


def test_no_duplicates_ts_and_md_overlap(tmp_path: Path) -> None:
    """Overlapping TypeScript and Markdown claims for the same symbol are deduplicated."""
    fact_user = CodeFact(
        name="User",
        kind=FactKind.CLASS,
        source_file=tmp_path / "user.ts",
        line_number=1,
        parameters=[],
        return_type=None,
        decorators=[],
        module="user",
    )

    # Claim from TypeScript code block
    claim_ts = DocClaim(
        raw_text="interface User",
        kind=ClaimKind.TS_CODE_BLOCK,
        doc_file=tmp_path / "api.md",
        line_number=10,
        name="User",
        metadata={"ts_kind": "interface"},
    )

    # Claim from Markdown property table (same symbol)
    claim_md = DocClaim(
        raw_text="User",
        kind=ClaimKind.TS_INTERFACE_REF,
        doc_file=tmp_path / "api.md",
        line_number=20,
        name="User",
        metadata={},
    )

    item_ts = DriftItem(
        fact=fact_user,
        claim=claim_ts,
        severity=Severity.WARNING,
        category="interface",
        message="User interface is undocumented",
    )

    item_md = DriftItem(
        fact=fact_user,
        claim=claim_md,
        severity=Severity.WARNING,
        category="interface",
        message="User interface is undocumented",
    )

    report1 = DriftReport(
        scanned_path=Path("/first"),
        facts=[fact_user],
        claims=[claim_ts],
        drift_items=[item_ts],
    )

    report2 = DriftReport(
        scanned_path=Path("/second"),
        facts=[fact_user],
        claims=[claim_md],
        drift_items=[item_md],
    )

    merged = _merge_reports([report1, report2])

    # Same (source_file, name, claim.name, category) → deduplicated to 1
    assert len(merged.drift_items) == 1
    assert merged.drift_items[0].fact == fact_user
    assert merged.drift_items[0].claim.name == "User"


def test_merge_preserves_unique_items(tmp_path: Path) -> None:
    """Unique drift items from different files/paths are all preserved."""
    fact_foo = CodeFact(
        name="foo",
        kind=FactKind.FUNCTION,
        source_file=tmp_path / "a.py",
        line_number=10,
        parameters=[],
        return_type=None,
        decorators=[],
        module="a",
    )
    fact_bar = CodeFact(
        name="bar",
        kind=FactKind.FUNCTION,
        source_file=tmp_path / "b.py",
        line_number=15,
        parameters=[],
        return_type=None,
        decorators=[],
        module="b",
    )

    claim_foo = DocClaim(
        raw_text="def foo()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=tmp_path / "a.md",
        line_number=5,
        name="foo",
        metadata={},
    )
    claim_bar = DocClaim(
        raw_text="def bar()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=tmp_path / "b.md",
        line_number=5,
        name="bar",
        metadata={},
    )

    item_foo = make_drift_item(fact_foo, claim_foo, "undocumented")
    item_bar = make_drift_item(fact_bar, claim_bar, "undocumented")

    report1 = DriftReport(
        scanned_path=Path("/first"),
        facts=[fact_foo, fact_bar],
        claims=[claim_foo, claim_bar],
        drift_items=[item_foo, item_bar],
    )

    report2 = DriftReport(
        scanned_path=Path("/second"),
        facts=[fact_foo],  # foo also scanned in second path
        claims=[claim_foo],
        drift_items=[item_foo],  # duplicate
    )

    merged = _merge_reports([report1, report2])

    # Should have 2 unique items (foo and bar)
    assert len(merged.drift_items) == 2
    names = {item.fact.name for item in merged.drift_items}
    assert names == {"foo", "bar"}


def test_deduplication_key_is_tuple(tmp_path: Path) -> None:
    """Deduplication uses (source_file, fact.name, claim.name, category) as key."""
    fact = CodeFact(
        name="foo",
        kind=FactKind.FUNCTION,
        source_file=tmp_path / "a.py",
        line_number=10,
        parameters=[],
        return_type=None,
        decorators=[],
        module="a",
    )
    claim = DocClaim(
        raw_text="def foo()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=tmp_path / "a.md",
        line_number=5,
        name="foo",
        metadata={},
    )

    item1 = DriftItem(
        fact=fact,
        claim=claim,
        severity=Severity.WARNING,
        category="undocumented",
        message="foo is undocumented",
    )
    # Same fact+claim but different category
    item2 = DriftItem(
        fact=fact,
        claim=claim,
        severity=Severity.WARNING,
        category="different_category",
        message="foo is undocumented",
    )

    report1 = DriftReport(
        scanned_path=Path("/first"),
        facts=[fact],
        claims=[claim],
        drift_items=[item1],
    )
    report2 = DriftReport(
        scanned_path=Path("/second"),
        facts=[fact],
        claims=[claim],
        drift_items=[item2],
    )

    merged = _merge_reports([report1, report2])

    # Different categories → different dedup keys → both kept
    assert len(merged.drift_items) == 2
    categories = {item.category for item in merged.drift_items}
    assert categories == {"undocumented", "different_category"}


def test_empty_reports_list() -> None:
    """Merging an empty list of reports returns a valid empty report."""
    merged = _merge_reports([])
    assert merged.scanned_path == Path(".")
    assert merged.drift_items == []


def test_single_report_passed_through() -> None:
    """A single report is returned as-is (no unnecessary processing)."""
    fact = CodeFact(
        name="foo",
        kind=FactKind.FUNCTION,
        source_file=Path("/a.py"),
        line_number=10,
        parameters=[],
        return_type=None,
        decorators=[],
        module="a",
    )
    claim = DocClaim(
        raw_text="def foo()",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path("/a.md"),
        line_number=5,
        name="foo",
        metadata={},
    )
    item = DriftItem(
        fact=fact,
        claim=claim,
        severity=Severity.WARNING,
        category="undocumented",
        message="foo is undocumented",
    )

    report = DriftReport(
        scanned_path=Path("/first"),
        facts=[fact],
        claims=[claim],
        drift_items=[item],
    )

    merged = _merge_reports([report])

    assert merged is report
    assert len(merged.drift_items) == 1
