"""Tests for confidence scoring (DRIFT-095)."""

import pytest

from drift.matcher import SignatureMatcher
from drift.models import (
    ClaimKind,
    CodeFact,
    ConfidenceSignals,
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

    def test_confidence_signals_exact_match(self):
        """Exact match with drift (wrong_default) has name_similarity=1.0 and signals set."""
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
        item = items[0]
        assert item.category == "wrong_default"
        assert item.signals is not None
        assert item.signals.name_similarity == 1.0
        assert item.signals.param_overlap == 1.0  # single param matches
        assert item.signals.type_match == 0.0  # wrong_default, not wrong_type

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


class TestConfidenceSignalsScore:
    """Tests for ConfidenceSignals.score() weighted combination."""

    def test_confidence_signals_score_weights(self):
        """score() returns correct weighted sum with weights:
        name_similarity=0.35, param_overlap=0.30, type_match=0.15,
        location_proximity=0.10, context_match=0.10."""
        signals = ConfidenceSignals(
            name_similarity=1.0,
            param_overlap=1.0,
            type_match=1.0,
            location_proximity=1.0,
            context_match=1.0,
        )
        # 0.35 + 0.30 + 0.15 + 0.10 + 0.10 = 1.0
        assert signals.score() == 1.0

    def test_confidence_signals_score_partial(self):
        """score() with partial signals returns weighted sum."""
        signals = ConfidenceSignals(
            name_similarity=0.5,
            param_overlap=0.5,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        # 0.5*0.35 + 0.5*0.30 = 0.175 + 0.15 = 0.325
        assert signals.score() == 0.325

    def test_confidence_signals_score_clamp_low(self):
        """score() clamps to 0.0 when weighted sum is negative (all zeros)."""
        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        assert signals.score() == 0.0

    def test_confidence_signals_score_rounds_to_3_decimal_places(self):
        """score() rounds result to 3 decimal places."""
        signals = ConfidenceSignals(
            name_similarity=0.333,
            param_overlap=0.333,
            type_match=0.333,
            location_proximity=0.0,
            context_match=0.0,
        )
        # 0.333*0.35 + 0.333*0.30 + 0.333*0.15 = 0.11655 + 0.0999 + 0.04995 = 0.2664
        assert signals.score() == 0.266


class TestJaccardParamOverlap:
    """Tests for _jaccard_param_overlap helper in SignatureMatcher."""

    def test_confidence_param_overlap_jaccard_full_overlap(self):
        """Full overlap: identical param names returns 1.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import Parameter
        matcher = SignatureMatcher()
        fact_params = {"x": Parameter("x"), "y": Parameter("y")}
        claim_params = {"x": Parameter("x"), "y": Parameter("y")}
        # intersection={x,y}, union={x,y} -> 2/2 = 1.0
        assert matcher._jaccard_param_overlap(fact_params, claim_params) == 1.0

    def test_confidence_param_overlap_jaccard_partial_overlap(self):
        """Partial overlap: shared + unique returns correct Jaccard."""
        from drift.matcher import SignatureMatcher
        from drift.models import Parameter
        matcher = SignatureMatcher()
        fact_params = {"x": Parameter("x"), "y": Parameter("y")}
        claim_params = {"x": Parameter("x"), "z": Parameter("z")}
        # intersection={x}, union={x,y,z} -> 1/3
        assert matcher._jaccard_param_overlap(fact_params, claim_params) == pytest.approx(1 / 3)

    def test_confidence_param_overlap_jaccard_no_overlap(self):
        """No overlap: disjoint sets returns 0.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import Parameter
        matcher = SignatureMatcher()
        fact_params = {"x": Parameter("x")}
        claim_params = {"y": Parameter("y")}
        # intersection={}, union={x,y} -> 0/2 = 0.0
        assert matcher._jaccard_param_overlap(fact_params, claim_params) == 0.0

    def test_confidence_param_overlap_jaccard_empty_both(self):
        """Both empty: returns 0.0."""
        from drift.matcher import SignatureMatcher
        matcher = SignatureMatcher()
        assert matcher._jaccard_param_overlap({}, {}) == 0.0
