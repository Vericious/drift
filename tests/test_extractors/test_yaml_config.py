"""Tests for YamlConfigExtractor."""

import tempfile
from pathlib import Path

import pytest

from drift.extractors.yaml_config import YamlConfigExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    """Return a YamlConfigExtractor instance."""
    return YamlConfigExtractor()


@pytest.fixture
def tmp_yaml_file(tmp_path):
    """Factory: create a YAML file with given content, return Path."""
    def _make(content: str) -> Path:
        f = tmp_path / "config.yaml"
        f.write_text(content)
        return f
    return _make


# ---------------------------------------------------------------------------
# can_handle tests
# ---------------------------------------------------------------------------


class TestCanHandle:
    """Tests for can_handle() method."""

    def test_can_handle_yaml_ext(self, extractor):
        assert extractor.can_handle(Path("config.yaml")) is True

    def test_can_handle_yml_ext(self, extractor):
        assert extractor.can_handle(Path("config.yml")) is True

    def test_can_handle_uppercase_ext(self, extractor):
        assert extractor.can_handle(Path("config.YAML")) is True
        assert extractor.can_handle(Path("config.YML")) is True

    def test_cannot_handle_other_ext(self, extractor):
        assert extractor.can_handle(Path("config.json")) is False
        assert extractor.can_handle(Path("config.toml")) is False
        assert extractor.can_handle(Path("config.txt")) is False
        assert extractor.can_handle(Path("config.xml")) is False

    def test_cannot_handle_no_ext(self, extractor):
        assert extractor.can_handle(Path("Makefile")) is False


# ---------------------------------------------------------------------------
# Basic extraction tests
# ---------------------------------------------------------------------------


class TestBasicExtraction:
    """Basic YAML key-value extraction tests."""

    def test_simple_key_value(self, extractor, tmp_yaml_file):
        """Single key-value pair is extracted."""
        path = tmp_yaml_file("port: 8080")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "port"
        assert facts[0].kind.value == "config_key"

    def test_multiple_keys(self, extractor, tmp_yaml_file):
        """Multiple top-level keys are extracted."""
        path = tmp_yaml_file("name: app\nversion: 1.0\ndebug: true")
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "name" in names
        assert "version" in names
        assert "debug" in names

    def test_nested_keys_dot_notation(self, extractor, tmp_yaml_file):
        """Nested dict keys use dot notation."""
        path = tmp_yaml_file("database:\n  host: localhost\n  port: 5432")
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "database.host" in names
        assert "database.port" in names

    def test_deeply_nested_keys(self, extractor, tmp_yaml_file):
        """Deeply nested keys are flattened with dot notation."""
        path = tmp_yaml_file("a:\n  b:\n    c:\n      d: value")
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "a.b.c.d" in names

    def test_list_items(self, extractor, tmp_yaml_file):
        """List items get indexed keys."""
        path = tmp_yaml_file("items:\n  - first\n  - second\n  - third")
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "items.0" in names
        assert "items.1" in names
        assert "items.2" in names

    def test_empty_yaml_returns_empty(self, extractor, tmp_yaml_file):
        """Empty YAML file returns no facts."""
        path = tmp_yaml_file("")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_only_comments_returns_empty(self, extractor, tmp_yaml_file):
        """YAML with only comments returns no facts."""
        path = tmp_yaml_file("# This is a comment\n# Another comment")
        facts = extractor.extract(path)
        assert len(facts) == 0


# ---------------------------------------------------------------------------
# Value type tests
# ---------------------------------------------------------------------------


class TestValueTypes:
    """Tests for different YAML value types."""

    def test_string_value(self, extractor, tmp_yaml_file):
        path = tmp_yaml_file("name: hello")
        facts = extractor.extract(path)
        assert facts[0].parameters[0].type_annotation == "str"

    def test_int_value(self, extractor, tmp_yaml_file):
        path = tmp_yaml_file("count: 42")
        facts = extractor.extract(path)
        assert facts[0].parameters[0].type_annotation == "int"

    def test_float_value(self, extractor, tmp_yaml_file):
        path = tmp_yaml_file("ratio: 3.14")
        facts = extractor.extract(path)
        assert facts[0].parameters[0].type_annotation == "float"

    def test_bool_value(self, extractor, tmp_yaml_file):
        path = tmp_yaml_file("enabled: true")
        facts = extractor.extract(path)
        assert facts[0].parameters[0].type_annotation == "bool"

    def test_null_value(self, extractor, tmp_yaml_file):
        path = tmp_yaml_file("value: null")
        facts = extractor.extract(path)
        assert facts[0].parameters[0].type_annotation == "null"

    def test_list_value(self, extractor, tmp_yaml_file):
        """List values are flattened into indexed keys."""
        path = tmp_yaml_file("tags: [a, b, c]")
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "tags.0" in names
        assert "tags.1" in names
        assert "tags.2" in names


# ---------------------------------------------------------------------------
# Docker Compose format tests
# ---------------------------------------------------------------------------


