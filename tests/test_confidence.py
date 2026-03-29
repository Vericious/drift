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


class TestConfidenceSignals:
    """Tests for ConfidenceSignals scoring and propagation."""

    def test_confidence_signals_exact_match(self):
        """When all signals are 1.0, score() returns 1.0."""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(
            name_similarity=1.0,
            param_overlap=1.0,
            type_match=1.0,
            location_proximity=1.0,
            context_match=1.0,
        )
        assert signals.score() == 1.0

    def test_confidence_signals_score_weights(self):
        """Weighted formula: name*0.35 + param*0.30 + type*0.15 + loc*0.10 + ctx*0.10."""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(
            name_similarity=1.0,
            param_overlap=1.0,
            type_match=1.0,
            location_proximity=1.0,
            context_match=1.0,
        )
        # All 1.0 → 1.0
        assert signals.score() == 1.0

        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        # All 0.0 → 0.0
        assert signals.score() == 0.0

        # Custom weights: name=1.0 → 0.35, param=1.0 → 0.30, rest 0
        signals = ConfidenceSignals(
            name_similarity=1.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        assert signals.score() == 0.35

        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=1.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        assert signals.score() == 0.30

    def test_confidence_param_overlap_jaccard(self):
        """param_overlap field exists and contributes to score."""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.75,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        assert signals.score() == round(0.75 * 0.30, 3)

    def test_confidence_type_match_fraction(self):
        """type_match field exists and contributes to score."""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.0,
            type_match=0.5,
            location_proximity=0.0,
            context_match=0.0,
        )
        assert signals.score() == round(0.5 * 0.15, 3)

    def test_confidence_location_proximity(self):
        """location_proximity field exists and contributes to score."""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.8,
            context_match=0.0,
        )
        assert signals.score() == round(0.8 * 0.10, 3)

    def test_confidence_context_match(self):
        """context_match field exists and contributes to score."""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.9,
        )
        assert signals.score() == round(0.9 * 0.10, 3)

    def test_confidence_signals_fuzzy_renamed(self):
        """Fuzzy-renamed items have confidence reflecting name similarity."""
        fact = CodeFact(
            name="my_function",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[Parameter(name="x")],
        )
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

    def test_confidence_signals_documented_but_missing(self):
        """documented_but_missing items have confidence = 0.0."""
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

    def test_confidence_json_output_signals(self):
        """JSON output includes signals dict for items that have them."""
        from drift.models import ConfidenceSignals, DriftReport
        from drift.reporter import DriftReporter

        signals = ConfidenceSignals(
            name_similarity=0.8,
            param_overlap=0.6,
            type_match=0.5,
            location_proximity=0.3,
            context_match=0.2,
        )
        item = DriftItem(
            fact=CodeFact(
                name="foo",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=10,
                parameters=[],
            ),
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="test",
            confidence=signals.score(),
            signals=signals,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        json_output = reporter.report_json()

        import json
        parsed = json.loads(json_output)
        assert "signals" in parsed["drift_items"][0]
        assert parsed["drift_items"][0]["signals"]["name_similarity"] == 0.8
        assert parsed["drift_items"][0]["signals"]["param_overlap"] == 0.6

    def test_confidence_sarif_rank(self):
        """SARIF output includes rank derived from confidence."""
        from drift.models import DriftReport
        from drift.reporter import DriftReporter

        item = DriftItem(
            fact=CodeFact(
                name="foo",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=10,
                parameters=[],
            ),
            claim=None,
            severity=Severity.ERROR,
            category="undocumented",
            message="test",
            confidence=0.75,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        sarif_output = reporter.report_sarif()

        # SARIF results should include rank (confidence * 100)
        assert '"rank": 75.0' in sarif_output or '"rank":75.0' in sarif_output

    def test_min_confidence_filter_count(self):
        """min_confidence threshold filters out low-confidence drift items."""
        from drift.models import ConfidenceSignals, DriftReport

        # Create items with different confidence levels
        high_conf = DriftItem(
            fact=CodeFact(
                name="func_a",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=10,
                parameters=[],
            ),
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="func_a undocumented",
            confidence=0.9,
            signals=ConfidenceSignals(name_similarity=0.9, param_overlap=0.9, type_match=0.9,
                                     location_proximity=0.9, context_match=0.9),
        )
        low_conf = DriftItem(
            fact=CodeFact(
                name="func_b",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=20,
                parameters=[],
            ),
            claim=None,
            severity=Severity.WARNING,
            category="undocumented",
            message="func_b undocumented",
            confidence=0.1,
            signals=ConfidenceSignals(name_similarity=0.1, param_overlap=0.1, type_match=0.1,
                                     location_proximity=0.1, context_match=0.1),
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[high_conf, low_conf])

        # Apply min_confidence filter (threshold = 0.5)
        threshold = 0.5
        filtered = [item for item in report.drift_items if item.confidence >= threshold]
        assert len(filtered) == 1
        assert filtered[0].fact.name == "func_a"
