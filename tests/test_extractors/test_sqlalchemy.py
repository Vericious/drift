"""Tests for sqlalchemy module."""

from pathlib import Path

from drift.extractors.sqlalchemy import SQLAlchemyExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_sqlalchemy.py"


class TestSQLAlchemyExtractor:
    """Test SQLAlchemyExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = SQLAlchemyExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False
        assert extractor.can_handle(Path("foo.pyx")) is False

    def test_extracts_table_schema_facts(self):
        """Extracts TABLE_SCHEMA facts from the fixture."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        table_facts = [f for f in facts if f.kind.value == "table_schema"]
        assert len(table_facts) > 0

    def test_kind_is_table_schema(self):
        """All extracted facts have kind=table_schema."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "table_schema" for f in facts)

    def test_fact_name_format_tablename_columnname(self):
        """Fact names follow 'table_name.column_name' format."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # Should have users.id, users.email, posts.title, etc.
        assert any("." in name for name in names)

    def test_users_table_columns_extracted(self):
        """Users table columns are extracted."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        user_cols = [f for f in facts if f.metadata.get("table") == "users"]
        assert len(user_cols) > 0

    def test_posts_table_columns_extracted(self):
        """Posts table columns are extracted."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        post_cols = [f for f in facts if f.metadata.get("table") == "posts"]
        assert len(post_cols) > 0

    def test_primary_key_detected(self):
        """Primary key columns are detected in metadata."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        pk_facts = [f for f in facts if f.metadata.get("primary_key")]
        assert len(pk_facts) > 0

    def test_nullable_detected(self):
        """Nullable columns are detected in metadata."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        nullable_facts = [f for f in facts if f.metadata.get("nullable") is not None
                         and not f.metadata.get("primary_key")]
        assert len(nullable_facts) > 0

    def test_foreign_key_detected(self):
        """Foreign key columns are detected in metadata."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        fk_facts = [f for f in facts if f.metadata.get("foreign_key")]
        assert len(fk_facts) > 0

    def test_index_detected(self):
        """Indexed columns are detected in metadata."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        indexed_facts = [f for f in facts if f.metadata.get("index")]
        assert len(indexed_facts) > 0

    def test_relationship_extracted(self):
        """Relationship columns are extracted with is_relationship=True."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        rel_facts = [f for f in facts if f.metadata.get("is_relationship")]
        assert len(rel_facts) > 0

    def test_relationship_target_extracted(self):
        """Relationship target is extracted in metadata."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        rel_facts = [f for f in facts if f.metadata.get("is_relationship")]
        targets = [f.metadata.get("relationship_target") for f in rel_facts]
        assert any(t is not None for t in targets)

    def test_multiple_tables_extracted(self):
        """Multiple tables (users, posts, comments) are extracted."""
        extractor = SQLAlchemyExtractor()
        facts = extractor.extract(FIXTURE)
        tables = {f.metadata.get("table") for f in facts}
        assert "users" in tables
        assert "posts" in tables
        assert "comments" in tables
