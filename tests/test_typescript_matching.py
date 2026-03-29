"""Tests for TypeScript interface/type/enum matching in SignatureMatcher."""

from pathlib import Path

import pytest

from drift.extractors.typescript import TypeScriptExtractor
from drift.matcher import SignatureMatcher
from drift.models import (
    ClaimKind,
    CodeFact,
    DocClaim,
    FactKind,
    Parameter,
)


class TestTSInterfaceMatching:
    """Test TS interface/type/enum matching."""

    def test_ts_interface_match(self):
        """Interface claim matches TS fact when all properties documented."""
        # TS fact from code
        fact = CodeFact(
            name="User",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="id", type_annotation="number"),
                Parameter(name="name", type_annotation="string"),
                Parameter(name="email", type_annotation="string"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

        # TS claim from docs (property table for User interface)
        claims = [
            DocClaim(
                raw_text="id",
                kind=ClaimKind.TS_INTERFACE_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="id",
                parameters=[
                    Parameter(name="id", type_annotation="number"),
                    Parameter(name="name", type_annotation="string"),
                    Parameter(name="email", type_annotation="string"),
                ],
                metadata={"parent_type": "User", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        # No drift — all properties match
        assert len(items) == 0

    def test_ts_property_missing(self):
        """Claim has property not in fact → extra_param ERROR."""
        # TS fact with only 'id' property
        fact = CodeFact(
            name="User",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[Parameter(name="id", type_annotation="number")],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

        # Claim documents 'id' AND 'email', but fact only has 'id'
        claims = [
            DocClaim(
                raw_text="email",
                kind=ClaimKind.TS_INTERFACE_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="email",
                parameters=[
                    Parameter(name="id", type_annotation="number"),
                    Parameter(name="email", type_annotation="string"),
                ],
                metadata={"parent_type": "User", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        extra_items = [i for i in items if i.category == "extra_param"]
        assert len(extra_items) == 1
        assert extra_items[0].severity.name == "ERROR"
        assert "email" in extra_items[0].message

    def test_ts_property_extra(self):
        """Fact has property not in claim → missing_param ERROR."""
        # TS fact with 'id', 'name', 'email' properties
        fact = CodeFact(
            name="User",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="id", type_annotation="number"),
                Parameter(name="name", type_annotation="string"),
                Parameter(name="email", type_annotation="string"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

        # Claim only documents 'id'
        claims = [
            DocClaim(
                raw_text="id",
                kind=ClaimKind.TS_INTERFACE_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="id",
                parameters=[Parameter(name="id", type_annotation="number")],
                metadata={"parent_type": "User", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        missing_items = [i for i in items if i.category == "missing_param"]
        assert len(missing_items) == 2  # 'name' and 'email' missing from docs
        assert all(i.severity.name == "ERROR" for i in missing_items)