class TestDockerCompose:
    """Tests for docker-compose.yml format."""

    def test_docker_compose_services(self, extractor, tmp_yaml_file):
        """Docker Compose services are extracted."""
        content = """services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
  db:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: secret
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "services.web.image" in names
        assert "services.db.image" in names
        assert "services.db.environment.POSTGRES_PASSWORD" in names

    def test_docker_compose_volumes(self, extractor, tmp_yaml_file):
        """Docker Compose volumes are extracted."""
        content = """volumes:
  db_data:
  app_cache:
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "volumes.db_data" in names
        assert "volumes.app_cache" in names

    def test_docker_compose_networks(self, extractor, tmp_yaml_file):
        """Docker Compose networks are extracted."""
        content = """networks:
  frontend:
  backend:
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "networks.frontend" in names
        assert "networks.backend" in names


# ---------------------------------------------------------------------------
# GitLab CI format tests
# ---------------------------------------------------------------------------


class TestGitLabCI:
    """Tests for .gitlab-ci.yml format."""

    def test_gitlab_ci_stages(self, extractor, tmp_yaml_file):
        """GitLab CI stages are extracted."""
        content = """stages:
  - build
  - test
  - deploy
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "stages.0" in names
        assert "stages.1" in names
        assert "stages.2" in names

    def test_gitlab_ci_jobs(self, extractor, tmp_yaml_file):
        """GitLab CI job definitions are extracted."""
        content = """build:
  stage: build
  script: make build
test:
  stage: test
  script: make test
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "build.stage" in names
        assert "test.script" in names

    def test_gitlab_ci_variables(self, extractor, tmp_yaml_file):
        """GitLab CI variables are extracted."""
        content = """variables:
  DEPLOY_ENV: production
  DEBUG: "false"
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "variables.DEPLOY_ENV" in names
        assert "variables.DEBUG" in names


# ---------------------------------------------------------------------------
# Kubernetes format tests
# ---------------------------------------------------------------------------


class TestKubernetes:
    """Tests for Kubernetes manifest format."""

    def test_kubernetes_kind_and_metadata(self, extractor, tmp_yaml_file):
        """Kubernetes kind and metadata are extracted."""
        content = """apiVersion: v1
kind: Pod
metadata:
  name: my-pod
  namespace: default
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "apiVersion" in names
        assert "kind" in names
        assert "metadata.name" in names
        assert "metadata.namespace" in names

    def test_kubernetes_spec(self, extractor, tmp_yaml_file):
        """Kubernetes spec section is extracted."""
        content = """apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 3
  selector:
    matchLabels:
      app: my-app
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "spec.replicas" in names
        assert "spec.selector.matchLabels.app" in names


# ---------------------------------------------------------------------------
# Edge cases and error handling
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_invalid_yaml_returns_empty(self, extractor, tmp_yaml_file):
        """Invalid YAML returns empty list."""
        path = tmp_yaml_file("invalid: yaml: content:")
        facts = extractor.extract(path)
        # Should not raise, just return empty

    def test_binary_file_returns_empty(self, extractor):
        """Non-UTF8 file returns empty list."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(b"\x00\x01\x02")
            f.flush()
            path = Path(f.name)
        try:
            facts = extractor.extract(path)
            assert len(facts) == 0
        finally:
            path.unlink()

    def test_none_top_level_returns_empty(self, extractor, tmp_yaml_file):
        """YAML that parses to non-dict (e.g., list) returns empty."""
        path = tmp_yaml_file("- item1\n- item2\n- item3")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_special_characters_in_keys(self, extractor, tmp_yaml_file):
        """Keys with special characters are handled."""
        path = tmp_yaml_file("'special:key': value\n\"another.key\": val")
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "special:key" in names
        assert "another.key" in names

    def test_multiline_string(self, extractor, tmp_yaml_file):
        """Multiline strings are handled."""
        content = """description: |
  This is a multiline
  string value
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        assert any(f.name == "description" for f in facts)


# ---------------------------------------------------------------------------
# Metadata tests
# ---------------------------------------------------------------------------


class TestMetadata:
    """Tests for fact metadata."""

    def test_metadata_has_yaml_kind_docker_compose(self, extractor, tmp_yaml_file):
        """Docker Compose YAML sets yaml_kind metadata."""
        content = """services:
  web:
    image: nginx
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        web_fact = next(f for f in facts if f.name == "services.web.image")
        assert web_fact.metadata.get("yaml_kind") == "docker-compose"

    def test_metadata_has_yaml_kind_gitlab_ci(self, extractor, tmp_yaml_file):
        """GitLab CI YAML sets yaml_kind metadata."""
        content = """stages:
  - build
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        stages_fact = next(f for f in facts if f.name == "stages.0")
        assert stages_fact.metadata.get("yaml_kind") == "gitlab-ci"

    def test_metadata_has_yaml_kind_kubernetes(self, extractor, tmp_yaml_file):
        """Kubernetes YAML sets yaml_kind metadata."""
        content = """apiVersion: v1
kind: Pod
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        kind_fact = next(f for f in facts if f.name == "kind")
        assert kind_fact.metadata.get("yaml_kind") == "kubernetes"

    def test_metadata_has_value_type(self, extractor, tmp_yaml_file):
        """Facts include value_type in metadata."""
        path = tmp_yaml_file("count: 42")
        facts = extractor.extract(path)
        assert facts[0].metadata.get("value_type") == "int"

    def test_metadata_has_value_representation(self, extractor, tmp_yaml_file):
        """Facts include string representation of value."""
        path = tmp_yaml_file("flag: true")
        facts = extractor.extract(path)
        assert "True" in facts[0].metadata.get("value", "")


# ---------------------------------------------------------------------------
# Integration tests with DriftScanner
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests using DriftScanner."""

    def test_scanner_extracts_yaml_keys(self, extractor, tmp_yaml_file):
        """DriftScanner extracts keys from YAML files."""
        content = """database:
  host: localhost
  port: 5432
  ssl:
    enabled: true
"""
        path = tmp_yaml_file(content)
        facts = extractor.extract(path)
        assert any(f.name == "database.host" for f in facts)
        assert any(f.name == "database.port" for f in facts)
        assert any(f.name == "database.ssl.enabled" for f in facts)

    def test_yaml_extractor_registered(self):
        """YamlConfigExtractor is registered in the extractor registry."""
        from drift.extractors.registry import get_extractors
        extractor_classes = get_extractors()
        class_names = [cls.__name__ for cls in extractor_classes]
        assert "YamlConfigExtractor" in class_names
