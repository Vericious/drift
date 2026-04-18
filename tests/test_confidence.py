"""Tests for confidence scoring (DRIFT-095)."""

import json

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


class TestTypeMatchFraction:
    """Tests for _type_match_fraction helper in SignatureMatcher."""

    def test_type_match_fraction_all_match(self):
        """All shared params with types match: returns 1.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y", type_annotation="str"),
            ],
        )
        claim = DocClaim(
            raw_text="foo(x: int, y: str)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y", type_annotation="str"),
            ],
        )
        assert matcher._type_match_fraction(fact, claim) == 1.0

    def test_type_match_fraction_partial_match(self):
        """Some params match: returns correct fraction."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y", type_annotation="str"),
            ],
        )
        claim = DocClaim(
            raw_text="foo(x: int, y: bool)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y", type_annotation="bool"),
            ],
        )
        # 1 out of 2 comparable params match = 0.5
        assert matcher._type_match_fraction(fact, claim) == 0.5

    def test_type_match_fraction_none_match(self):
        """No params match: returns 0.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y", type_annotation="str"),
            ],
        )
        claim = DocClaim(
            raw_text="foo(x: str, y: bool)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[
                Parameter(name="x", type_annotation="str"),
                Parameter(name="y", type_annotation="bool"),
            ],
        )
        assert matcher._type_match_fraction(fact, claim) == 0.0

    def test_type_match_fraction_ignores_missing_types(self):
        """Params without types on both sides are ignored."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y"),  # no type annotation
            ],
        )
        claim = DocClaim(
            raw_text="foo(x: int, y)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[
                Parameter(name="x", type_annotation="int"),
                Parameter(name="y"),  # no type annotation
            ],
        )
        # Only x is comparable (both have types); y is ignored
        # x matches, so 1/1 = 1.0
        assert matcher._type_match_fraction(fact, claim) == 1.0

    def test_type_match_fraction_no_comparable_params(self):
        """No params with types on both sides: returns 0.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("code.py"),
            line_number=10,
            parameters=[
                Parameter(name="x"),  # no type annotation
                Parameter(name="y"),  # no type annotation
            ],
        )
        claim = DocClaim(
            raw_text="foo(x, y)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="foo",
            parameters=[
                Parameter(name="x"),
                Parameter(name="y"),
            ],
        )
        # No params with types on both sides
        assert matcher._type_match_fraction(fact, claim) == 0.0


class TestLocationProximity:
    """Tests for _location_proximity helper in SignatureMatcher."""

    def test_location_proximity_same_dir(self):
        """Same directory: returns 1.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/foo.py"),
            line_number=10,
            parameters=[],
        )
        claim = DocClaim(
            raw_text="foo()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("src/docs.md"),
            line_number=1,
            name="foo",
            parameters=[],
        )
        assert matcher._location_proximity(fact, claim) == 1.0

    def test_location_proximity_sibling_dirs(self):
        """Sibling directories (common parent, different subdirs): returns 0.5."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/module/foo.py"),
            line_number=10,
            parameters=[],
        )
        claim = DocClaim(
            raw_text="foo()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("src/docs/api.md"),
            line_number=1,
            name="foo",
            parameters=[],
        )
        # src/module and src/docs share 'src' as common ancestor (depth=1)
        # max_depth=2, ratio=1/2=0.5
        result = matcher._location_proximity(fact, claim)
        assert result == 0.5

    def test_location_proximity_distant_paths(self):
        """Paths with only root in common: returns low score (0.2)."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("/home/user/project/src/foo.py"),
            line_number=10,
            parameters=[],
        )
        claim = DocClaim(
            raw_text="foo()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("/var/docs/api.md"),
            line_number=1,
            name="foo",
            parameters=[],
        )
        # /home/user/project/src and /var/docs share only '/' as common
        # common_length=1, max_depth=5, ratio=0.2
        result = matcher._location_proximity(fact, claim)
        assert result == 0.2

    def test_location_proximity_parent_child(self):
        """Parent-child relationship: returns high score (0.75)."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/foo.py"),
            line_number=10,
            parameters=[],
        )
        claim = DocClaim(
            raw_text="foo()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/api.md"),
            line_number=1,
            name="foo",
            parameters=[],
        )
        # src and docs share nothing common at start
        result = matcher._location_proximity(fact, claim)
        # They have '' as common (root), depth=0
        assert result == 0.0


class TestContextMatch:
    """Tests for _context_match helper in SignatureMatcher."""

    def test_context_match_same_module(self):
        """Same module: returns 1.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/module/foo.py"),
            line_number=10,
            parameters=[],
        )
        claim = DocClaim(
            raw_text="foo()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("src/module/docs.md"),
            line_number=1,
            name="foo",
            parameters=[],
        )
        # src/module vs src/module -> all parts overlap
        assert matcher._context_match(fact, claim) == 1.0

    def test_context_match_cross_module(self):
        """Different modules: returns fraction of overlapping path components."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/module_a/foo.py"),
            line_number=10,
            parameters=[],
        )
        claim = DocClaim(
            raw_text="foo()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("src/module_b/docs.md"),
            line_number=1,
            name="foo",
            parameters=[],
        )
        # src/module_a vs src/module_b
        # set('src', 'module_a') vs set('src', 'module_b')
        # overlap = {src} = 1, union = {src, module_a, module_b} = 3
        # ratio = 1/3 ≈ 0.333 (rounded to 3 decimal places)
        result = matcher._context_match(fact, claim)
        assert result == 0.333

    def test_context_match_no_overlap(self):
        """No path overlap: returns 0.0."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/alpha/foo.py"),
            line_number=10,
            parameters=[],
        )
        claim = DocClaim(
            raw_text="foo()",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/beta/readme.md"),
            line_number=1,
            name="foo",
            parameters=[],
        )
        # src/alpha vs docs/beta -> no overlap
        assert matcher._context_match(fact, claim) == 0.0


