"""
Tests for SignatureMatcher — compares CodeFact objects against DocClaim objects.
"""
from pathlib import Path

import pytest

from drift.models import (
    ClaimKind,
    CodeFact,
    DocClaim,
    DriftItem,
    FactKind,
    Parameter,
    Severity,
)
from drift.matcher import SignatureMatcher, build_report


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def fact(
    name: str,
    params: list[Parameter] | None = None,
    return_type: str | None = None,
) -> CodeFact:
    return CodeFact(
        name=name,
        kind=FactKind.FUNCTION,
        source_file=Path("test.py"),
        line_number=1,
        parameters=params or [],
        return_type=return_type,
    )


def claim(
    name: str,
    params: list[Parameter] | None = None,
    return_type: str | None = None,
) -> DocClaim:
    return DocClaim(
        raw_text=f"docs for {name}",
        kind=ClaimKind.FUNCTION_SIGNATURE,
        doc_file=Path("test.md"),
        line_number=1,
        name=name,
        parameters=params or [],
        return_type=return_type,
    )


def param(name: str, type_annotation: str | None = None, default: str | None = None) -> Parameter:
    return Parameter(name=name, type_annotation=type_annotation, default=default)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestExactMatch:
    def test_exact_match_empty_drift(self):
        """Exact match → empty drift items."""
        f = fact("foo", params=[param("x", "int"), param("y", "str", '"hello"')])
        c = claim("foo", params=[param("x", "int"), param("y", "str", '"hello"')])

        items = SignatureMatcher().match([f], [c])
        assert items == []

    def test_no_claims_no_drift(self):
        """No claims → undocumented items, not errors."""
        f = fact("foo")
        items = SignatureMatcher().match([f], [])
        assert len(items) == 1
        assert items[0].category == "undocumented"
        assert items[0].severity == Severity.WARNING


class TestMissingParam:
    def test_missing_param_in_docs(self):
        """Fact has parameter, claim doesn't → MISSING_PARAM, ERROR."""
        f = fact("foo", params=[param("x", "int"), param("y", "str", '"hello"')])
        c = claim("foo", params=[param("x", "int")])

        items = SignatureMatcher().match([f], [c])
        assert len(items) == 1
        assert items[0].category == "missing_param"
        assert items[0].severity == Severity.ERROR
        assert "y" in items[0].message
        assert items[0].fact == f
        assert items[0].claim == c


class TestExtraParam:
    def test_extra_param_in_docs(self):
        """Claim has parameter not in fact → EXTRA_PARAM, ERROR."""
        f = fact("foo", params=[param("x", "int")])
        c = claim("foo", params=[param("x", "int"), param("y", "str", '"hello"')])

        items = SignatureMatcher().match([f], [c])
        assert len(items) == 1
        assert items[0].category == "extra_param"
        assert items[0].severity == Severity.ERROR
        assert "y" in items[0].message


class TestWrongDefault:
    def test_wrong_default(self):
        """Both have param but defaults differ → WRONG_DEFAULT, WARNING."""
        f = fact("foo", params=[param("y", "str", '"hello"')])
        c = claim("foo", params=[param("y", "str", '"world"')])

        items = SignatureMatcher().match([f], [c])
        assert len(items) == 1
        assert items[0].category == "wrong_default"
        assert items[0].severity == Severity.WARNING
        assert '"hello"' in items[0].message or '"world"' in items[0].message


class TestWrongType:
    def test_wrong_type(self):
        """Both have param but types differ → WRONG_TYPE, WARNING."""
        f = fact("foo", params=[param("y", "int")])
        c = claim("foo", params=[param("y", "str")])

        items = SignatureMatcher().match([f], [c])
        assert len(items) == 1
        assert items[0].category == "wrong_type"
        assert items[0].severity == Severity.WARNING


class TestWrongReturnType:
    def test_wrong_return_type(self):
        """Fact and claim return types differ → WRONG_RETURN_TYPE, WARNING."""
        f = fact("foo", return_type="int")
        c = claim("foo", return_type="str")

        items = SignatureMatcher().match([f], [c])
        assert len(items) == 1
        assert items[0].category == "wrong_return_type"
        assert items[0].severity == Severity.WARNING


