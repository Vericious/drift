"""Tests for pydantic module."""
from pathlib import Path

import pytest

from drift.extractors.pydantic import PydanticExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_settings.py"


class TestPydanticExtractor:
    """Test PydanticExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = PydanticExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_at_least_six_facts(self):
        """Extracts 6+ facts from the fixture."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        assert len(facts) >= 6

    def test_fact_names_follow_classname_dot_field_pattern(self):
        """Fact names follow ClassName.field pattern."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "AppConfig.debug" in names
        assert "AppConfig.port" in names
        assert "AppConfig.host" in names
        assert "UserModel.name" in names
        assert "UserModel.count" in names

    def test_types_extracted(self):
        """Types are extracted correctly."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        debug_fact = next((f for f in facts if f.name == "AppConfig.debug"), None)
        assert debug_fact is not None
        assert debug_fact.parameters[0].type_annotation == "bool"

        port_fact = next((f for f in facts if f.name == "AppConfig.port"), None)
        assert port_fact is not None
        assert port_fact.parameters[0].type_annotation == "int"

    def test_defaults_extracted(self):
        """Default values are extracted."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        debug_fact = next((f for f in facts if f.name == "AppConfig.debug"), None)
        assert debug_fact is not None
        assert debug_fact.parameters[0].default == "False"

        port_fact = next((f for f in facts if f.name == "AppConfig.port"), None)
        assert port_fact is not None
        assert port_fact.parameters[0].default == "8000"

    def test_env_var_mapping(self):
        """Env var mappings are captured in metadata."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        port_fact = next((f for f in facts if f.name == "AppConfig.port"), None)
        assert port_fact is not None
        assert port_fact.metadata.get("env_var") == "PORT"

        host_fact = next((f for f in facts if f.name == "AppConfig.host"), None)
        assert host_fact is not None
        assert host_fact.metadata.get("env_var") == "HOST"

        db_fact = next((f for f in facts if f.name == "AppConfig.database_url"), None)
        assert db_fact is not None
        assert db_fact.metadata.get("env_var") == "DATABASE_URL"

    def test_description_in_metadata(self):
        """Description is captured in metadata."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        port_fact = next((f for f in facts if f.name == "AppConfig.port"), None)
        assert port_fact is not None
        assert port_fact.metadata.get("description") == "Port to listen on."

        name_fact = next((f for f in facts if f.name == "UserModel.name"), None)
        assert name_fact is not None
        assert name_fact.metadata.get("description") == "User's full name."

    def test_no_pydantic_returns_empty(self):
        """File with no pydantic returns empty list."""
        no_pydantic = Path(__file__).parent.parent / "test_models.py"
        extractor = PydanticExtractor()
        facts = extractor.extract(no_pydantic)
        config_facts = [f for f in facts if f.kind.value == "config_key"]
        assert config_facts == []

    def test_kind_is_config_key(self):
        """All extracted facts have kind=config_key."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "config_key" for f in facts)

    def test_alias_extracted(self):
        """Alias is captured in metadata."""
        extractor = PydanticExtractor()
        facts = extractor.extract(FIXTURE)
        log_level_fact = next((f for f in facts if f.name == "AppConfig.log_level"), None)
        assert log_level_fact is not None
        assert log_level_fact.metadata.get("alias") == "level"
