"""Tests for confidence scoring (DRIFT-095)."""

import pytest

from drift.matcher import SignatureMatcher
from drift.models import (
    ClaimKind,
    CodeFact,
    DocClaim,
    DriftItem,
    FactKind,
    Parameter,
    Path,
    Severity,
)


class TestConfidence:
    def test_exact_match_confidence(self):
        """exact_match (parameter mismatch): confidence = 1.0"""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[Parameter(name="x"), Parameter(name="y")],
        )
        claim = DocClaim(
            raw_text="foo(x, y)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[Parameter(name="x"), Parameter(name="y")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        # No drift items since they match exactly
        assert items == []

    def test_exact_match_missing_param_confidence(self):
        """Parameter missing in docs: exact match so confidence = 1.0"""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[Parameter(name="x"), Parameter(name="y")],
        )
        # Claim only documents 'x', 'y' is missing
        claim = DocClaim(
            raw_text="foo(x)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[Parameter(name="x")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        assert len(items) == 1
        assert items[0].confidence == 1.0
        assert items[0].category == "missing_param"

    def test_document_but_missing_confidence(self):
        """documented_but_missing: confidence = 0.0"""
        claim = DocClaim(
            raw_text="def bar(): ...",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="bar",
            parameters=[],
        )
        matcher = SignatureMatcher()
        items = matcher.match([], [claim])
        assert len(items) == 1
        assert items[0].confidence == 0.0
        assert items[0].category == "documented_but_missing"

    def test_undocumented_confidence(self):
        """undocumented: confidence = 0.0"""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[Parameter(name="x")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [])
        assert len(items) == 1
        assert items[0].confidence == 0.0
        assert items[0].category == "undocumented"

    def test_fuzzy_confidence(self):
        """fuzzy_renamed: confidence reflects fuzzy ratio"""
        fact = CodeFact(
            name="my_function",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[Parameter(name="x")],
        )
        # Name is similar enough to fuzzy-match
        claim = DocClaim(
            raw_text="myFunction(x)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="myFunction",
            parameters=[Parameter(name="x")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        assert 0.0 < fuzzy_items[0].confidence <= 1.0

    def test_renamed_confidence(self):
        """renamed: confidence based on name ratio"""
        fact = CodeFact(
            name="bar",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[Parameter(name="x")],
        )
        # Similar name, different enough to not fuzzy-match
        claim = DocClaim(
            raw_text="baz(x)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="baz",
            parameters=[Parameter(name="x")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        renamed_items = [i for i in items if i.category == "renamed"]
        assert len(renamed_items) == 1
        assert 0.0 < renamed_items[0].confidence <= 1.0

    def test_wrong_default_confidence(self):
        """wrong_default: exact match so confidence = 1.0"""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[Parameter(name="x", default="1")],
        )
        claim = DocClaim(
            raw_text="foo(x=0)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[Parameter(name="x", default="0")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        assert len(items) == 1
        assert items[0].confidence == 1.0
        assert items[0].category == "wrong_default"

    def test_drift_item_confidence_field_exists(self):
        """DriftItem has a confidence field with correct default."""
        item = DriftItem(
            fact=None,
            claim=None,
            severity=Severity.WARNING,
            category="test",
            message="test",
        )
        assert hasattr(item, "confidence")
        assert item.confidence == 1.0  # default

    def test_drift_item_confidence_explicit(self):
        """DriftItem confidence can be set explicitly."""
        item = DriftItem(
            fact=None,
            claim=None,
            severity=Severity.ERROR,
            category="documented_but_missing",
            message="test",
            confidence=0.0,
        )
        assert item.confidence == 0.0

    def test_confidence_signals_fuzzy_renamed(self):
        """fuzzy_renamed: signals populated with name_similarity, param_overlap, type_match."""
        fact = CodeFact(
            name="my_function",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y", type_annotation="str"),
            ],
        )
        # Name is similar enough to fuzzy-match; param names match but types differ for y
        claim = DocClaim(
            raw_text="myFunction(x: int, y: int)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="myFunction",
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y", type_annotation="int"),  # type mismatch
            ],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        item = fuzzy_items[0]
        assert item.signals is not None
        assert 0.0 < item.signals.name_similarity <= 1.0
        assert item.signals.param_overlap == 1.0  # all param names match
        assert item.signals.type_match == 0.5  # x matches but y doesn't (1/2)
        assert item.signals.location_proximity == 0.0
        assert item.signals.context_match == 0.0
        # confidence should come from signals.score()
        assert item.confidence == item.signals.score()
