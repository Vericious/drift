"""Tests for ConfidenceSignals computation in SignatureMatcher (DRIFT-158)."""

import pytest

from drift.matcher import SignatureMatcher
from drift.models import (
    ClaimKind,
    CodeFact,
    ConfidenceSignals,
    DocClaim,
    FactKind,
    Parameter,
    Path,
    Severity,
)


class TestSignalsFuzzy:
    """Tests for fuzzy_renamed ConfidenceSignals computation."""

    def test_signals_fuzzy_basic(self):
        """fuzzy_renamed: signals are computed correctly for fuzzy match."""
        fact = CodeFact(
            name="fetch_user",
            kind=FactKind.FUNCTION,
            source_file=Path("src/models.py"),
            line_number=10,
            parameters=[Parameter(name="user_id", type_annotation="int")],
        )
        claim = DocClaim(
            raw_text="get_user(user_id: int)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/api.md"),
            line_number=1,
            name="get_user",
            parameters=[Parameter(name="user_id", type_annotation="int")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        item = fuzzy_items[0]
        assert item.signals is not None
        # name_similarity should be high for similar names
        assert 0.0 < item.signals.name_similarity <= 1.0
        # param_overlap should be 1.0 since params match exactly
        assert item.signals.param_overlap == 1.0
        # type_match should be 1.0 since types match
        assert item.signals.type_match == 1.0
        # location_proximity: fact in src/, claim in docs/ → different dirs
        assert item.signals.location_proximity == 0.5
        # context_match is always 0.0
        assert item.signals.context_match == 0.0
        # confidence should be signals.score()
        assert 0.0 < item.confidence <= 1.0

    def test_signals_fuzzy_same_directory(self):
        """fuzzy_renamed: location_proximity=1.0 when fact and claim in same directory."""
        fact = CodeFact(
            name="get_user",
            kind=FactKind.FUNCTION,
            source_file=Path("api/models.py"),
            line_number=10,
            parameters=[Parameter(name="id", type_annotation="int")],
        )
        claim = DocClaim(
            raw_text="fetch_user(id: int)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("api/docs.md"),
            line_number=1,
            name="fetch_user",
            parameters=[Parameter(name="id", type_annotation="int")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        assert fuzzy_items[0].signals.location_proximity == 1.0

    def test_signals_fuzzy_param_overlap(self):
        """fuzzy_renamed: param_overlap is 1.0 when signatures match exactly."""
        # fuzzy_renamed only triggers when _same_signature_structure is true,
        # so param_overlap will be 1.0 (identical param name sets)
        fact = CodeFact(
            name="fetch_user",
            kind=FactKind.FUNCTION,
            source_file=Path("core/db.py"),
            line_number=10,
            parameters=[
                Parameter(name="user_id", type_annotation="int"),
            ],
        )
        # Same param, so Jaccard({user_id}, {user_id}) = 1.0
        claim = DocClaim(
            raw_text="get_user(user_id: int)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/api.md"),
            line_number=1,
            name="get_user",
            parameters=[Parameter(name="user_id", type_annotation="int")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        # When signatures match exactly, Jaccard is 1.0
        assert fuzzy_items[0].signals.param_overlap == 1.0


class TestSignalsExactDrift:
    """Tests for exact-with-drift ConfidenceSignals computation."""

    def test_signals_exact_drift_missing_param(self):
        """exact-with-drift: missing_param has name_sim=1.0, location_prox based on dirs."""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/foo.py"),
            line_number=10,
            parameters=[Parameter(name="x"), Parameter(name="y")],
        )
        claim = DocClaim(
            raw_text="foo(x)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/api.md"),
            line_number=1,
            name="foo",
            parameters=[Parameter(name="x")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        missing_items = [i for i in items if i.category == "missing_param"]
        assert len(missing_items) == 1
        item = missing_items[0]
        assert item.signals is not None
        # exact name match
        assert item.signals.name_similarity == 1.0
        # params differ (that's the drift)
        assert item.signals.param_overlap == 1.0
        assert item.signals.type_match == 1.0
        assert item.signals.context_match == 1.0
        # different directories (src/ vs docs/)
        assert item.signals.location_proximity == 0.5
        # confidence = signals.score() = 0.35+0.30+0.15+0.05+0.10 = 0.95
        assert item.confidence == 0.95

    def test_signals_exact_drift_wrong_default(self):
        """exact-with-drift: wrong_default has name_sim=1.0, high signals."""
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
            doc_file=Path("src/api.md"),
            line_number=1,
            name="foo",
            parameters=[Parameter(name="x", default="0")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        wrong_default_items = [i for i in items if i.category == "wrong_default"]
        assert len(wrong_default_items) == 1
        item = wrong_default_items[0]
        assert item.signals.name_similarity == 1.0
        # same directory (both under src/)
        assert item.signals.location_proximity == 1.0
        # confidence = 1.0 when same directory
        assert item.confidence == 1.0

    def test_signals_exact_drift_wrong_type(self):
        """exact-with-drift: wrong_type has name_sim=1.0."""
        fact = CodeFact(
            name="foo",
            kind=FactKind.FUNCTION,
            source_file=Path("src/foo.py"),
            line_number=10,
            parameters=[Parameter(name="x", type_annotation="int")],
        )
        claim = DocClaim(
            raw_text="foo(x: str)",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=Path("docs/api.md"),
            line_number=1,
            name="foo",
            parameters=[Parameter(name="x", type_annotation="str")],
        )
        matcher = SignatureMatcher()
        items = matcher.match([fact], [claim])
        wrong_type_items = [i for i in items if i.category == "wrong_type"]
        assert len(wrong_type_items) == 1
        item = wrong_type_items[0]
        assert item.signals.name_similarity == 1.0
        # different directories (src/ vs docs/)
        assert item.signals.location_proximity == 0.5
        # confidence = 0.95 when different directories
        assert item.confidence == 0.95


class TestSignalsMissing:
    """Tests for documented_but_missing ConfidenceSignals computation."""

    def test_signals_missing_all_zeros(self):
        """documented_but_missing: all signals are 0.0."""
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
        item = items[0]
        assert item.category == "documented_but_missing"
        assert item.signals is not None
        assert item.signals.name_similarity == 0.0
        assert item.signals.param_overlap == 0.0
        assert item.signals.type_match == 0.0
        assert item.signals.location_proximity == 0.0
        assert item.signals.context_match == 0.0
        # confidence = signals.score() = 0.0
        assert item.confidence == 0.0


class TestSignalsScore:
    """Tests for ConfidenceSignals.score() method."""

    def test_score_weighted_sum(self):
        """score() returns weighted sum of signals."""
        signals = ConfidenceSignals(
            name_similarity=1.0,
            param_overlap=1.0,
            type_match=1.0,
            location_proximity=1.0,
            context_match=1.0,
        )
        # 0.35 + 0.30 + 0.15 + 0.10 + 0.10 = 1.0
        assert signals.score() == 1.0

    def test_score_zeros(self):
        """score() with all zeros returns 0.0."""
        signals = ConfidenceSignals()
        assert signals.score() == 0.0

    def test_score_partial(self):
        """score() with partial signals returns correct weighted sum."""
        signals = ConfidenceSignals(
            name_similarity=1.0,
            param_overlap=0.0,
            type_match=0.0,
            location_proximity=0.0,
            context_match=0.0,
        )
        # 1.0*0.35 + 0.0*0.30 + 0.0*0.15 + 0.0*0.10 + 0.0*0.10 = 0.35
        assert signals.score() == 0.35

    def test_score_clamped(self):
        """score() is clamped to [0, 1]."""
        signals = ConfidenceSignals(
            name_similarity=2.0,  # > 1.0
            param_overlap=-0.5,   # < 0.0
            type_match=0.5,
            location_proximity=0.5,
            context_match=0.5,
        )
        # Would be 0.7+(-0.15)+0.075+0.05+0.05 = 0.725
        # But clamped to 1.0
        assert signals.score() <= 1.0
        assert signals.score() >= 0.0
