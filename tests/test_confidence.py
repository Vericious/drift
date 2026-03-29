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
    """Test ConfidenceSignals weighted scoring."""

    def test_confidence_signals_exact_match(self):
        """All signals = 1.0 should give score = 1.0"""
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
        """Score uses correct weights: name=0.35, param=0.30, type=0.15, loc=0.10, ctx=0.10"""
        from drift.models import ConfidenceSignals

        # Only name_similarity = 1.0
        signals = ConfidenceSignals(name_similarity=1.0)
        assert signals.score() == 0.35

        # Only param_overlap = 1.0
        signals = ConfidenceSignals(param_overlap=1.0)
        assert signals.score() == 0.30

        # Only type_match = 1.0
        signals = ConfidenceSignals(type_match=1.0)
        assert signals.score() == 0.15

        # Only location_proximity = 1.0
        signals = ConfidenceSignals(location_proximity=1.0)
        assert signals.score() == 0.10

        # Only context_match = 1.0
        signals = ConfidenceSignals(context_match=1.0)
        assert signals.score() == 0.10

    def test_confidence_param_overlap_jaccard(self):
        """param_overlap should use Jaccard similarity: |intersection| / |union|"""
        from drift.models import ConfidenceSignals

        # 2 common params, 1 unique to each -> Jaccard = 2/3
        signals = ConfidenceSignals(param_overlap=2 / 3)
        # Score from param_overlap alone would be 0.30 * (2/3) = 0.20
        assert signals.score() == 0.20

    def test_confidence_type_match_fraction(self):
        """type_match signal directly influences score by 0.15 weight"""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(type_match=0.5)
        # Score = 0.5 * 0.15 = 0.075
        assert signals.score() == 0.075

    def test_confidence_location_proximity(self):
        """location_proximity signal should reflect how close fact and claim are"""
        from drift.models import ConfidenceSignals

        # Perfect proximity
        signals = ConfidenceSignals(location_proximity=1.0)
        assert signals.score() == 0.10

        # No proximity
        signals = ConfidenceSignals(location_proximity=0.0)
        assert signals.score() == 0.0

    def test_confidence_context_match(self):
        """context_match signal reflects doc vs code context alignment"""
        from drift.models import ConfidenceSignals

        signals = ConfidenceSignals(context_match=1.0)
        assert signals.score() == 0.10

        signals = ConfidenceSignals(context_match=0.5)
        assert signals.score() == 0.05

    def test_confidence_json_output_signals(self):
        """JSON output should include confidence signals"""
        import json
        from drift.models import ConfidenceSignals, DriftReport
        from drift.reporter import DriftReporter

        item = DriftItem(
            fact=CodeFact(
                name="foo",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=10,
                parameters=[Parameter(name="x")],
            ),
            claim=DocClaim(
                raw_text="foo(x)",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path("docs.md"),
                line_number=5,
                name="foo",
                parameters=[Parameter(name="x")],
            ),
            severity=Severity.WARNING,
            category="test",
            message="test",
            signals=ConfidenceSignals(
                name_similarity=1.0,
                param_overlap=1.0,
                type_match=1.0,
                location_proximity=1.0,
                context_match=1.0,
            ),
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        json_output = DriftReporter(report).report_json()

        assert "signals" in json_output
        data = json.loads(json_output)
        assert "signals" in data["drift_items"][0]
        sigs = data["drift_items"][0]["signals"]
        assert sigs["name_similarity"] == 1.0
        assert sigs["param_overlap"] == 1.0

    def test_confidence_sarif_rank(self):
        """SARIF output should include confidence as ranking property"""
        import json
        from drift.models import ConfidenceSignals, DriftReport
        from drift.reporter import DriftReporter

        item = DriftItem(
            fact=CodeFact(
                name="foo",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=10,
                parameters=[Parameter(name="x")],
            ),
            claim=DocClaim(
                raw_text="foo(x)",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path("docs.md"),
                line_number=5,
                name="foo",
                parameters=[Parameter(name="x")],
            ),
            severity=Severity.WARNING,
            category="test",
            message="test",
            confidence=0.85,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        sarif_output = DriftReporter(report).report_sarif()

        data = json.loads(sarif_output)
        # Check that results have rankings or confidence properties
        results = data["runs"][0]["results"]
        assert len(results) == 1
        assert results[0].get("confidence") == 0.85 or "rank" in results[0]

    def test_min_confidence_filter_count(self):
        """Reporter should include all items regardless of confidence in diff output"""
        import json
        from drift.reporter import DriftReporter
        from drift.models import ConfidenceSignals, DriftReport

        # Create items with different confidence scores
        high_conf = DriftItem(
            fact=CodeFact(
                name="func_a",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=10,
                parameters=[Parameter(name="x")],
            ),
            claim=DocClaim(
                raw_text="func_a(x)",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path("docs.md"),
                line_number=5,
                name="func_a",
                parameters=[Parameter(name="x")],
            ),
            severity=Severity.WARNING,
            category="test",
            message="high confidence",
            confidence=0.9,
        )
        low_conf = DriftItem(
            fact=CodeFact(
                name="func_b",
                kind=FactKind.FUNCTION,
                source_file=Path("code.py"),
                line_number=20,
                parameters=[Parameter(name="y")],
            ),
            claim=DocClaim(
                raw_text="func_b(y)",
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=Path("docs.md"),
                line_number=15,
                name="func_b",
                parameters=[Parameter(name="y")],
            ),
            severity=Severity.WARNING,
            category="test",
            message="low confidence",
            confidence=0.3,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[high_conf, low_conf])
        reporter = DriftReporter(report)

        # Both items should appear in the diff output (by message content)
        diff_output = reporter.report_diff()
        assert "high confidence" in diff_output
        assert "low confidence" in diff_output

        # JSON output should also include both items with their confidences
        json_output = DriftReporter(report).report_json()
        data = json.loads(json_output)
        assert len(data["drift_items"]) == 2
        confidences = {item["message"]: item["confidence"] for item in data["drift_items"]}
        assert confidences["high confidence"] == 0.9
        assert confidences["low confidence"] == 0.3

    def test_confidence_signals_fuzzy_renamed(self):
        """Fuzzy renamed function has reduced name_similarity but full param match."""
        from drift.models import ConfidenceSignals

        # When a function is renamed (e.g., get_user -> fetch_user),
        # name_similarity might be 0.6 but params still match
        signals = ConfidenceSignals(
            name_similarity=0.6,
            param_overlap=1.0,
            type_match=1.0,
            location_proximity=1.0,
            context_match=1.0,
        )
        # Score = 0.6*0.35 + 1.0*0.30 + 1.0*0.15 + 1.0*0.10 + 1.0*0.10
        #       = 0.21 + 0.30 + 0.15 + 0.10 + 0.10 = 0.86
        assert signals.score() == 0.86

    def test_confidence_signals_documented_but_missing(self):
        """Documented but missing function has low name_similarity and no param overlap."""
        from drift.models import ConfidenceSignals

        # When a function is documented but missing from code,
        # we have no fact to compare against, so signals are minimal
        signals = ConfidenceSignals(
            name_similarity=0.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        assert signals.score() == 0.0