class TestRenamed:
    def test_renamed_same_signature(self):
        """Same signature structure but different names → RENAMED, ERROR."""
        f = fact("new_foo", params=[param("x", "int")])
        c = claim("old_foo", params=[param("x", "int")])

        items = SignatureMatcher().match([f], [c])
        renamed_items = [i for i in items if i.category == "renamed"]
        assert len(renamed_items) == 1
        assert renamed_items[0].severity == Severity.ERROR


class TestDocumentedButMissing:
    def test_documented_but_missing(self):
        """Claim exists but no matching fact → DOCUMENTED_BUT_MISSING, ERROR."""
        c = claim("ghost_func", params=[param("x", "int")])

        items = SignatureMatcher().match([], [c])
        assert len(items) == 1
        assert items[0].category == "documented_but_missing"
        assert items[0].severity == Severity.ERROR
        assert items[0].claim == c


class TestUndocumented:
    def test_undocumented(self):
        """Fact exists but no matching claim → UNDOCUMENTED, WARNING."""
        f = fact("undoc_func", params=[param("x", "int")])

        items = SignatureMatcher().match([f], [])
        assert len(items) == 1
        assert items[0].category == "undocumented"
        assert items[0].severity == Severity.WARNING
        assert items[0].fact == f


class TestBuildReport:
    def test_build_report_produces_correct_drift_report(self):
        """build_report produces correct DriftReport."""
        f = fact("foo", params=[param("x", "int")])
        c = claim("foo", params=[param("x", "int")])

        report = build_report([f], [c])

        assert report.scanned_path == Path(".")
        assert report.facts == [f]
        assert report.claims == [c]
        assert report.drift_items == []
        assert report.has_drift is False

    def test_build_report_with_drift(self):
        """build_report includes drift items."""
        f = fact("foo", params=[param("x", "int")])
        c = claim("ghost_func", params=[param("y", "int")])  # different param → not renamed

        report = build_report([f], [c])

        # ghost_func: different param names → documented_but_missing (no match)
        # foo: unmatched → undocumented
        assert len(report.drift_items) == 2
        assert report.has_drift is True


class TestHasDrift:
    def test_has_drift_false_when_no_error_severity_items(self):
        """has_drift is False when no ERROR-severity items (only warnings)."""
        f = fact("foo", params=[param("y", "str", '"hello"')])
        c = claim("foo", params=[param("y", "str", '"world"')])  # wrong default → WARNING

        items = SignatureMatcher().match([f], [c])
        assert len(items) == 1
        assert items[0].severity == Severity.WARNING

        report = build_report([f], [c])
        assert report.has_drift is False

    def test_has_drift_true_with_error_items(self):
        """has_drift is True when ERROR-severity items exist."""
        f = fact("foo", params=[param("x", "int"), param("y", "str")])
        c = claim("foo", params=[param("x", "int")])  # missing y → ERROR

        items = SignatureMatcher().match([f], [c])
        report = build_report([f], [c])
        assert report.has_drift is True


class TestUnqualifiedNameFallback:
    def test_unqualified_name_match(self):
        """Unqualified name fallback works when exact match fails."""
        f = fact("mymodule.my_func", params=[param("x", "int")])
        c = claim("my_func", params=[param("x", "int")])

        items = SignatureMatcher().match([f], [c])
        # Should match and produce no drift
        missing_param_items = [i for i in items if i.category == "missing_param"]
        assert missing_param_items == []


class TestMultipleDriftItems:
    def test_multiple_drift_items_from_single_claim(self):
        """Multiple drift items can be produced from a single claim-fact pair."""
        f = fact("foo", params=[param("x", "int", "0")], return_type="int")
        c = claim("foo", params=[param("x", "str", '"default"')])

        items = SignatureMatcher().match([f], [c])

        # Should have: wrong_type, wrong_default, wrong_return_type
        categories = {i.category for i in items}
        assert "wrong_type" in categories
        assert "wrong_default" in categories
        assert "wrong_return_type" in categories


