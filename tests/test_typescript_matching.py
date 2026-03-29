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

    def test_ts_interface_exact_match(self):
        """Interface claim matches TS fact when all properties documented."""
        fact = CodeFact(
            name="User",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="id", type_annotation="number"),
                Parameter(name="name", type_annotation="string"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

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
                ],
                metadata={"parent_type": "User", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)
        assert len(items) == 0

    def test_ts_interface_missing_property(self):
        """Fact has property not in claim → missing_param ERROR."""
        fact = CodeFact(
            name="User",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="id", type_annotation="number"),
                Parameter(name="name", type_annotation="string"),
                Parameter(name="age", type_annotation="number"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

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
                ],
                metadata={"parent_type": "User", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        missing_items = [i for i in items if i.category == "missing_param"]
        assert len(missing_items) == 1
        assert missing_items[0].severity.name == "ERROR"
        assert "age" in missing_items[0].message

    def test_ts_interface_extra_property(self):
        """Claim has property not in fact → extra_param ERROR."""
        fact = CodeFact(
            name="User",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="id", type_annotation="number"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

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
                ],
                metadata={"parent_type": "User", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        extra_items = [i for i in items if i.category == "extra_param"]
        assert len(extra_items) == 1
        assert extra_items[0].severity.name == "ERROR"
        assert "name" in extra_items[0].message

    def test_ts_type_alias_match(self):
        """Type alias claim matches TS_TYPE fact when all properties documented."""
        fact = CodeFact(
            name="UserId",
            kind=FactKind.TS_TYPE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="value", type_annotation="number"),
            ],
            metadata={"ts_kind": "TS_TYPE"},
        )

        claims = [
            DocClaim(
                raw_text="value",
                kind=ClaimKind.TS_TYPE_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="value",
                parameters=[
                    Parameter(name="value", type_annotation="number"),
                ],
                metadata={"parent_type": "UserId", "ts_kind": "TS_TYPE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)
        assert len(items) == 0

    def test_ts_enum_match(self):
        """Enum claim matches TS_ENUM fact when all members documented."""
        fact = CodeFact(
            name="Status",
            kind=FactKind.TS_ENUM,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="ACTIVE", type_annotation="string"),
                Parameter(name="INACTIVE", type_annotation="string"),
            ],
            metadata={"ts_kind": "TS_ENUM"},
        )

        claims = [
            DocClaim(
                raw_text="ACTIVE",
                kind=ClaimKind.TS_ENUM_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="ACTIVE",
                parameters=[
                    Parameter(name="ACTIVE", type_annotation="string"),
                    Parameter(name="INACTIVE", type_annotation="string"),
                ],
                metadata={"parent_type": "Status", "ts_kind": "TS_ENUM"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)
        assert len(items) == 0

    def test_ts_enum_missing_member(self):
        """Claim has enum member not in fact → extra_param ERROR."""
        fact = CodeFact(
            name="Status",
            kind=FactKind.TS_ENUM,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="ACTIVE", type_annotation="string"),
            ],
            metadata={"ts_kind": "TS_ENUM"},
        )

        claims = [
            DocClaim(
                raw_text="ACTIVE",
                kind=ClaimKind.TS_ENUM_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="ACTIVE",
                parameters=[
                    Parameter(name="ACTIVE", type_annotation="string"),
                    Parameter(name="INACTIVE", type_annotation="string"),
                ],
                metadata={"parent_type": "Status", "ts_kind": "TS_ENUM"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        extra_items = [i for i in items if i.category == "extra_param"]
        assert len(extra_items) == 1
        assert extra_items[0].severity.name == "ERROR"
        assert "INACTIVE" in extra_items[0].message

    def test_ts_interface_renamed(self):
        """Interface claim for 'User' but fact is 'UserRecord' → documented_but_missing + undocumented."""
        fact = CodeFact(
            name="UserRecord",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="id", type_annotation="number"),
                Parameter(name="name", type_annotation="string"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

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
                ],
                metadata={"parent_type": "User", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        # TS interface refs match by parent_type exactly - no fuzzy matching
        # So "User" claim won't match "UserRecord" fact
        categories = {i.category for i in items}
        assert "documented_but_missing" in categories
        assert "undocumented" in categories

    def test_ts_code_block_in_md(self):
        """TS code block claim in markdown is processed correctly."""
        fact = CodeFact(
            name="Config",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="debug", type_annotation="boolean"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

        claims = [
            DocClaim(
                raw_text="debug",
                kind=ClaimKind.TS_INTERFACE_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="debug",
                parameters=[
                    Parameter(name="debug", type_annotation="boolean"),
                ],
                metadata={"parent_type": "Config", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)
        assert len(items) == 0

    def test_ts_property_table_in_md(self):
        """TS property table in markdown is processed correctly."""
        fact = CodeFact(
            name="Options",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="timeout", type_annotation="number"),
                Parameter(name="retries", type_annotation="number"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

        claims = [
            DocClaim(
                raw_text="timeout",
                kind=ClaimKind.TS_INTERFACE_REF,
                doc_file=Path("docs.md"),
                line_number=10,
                name="timeout",
                parameters=[
                    Parameter(name="timeout", type_annotation="number"),
                    Parameter(name="retries", type_annotation="number"),
                ],
                metadata={"parent_type": "Options", "ts_kind": "TS_INTERFACE"},
            ),
        ]

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)
        assert len(items) == 0

    def test_ts_undocumented_interface(self):
        """TS interface fact with no matching claim → undocumented."""
        fact = CodeFact(
            name="HiddenConfig",
            kind=FactKind.TS_INTERFACE,
            source_file=Path("types.ts"),
            line_number=1,
            parameters=[
                Parameter(name="secret", type_annotation="string"),
            ],
            metadata={"ts_kind": "TS_INTERFACE"},
        )

        claims: list[DocClaim] = []

        matcher = SignatureMatcher()
        items = matcher.match([fact], claims)

        undocumented = [i for i in items if i.category == "undocumented"]
        assert len(undocumented) == 1
        assert "HiddenConfig" in undocumented[0].message
