"""Tests for the GraphQLExtractor."""

import os
import tempfile
from pathlib import Path

from drift.extractors.graphql import GraphQLExtractor
from drift.models import CodeFact, FactKind
from tests.fixtures.sample_schema import (
    SAMPLE_INTERFACE_ONLY,
    SAMPLE_MINIMAL_UNION,
    SAMPLE_SCALAR_ONLY,
    SAMPLE_UNION_INTERFACE_SCHEMA,
)


class TestGraphQLExtractorCanHandle:
    """Tests for can_handle method."""

    def test_handles_graphql_suffix(self):
        path = Path("schema.graphql")
        assert GraphQLExtractor().can_handle(path) is True

    def test_handles_gql_suffix(self):
        path = Path("schema.gql")
        assert GraphQLExtractor().can_handle(path) is True

    def test_rejects_other_files(self):
        path = Path("schema.json")
        assert GraphQLExtractor().can_handle(path) is False

        path = Path("schema.sql")
        assert GraphQLExtractor().can_handle(path) is False

    def test_handles_case_insensitive(self):
        path = Path("schema.GRAPHQL")
        assert GraphQLExtractor().can_handle(path) is True


class TestUnionExtraction:
    """Tests for union type extraction."""

    def _extract(self, content: bytes) -> list[CodeFact]:
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".graphql", delete=False
        ) as f:
            f.write(content)
            temp_path = Path(f.name)
        try:
            return GraphQLExtractor().extract(temp_path)
        finally:
            os.unlink(temp_path)

    def test_extracts_union_type(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        names = {f.name for f in facts}
        assert "graphql.SearchResult" in names

    def test_union_member_types_in_metadata(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        search_fact = next(f for f in facts if f.name == "graphql.SearchResult")
        assert search_fact.metadata["graphql_kind"] == "union"
        assert "User" in search_fact.metadata["member_types"]
        assert "Post" in search_fact.metadata["member_types"]
        assert "Comment" in search_fact.metadata["member_types"]

    def test_minimal_union(self):
        facts = self._extract(SAMPLE_MINIMAL_UNION)
        names = {f.name for f in facts}
        assert "graphql.SearchResult" in names
        search_fact = next(f for f in facts if f.name == "graphql.SearchResult")
        assert search_fact.metadata["member_types"] == ["User", "Post"]

    def test_union_kind_is_class(self):
        facts = self._extract(SAMPLE_MINIMAL_UNION)
        search_fact = next(f for f in facts if f.name == "graphql.SearchResult")
        assert search_fact.kind == FactKind.CLASS

    def test_union_has_source_file(self):
        facts = self._extract(SAMPLE_MINIMAL_UNION)
        search_fact = next(f for f in facts if f.name == "graphql.SearchResult")
        assert search_fact.source_file is not None


class TestInterfaceExtraction:
    """Tests for interface type extraction."""

    def _extract(self, content: bytes) -> list[CodeFact]:
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".graphql", delete=False
        ) as f:
            f.write(content)
            temp_path = Path(f.name)
        try:
            return GraphQLExtractor().extract(temp_path)
        finally:
            os.unlink(temp_path)

    def test_extracts_interface_type(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        names = {f.name for f in facts}
        assert "graphql.Node" in names
        assert "graphql.Timestamped" in names

    def test_interface_metadata_has_fields(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        node_fact = next(f for f in facts if f.name == "graphql.Node")
        assert node_fact.metadata["graphql_kind"] == "interface"
        assert "fields" in node_fact.metadata

    def test_interface_fields_parsed(self):
        facts = self._extract(SAMPLE_INTERFACE_ONLY)
        node_fact = next(f for f in facts if f.name == "graphql.Node")
        fields = node_fact.metadata["fields"]
        assert len(fields) == 1
        assert fields[0]["name"] == "id"
        assert fields[0]["type_annotation"] == "ID!"

    def test_interface_implements_listed(self):
        facts = self._extract(SAMPLE_INTERFACE_ONLY)
        node_fact = next(f for f in facts if f.name == "graphql.Node")
        # Node is an interface, doesn't implement anything itself
        # (User implements Node, but that's User's metadata, not Node's)
        assert "implements" in node_fact.metadata

    def test_interface_kind_is_class(self):
        facts = self._extract(SAMPLE_INTERFACE_ONLY)
        node_fact = next(f for f in facts if f.name == "graphql.Node")
        assert node_fact.kind == FactKind.CLASS


class TestScalarExtraction:
    """Tests for scalar type extraction."""

    def _extract(self, content: bytes) -> list[CodeFact]:
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".graphql", delete=False
        ) as f:
            f.write(content)
            temp_path = Path(f.name)
        try:
            return GraphQLExtractor().extract(temp_path)
        finally:
            os.unlink(temp_path)

    def test_extracts_scalar_types(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        names = {f.name for f in facts}
        assert "graphql.DateTime" in names
        assert "graphql.URL" in names
        assert "graphql.JSON" in names

    def test_scalar_metadata(self):
        facts = self._extract(SAMPLE_SCALAR_ONLY)
        datetime_fact = next(f for f in facts if f.name == "graphql.DateTime")
        assert datetime_fact.metadata["graphql_kind"] == "scalar"
        assert datetime_fact.kind == FactKind.CLASS

    def test_multiple_scalars(self):
        facts = self._extract(SAMPLE_SCALAR_ONLY)
        scalar_facts = [f for f in facts if f.metadata.get("graphql_kind") == "scalar"]
        assert len(scalar_facts) == 2

    def test_scalar_has_source_file(self):
        facts = self._extract(SAMPLE_SCALAR_ONLY)
        datetime_fact = next(f for f in facts if f.name == "graphql.DateTime")
        assert datetime_fact.source_file is not None


class TestEdgeCases:
    """Tests for edge cases."""

    def _extract(self, content: bytes) -> list[CodeFact]:
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".graphql", delete=False
        ) as f:
            f.write(content)
            temp_path = Path(f.name)
        try:
            return GraphQLExtractor().extract(temp_path)
        finally:
            os.unlink(temp_path)

    def test_empty_schema_no_type_definitions(self):
        """A schema with only comments should produce no facts."""
        content = b"""
# Just a comment
"""
        facts = self._extract(content)
        assert facts == []

    def test_invalid_file_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".graphql", delete=False
        ) as f:
            f.write(b"not graphql at all")
            temp_path = Path(f.name)
        try:
            facts = GraphQLExtractor().extract(temp_path)
        finally:
            os.unlink(temp_path)
        assert facts == []

    def test_union_without_pipe(self):
        """Test union with single type (valid GraphQL)."""
        content = b"""
union SingleUnion = User

type User {
    id: ID!
}
"""
        facts = self._extract(content)
        names = {f.name for f in facts}
        assert "graphql.SingleUnion" in names
        single_fact = next(f for f in facts if f.name == "graphql.SingleUnion")
        assert single_fact.metadata["member_types"] == ["User"]

    def test_interface_without_implements(self):
        """Test interface without implements clause."""
        content = b"""
interface SimpleInterface {
    id: ID!
    name: String
}
"""
        facts = self._extract(content)
        names = {f.name for f in facts}
        assert "graphql.SimpleInterface" in names
        simple_fact = next(f for f in facts if f.name == "graphql.SimpleInterface")
        assert simple_fact.metadata["graphql_kind"] == "interface"


class TestGraphQLExtractorIntegration:
    """Integration tests."""

    def _extract(self, content: bytes) -> list[CodeFact]:
        with tempfile.NamedTemporaryFile(
            "wb", suffix=".graphql", delete=False
        ) as f:
            f.write(content)
            temp_path = Path(f.name)
        try:
            return GraphQLExtractor().extract(temp_path)
        finally:
            os.unlink(temp_path)

    def test_full_schema_includes_all_type_kinds(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        kinds = {f.metadata.get("graphql_kind") for f in facts}
        assert "union" in kinds
        assert "interface" in kinds
        assert "scalar" in kinds

    def test_extractor_registered(self):
        """Test that the extractor is registered."""
        from drift.extractors.registry import get_extractors
        extractors = get_extractors()
        gql_extractors = [e for e in extractors if e.__name__ == "GraphQLExtractor"]
        assert len(gql_extractors) == 1

    def test_source_file_set_on_all_facts(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        for fact in facts:
            assert fact.source_file is not None

    def test_line_number_set(self):
        facts = self._extract(SAMPLE_UNION_INTERFACE_SCHEMA)
        for fact in facts:
            assert fact.line_number > 0
