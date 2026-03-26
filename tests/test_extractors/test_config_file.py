"""Tests for config_file extractor."""
from pathlib import Path

import pytest

from drift.extractors.config_file import ConfigFileExtractor


YAML_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_config.yaml"
TOML_FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_config.toml"


class TestConfigFileExtractor:
    """Test ConfigFileExtractor."""

    def test_can_handle_yaml(self):
        """can_handle returns True for .yaml files."""
        extractor = ConfigFileExtractor()
        assert extractor.can_handle(Path("config.yaml")) is True
        assert extractor.can_handle(Path("config.yml")) is True

    def test_can_handle_toml(self):
        """can_handle returns True for .toml files."""
        extractor = ConfigFileExtractor()
        assert extractor.can_handle(Path("config.toml")) is True

    def test_can_handle_rejects_other_files(self):
        """can_handle returns False for non-config files."""
        extractor = ConfigFileExtractor()
        assert extractor.can_handle(Path("config.py")) is False
        assert extractor.can_handle(Path("config.md")) is False
        assert extractor.can_handle(Path("config.txt")) is False

    def test_yaml_extracts_all_leaf_keys(self):
        """All leaf keys are extracted with dot-notation names."""
        extractor = ConfigFileExtractor()
        facts = extractor.extract(YAML_FIXTURE)
        names = {f.name for f in facts}
        assert "database.host" in names
        assert "database.port" in names
        assert "database.ssl" in names
        assert "database.pools.min" in names
        assert "server.port" in names
        assert "logging.level" in names

    def test_toml_extracts_all_leaf_keys(self):
        """TOML leaf keys are extracted with dot-notation names."""
        extractor = ConfigFileExtractor()
        facts = extractor.extract(TOML_FIXTURE)
        names = {f.name for f in facts}
        assert "database.host" in names
        assert "server.port" in names
        assert "logging.level" in names

    def test_list_values_have_list_type(self):
        """List values have value_type 'list'."""
        extractor = ConfigFileExtractor()
        facts = extractor.extract(YAML_FIXTURE)
        handlers_fact = next((f for f in facts if f.name == "logging.handlers"), None)
        assert handlers_fact is not None
        assert handlers_fact.metadata.get("value_type") == "list"

    def test_bool_values_have_bool_type(self):
        """Bool values have value_type 'bool'."""
        extractor = ConfigFileExtractor()
        facts = extractor.extract(YAML_FIXTURE)
        ssl_fact = next((f for f in facts if f.name == "database.ssl"), None)
        assert ssl_fact is not None
        assert ssl_fact.metadata.get("value_type") == "bool"

    def test_int_values_have_int_type(self):
        """Int values have value_type 'int'."""
        extractor = ConfigFileExtractor()
        facts = extractor.extract(YAML_FIXTURE)
        port_fact = next((f for f in facts if f.name == "database.port"), None)
        assert port_fact is not None
        assert port_fact.metadata.get("value_type") == "int"

    def test_str_values_have_str_type(self):
        """String values have value_type 'str'."""
        extractor = ConfigFileExtractor()
        facts = extractor.extract(YAML_FIXTURE)
        host_fact = next((f for f in facts if f.name == "database.host"), None)
        assert host_fact is not None
        assert host_fact.metadata.get("value_type") == "str"

    def test_empty_yaml_file_returns_empty(self):
        """Empty YAML file returns empty list."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("")
            tmp = Path(f.name)
        try:
            extractor = ConfigFileExtractor()
            facts = extractor.extract(tmp)
            assert facts == []
        finally:
            tmp.unlink()

    def test_kind_is_config_key(self):
        """All extracted facts have kind=config_key."""
        extractor = ConfigFileExtractor()
        yaml_facts = extractor.extract(YAML_FIXTURE)
        assert all(f.kind.value == "config_key" for f in yaml_facts)
        toml_facts = extractor.extract(TOML_FIXTURE)
        assert all(f.kind.value == "config_key" for f in toml_facts)