class TestNoClaimName:
    def test_claim_with_no_name_is_skipped(self):
        """Claims with no name are skipped (no crash, no drift)."""
        c = DocClaim(
            raw_text="some prose",
            kind=ClaimKind.CODE_EXAMPLE,
            doc_file=Path("test.md"),
            line_number=1,
            name=None,
        )
        f = fact("foo")

        items = SignatureMatcher().match([f], [c])
        # Should only produce undocumented for the fact
        assert len(items) == 1
        assert items[0].category == "undocumented"


class TestFuzzyRenamed:
    """Tests for fuzzy name matching in SignatureMatcher."""

    def test_fuzzy_rename_above_threshold_same_signature(self):
        """Fuzzy name match + same signature → fuzzy_renamed, WARNING."""
        # get_user vs fetch_user are similar (fuzzy match)
        # same params → fuzzy_renamed
        f = fact("fetch_user", params=[param("user_id", "int")])
        c = claim("get_user", params=[param("user_id", "int")])

        items = SignatureMatcher().match([f], [c])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        assert fuzzy_items[0].severity == Severity.WARNING
        assert fuzzy_items[0].metadata.get("match_method") == "fuzzy"
        assert "confidence" in fuzzy_items[0].metadata

    def test_fuzzy_rename_below_threshold_stays_documented_but_missing(self):
        """Fuzzy name match below threshold → documented_but_missing, not fuzzy_renamed."""
        # "process" vs "calculate" are too different to fuzzy match
        f = fact("calculate", params=[param("x", "int")])
        c = claim("process", params=[param("x", "int")])

        items = SignatureMatcher().match([f], [c])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 0
        missing_items = [i for i in items if i.category == "documented_but_missing"]
        assert len(missing_items) == 1

    def test_fuzzy_rename_different_signature_no_match(self):
        """Fuzzy name match but different signatures → no fuzzy_renamed."""
        # Names similar but params differ
        f = fact("get_user", params=[param("x", "int")])
        c = claim("fetch_user", params=[param("x", "int"), param("name", "str")])

        items = SignatureMatcher().match([f], [c])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 0

    def test_fuzzy_rename_chooses_highest_confidence(self):
        """When multiple candidates match, highest confidence is chosen."""
        # get_user (claim) vs fetch_user (high similarity) vs get_user_details (lower similarity)
        f1 = fact("fetch_user", params=[param("id", "int")])
        f2 = fact("get_user_details", params=[param("id", "int")])
        c = claim("get_user", params=[param("id", "int")])

        # get_user should fuzzy-match fetch_user (high confidence) over get_user_details
        items = SignatureMatcher().match([f1, f2], [c])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        # Should match fetch_user (higher confidence) not get_user_details
        assert fuzzy_items[0].fact.name == "fetch_user"

    def test_exact_rename_takes_precedence_over_fuzzy(self):
        """Exact name match → renamed, not fuzzy_renamed (even if names differ)."""
        # exact rename detection takes precedence over fuzzy
        f = fact("new_get_user", params=[param("x", "int")])
        c = claim("new_get_user", params=[param("x", "int")])

        items = SignatureMatcher().match([f], [c])
        renamed_items = [i for i in items if i.category == "renamed"]
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(renamed_items) == 0  # exact match, no drift
        assert len(fuzzy_items) == 0

    def test_fuzzy_rename_metadata_has_confidence(self):
        """fuzzy_renamed items have confidence score in metadata."""
        f = fact("process_item", params=[param("x", "int")])
        c = claim("process_items", params=[param("x", "int")])

        items = SignatureMatcher().match([f], [c])
        fuzzy_items = [i for i in items if i.category == "fuzzy_renamed"]
        assert len(fuzzy_items) == 1
        confidence = fuzzy_items[0].metadata.get("confidence")
        assert isinstance(confidence, float)
        assert 0 <= confidence <= 100