class TestConfidenceSignalsDocumentedButMissing:
    """Tests for ConfidenceSignals on documented_but_missing items."""

    def test_confidence_signals_documented_but_missing(self):
        """documented_but_missing items have all-zero ConfidenceSignals."""
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, DocClaim, Path
        matcher = SignatureMatcher()
        claim = DocClaim(
            raw_text="missing_func(x)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs.md"),
            line_number=1,
            name="missing_func",
            parameters=[],
        )
        items = matcher.match([], [claim])
        assert len(items) == 1
        item = items[0]
        assert item.category == "documented_but_missing"
        assert item.signals is not None
        assert item.signals.name_similarity == 0.0
        assert item.signals.param_overlap == 0.0
        assert item.signals.type_match == 0.0
        assert item.signals.location_proximity == 0.0
        assert item.signals.context_match == 0.0


class TestConfidenceJsonOutput:
    """Tests for JSON output including signals."""

    def test_confidence_json_output_signals(self):
        """JSON output includes signals dict with all signal fields."""
        import json
        from drift.matcher import SignatureMatcher
        from drift.models import ClaimKind, CodeFact, DocClaim, FactKind, Parameter, Path
        matcher = SignatureMatcher()
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/foo.py"),
            line_number=10,
            parameters=[Parameter(name="x", default="1")],
        )
        claim = DocClaim(
            raw_text="foo(x=0)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/api.md"),
            line_number=1,
            name="foo",
            parameters=[Parameter(name="x", default="0")],
        )
        items = matcher.match([fact], [claim])
        assert len(items) == 1
        item = items[0]
        # Verify signals dict has all required fields
        assert item.signals is not None
        signals_dict = item.signals.to_dict()
        assert "name_similarity" in signals_dict
        assert "param_overlap" in signals_dict
        assert "type_match" in signals_dict
        assert "location_proximity" in signals_dict
        assert "context_match" in signals_dict


class TestConfidenceSarifRank:
    """Tests for SARIF rank and signals in properties."""

    def test_confidence_sarif_rank(self):
        """SARIF rank = confidence * 100 in result properties."""
        from drift.models import (
            ClaimKind,
            CodeFact,
            ConfidenceSignals,
            DocClaim,
            DriftItem,
            DriftReport,
            FactKind,
            Parameter,
            Path,
            Severity,
        )
        from drift.reporter import DriftReporter

        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/foo.py"),
            line_number=10,
            parameters=[Parameter(name="x", default="1")],
        )
        signals = ConfidenceSignals(
            name_similarity=0.8,
            param_overlap=1.0,
            type_match=0.0,
            location_proximity=0.5,
            context_match=0.5,
        )
        item = DriftItem(
            fact=fact,
            severity=Severity.WARNING,
            category="wrong_default",
            message="Default mismatch",
            confidence=0.68,
            signals=signals,
        )
        report = DriftReport(scanned_path=Path("."), drift_items=[item])
        reporter = DriftReporter(report)
        parsed = json.loads(reporter.report_sarif())
        result = parsed["runs"][0]["results"][0]
        assert result["properties"]["rank"] == 68.0
        assert result["properties"]["confidence"] == {
            "name_similarity": 0.8,
            "param_overlap": 1.0,
            "type_match": 0.0,
            "location_proximity": 0.5,
            "context_match": 0.5,
        }
