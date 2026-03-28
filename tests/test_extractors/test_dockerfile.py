"""Tests for DockerfileExtractor."""

import tempfile
from pathlib import Path

import pytest

from drift.extractors.dockerfile import DockerfileExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    """Return a DockerfileExtractor instance."""
    return DockerfileExtractor()


@pytest.fixture
def tmp_dockerfile(tmp_path):
    """Factory: create a Dockerfile with given content, return Path."""
    def _make(content: str, name: str = "Dockerfile") -> Path:
        f = tmp_path / name
        f.write_text(content)
        return f
    return _make


# ---------------------------------------------------------------------------
# can_handle tests
# ---------------------------------------------------------------------------


class TestCanHandle:
    """Tests for can_handle() method."""

    def test_can_handle_dockerfile(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("FROM python:3.11", "Dockerfile")
        assert extractor.can_handle(path) is True

    def test_can_handle_dockerfile_with_suffix(self, extractor, tmp_dockerfile):
        assert extractor.can_handle(Path("Dockerfile.dev")) is True
        assert extractor.can_handle(Path("Dockerfile.prod")) is True
        assert extractor.can_handle(Path("Dockerfile.staging")) is True

    def test_can_handle_dockerfile_extension(self, extractor, tmp_dockerfile):
        assert extractor.can_handle(Path("app.dockerfile")) is True
        assert extractor.can_handle(Path("web.dockerfile")) is True

    def test_cannot_handle_regular_files(self, extractor):
        assert extractor.can_handle(Path("docker-compose.yml")) is False
        assert extractor.can_handle(Path(".dockerignore")) is False
        assert extractor.can_handle(Path("Makefile")) is False
        assert extractor.can_handle(Path("app.py")) is False


# ---------------------------------------------------------------------------
# FROM instruction tests
# ---------------------------------------------------------------------------


class TestFromInstruction:
    """Tests for FROM instruction extraction."""

    def test_simple_from(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("FROM python:3.11")
        facts = extractor.extract(path)
        from_facts = [f for f in facts if f.name.startswith("from.")]
        assert len(from_facts) == 1
        assert "python:3.11" in from_facts[0].metadata["image"]

    def test_from_with_alias(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("FROM python:3.11 AS builder")
        facts = extractor.extract(path)
        from_facts = [f for f in facts if f.name.startswith("from.")]
        assert len(from_facts) == 1
        assert from_facts[0].metadata["stage"] == "builder"

    def test_multi_stage_froms(self, extractor, tmp_dockerfile):
        content = """FROM python:3.11 AS builder
FROM gcr.io/distroless/python3 AS final
"""
        path = tmp_dockerfile(content)
        facts = extractor.extract(path)
        from_facts = [f for f in facts if f.name.startswith("from.")]
        assert len(from_facts) == 2
        stages = {f.metadata["stage"] for f in from_facts}
        assert "builder" in stages
        assert "final" in stages

    def test_from_with_version_tag(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("FROM node:18-alpine")
        facts = extractor.extract(path)
        from_fact = next(f for f in facts if f.name.startswith("from."))
        assert "node:18-alpine" in from_fact.metadata["image"]


# ---------------------------------------------------------------------------
# ENV instruction tests
# ---------------------------------------------------------------------------


class TestEnvInstruction:
    """Tests for ENV instruction extraction."""

    def test_single_env(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("ENV APP_ENV=production")
        facts = extractor.extract(path)
        env_facts = [f for f in facts if f.name.startswith("env.")]
        assert len(env_facts) == 1
        assert env_facts[0].name == "env.APP_ENV"
        assert env_facts[0].metadata["value"] == "production"

    def test_multiple_envs_same_line(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1")
        facts = extractor.extract(path)
        env_facts = [f for f in facts if f.name.startswith("env.")]
        assert len(env_facts) == 2
        names = {f.name for f in env_facts}
        assert "env.PYTHONDONTWRITEBYTECODE" in names
        assert "env.PYTHONUNBUFFERED" in names

    def test_env_with_equals_in_value(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("ENV DATABASE_URL=postgresql://user:pass@host:5432/db")
        facts = extractor.extract(path)
        env_fact = next(f for f in facts if f.name == "env.DATABASE_URL")
        assert "postgresql://" in env_fact.metadata["value"]


# ---------------------------------------------------------------------------
# LABEL instruction tests
# ---------------------------------------------------------------------------


class TestLabelInstruction:
    """Tests for LABEL instruction extraction."""

    def test_single_label(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile('LABEL maintainer="dev@example.com"')
        facts = extractor.extract(path)
        label_facts = [f for f in facts if f.name.startswith("label.")]
        assert len(label_facts) == 1
        assert label_facts[0].name == "label.maintainer"
        assert label_facts[0].metadata["value"] == "dev@example.com"

    def test_multiple_labels_same_line(self, extractor, tmp_dockerfile):
        content = '''LABEL maintainer="dev@example.com" version="1.0.0"'''
        path = tmp_dockerfile(content)
        facts = extractor.extract(path)
        label_facts = [f for f in facts if f.name.startswith("label.")]
        assert len(label_facts) == 2
        names = {f.name for f in label_facts}
        assert "label.maintainer" in names
        assert "label.version" in names

    def test_multiline_labels(self, extractor, tmp_dockerfile):
        content = '''LABEL org.opencontainers.image.title="Sample App" \\
      org.opencontainers.image.version="1.0.0"'''
        path = tmp_dockerfile(content)
        facts = extractor.extract(path)
        label_facts = [f for f in facts if f.name.startswith("label.")]
        assert len(label_facts) >= 2


# ---------------------------------------------------------------------------
# EXPOSE instruction tests
# ---------------------------------------------------------------------------


class TestExposeInstruction:
    """Tests for EXPOSE instruction extraction."""

    def test_single_port(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("EXPOSE 8000")
        facts = extractor.extract(path)
        expose_facts = [f for f in facts if f.name.startswith("expose.")]
        assert len(expose_facts) == 1
        assert expose_facts[0].name == "expose.8000"

    def test_multiple_ports(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("EXPOSE 8000 8080 3000")
        facts = extractor.extract(path)
        expose_facts = [f for f in facts if f.name.startswith("expose.")]
        assert len(expose_facts) == 3
        ports = {f.name.split(".")[1] for f in expose_facts}
        assert ports == {"8000", "8080", "3000"}

    def test_port_with_protocol(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("EXPOSE 8080/udp")
        facts = extractor.extract(path)
        expose_fact = next(f for f in facts if f.name.startswith("expose."))
        assert expose_fact.name == "expose.8080"
        assert expose_fact.metadata["port"] == "8080"


# ---------------------------------------------------------------------------
# ARG instruction tests
# ---------------------------------------------------------------------------


class TestArgInstruction:
    """Tests for ARG instruction extraction."""

    def test_arg_without_default(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("ARG VERSION")
        facts = extractor.extract(path)
        arg_facts = [f for f in facts if f.name.startswith("arg.")]
        assert len(arg_facts) == 1
        assert arg_facts[0].name == "arg.VERSION"
        assert arg_facts[0].metadata["default"] is None

    def test_arg_with_default(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("ARG VERSION=1.0.0")
        facts = extractor.extract(path)
        arg_fact = next(f for f in facts if f.name == "arg.VERSION")
        assert arg_fact.metadata["default"] == "1.0.0"


# ---------------------------------------------------------------------------
# ENTRYPOINT and CMD tests
# ---------------------------------------------------------------------------


class TestEntrypointCmd:
    """Tests for ENTRYPOINT and CMD instruction extraction."""

    def test_entrypoint_shell_form(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile('ENTRYPOINT echo "Hello"')
        facts = extractor.extract(path)
        entrypoint_facts = [f for f in facts if f.name == "entrypoint"]
        assert len(entrypoint_facts) == 1
        assert "echo" in entrypoint_facts[0].metadata["command"]

    def test_entrypoint_exec_form(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile('ENTRYPOINT ["python", "main.py"]')
        facts = extractor.extract(path)
        entrypoint_facts = [f for f in facts if f.name == "entrypoint"]
        assert len(entrypoint_facts) == 1

    def test_cmd_shell_form(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile('CMD echo "World"')
        facts = extractor.extract(path)
        cmd_facts = [f for f in facts if f.name == "cmd"]
        assert len(cmd_facts) == 1
        assert "echo" in cmd_facts[0].metadata["command"]

    def test_cmd_exec_form(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile('CMD ["--bind", "0.0.0.0:8000"]')
        facts = extractor.extract(path)
        cmd_facts = [f for f in facts if f.name == "cmd"]
        assert len(cmd_facts) == 1


# ---------------------------------------------------------------------------
# Other instructions
# ---------------------------------------------------------------------------


class TestOtherInstructions:
    """Tests for WORKDIR, USER, COPY, ADD instructions."""

    def test_workdir(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("WORKDIR /app")
        facts = extractor.extract(path)
        workdir_facts = [f for f in facts if f.name == "workdir"]
        assert len(workdir_facts) == 1
        assert workdir_facts[0].metadata["path"] == "/app"

    def test_user(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("USER appuser")
        facts = extractor.extract(path)
        user_facts = [f for f in facts if f.name == "user"]
        assert len(user_facts) == 1
        assert user_facts[0].metadata["user"] == "appuser"

    def test_copy(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("COPY . /app")
        facts = extractor.extract(path)
        copy_facts = [f for f in facts if f.name == "copy"]
        assert len(copy_facts) == 1
        assert copy_facts[0].metadata["source"] == "."

    def test_add(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("ADD archive.tar.gz /app")
        facts = extractor.extract(path)
        add_facts = [f for f in facts if f.name == "add"]
        assert len(add_facts) == 1
        assert add_facts[0].metadata["source"] == "archive.tar.gz"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_dockerfile(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_only_comments(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("# This is a comment\n# Another comment")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_case_insensitive_instructions(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("from python:3.11\nenv APP=hello\nlabel version=1.0")
        facts = extractor.extract(path)
        assert len(facts) > 0

    def test_unknown_instruction_ignored(self, extractor, tmp_dockerfile):
        path = tmp_dockerfile("RUN echo hello\nMAINTAINER dev@example.com")
        facts = extractor.extract(path)
        # RUN and MAINTAINER are not currently extracted
        run_facts = [f for f in facts if f.metadata.get("instruction") == "RUN"]
        assert len(run_facts) == 0


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests using sample Dockerfile."""

    def test_extracts_all_instructions_from_sample(self, extractor):
        """Sample Dockerfile is parsed correctly."""
        fixture = Path(__file__).parent.parent / "fixtures" / "sample_Dockerfile"
        if not fixture.exists():
            pytest.skip("Sample Dockerfile fixture not found")

        facts = extractor.extract(fixture)
        assert len(facts) > 0

        # Check we have FROM facts
        from_facts = [f for f in facts if f.name.startswith("from.")]
        assert len(from_facts) == 3  # builder, frontend, final

        # Check we have EXPOSE facts
        expose_facts = [f for f in facts if f.name.startswith("expose.")]
        assert len(expose_facts) >= 2  # 8000 and 8080

        # Check we have ENV facts
        env_facts = [f for f in facts if f.name.startswith("env.")]
        assert len(env_facts) >= 3

        # Check we have LABEL facts
        label_facts = [f for f in facts if f.name.startswith("label.")]
        assert len(label_facts) >= 3

    def test_dockerfile_extractor_registered(self):
        """DockerfileExtractor is registered in the extractor registry."""
        from drift.extractors.registry import get_extractors
        extractor_classes = get_extractors()
        class_names = [cls.__name__ for cls in extractor_classes]
        assert "DockerfileExtractor" in class_names

    def test_multistage_build_copies(self, extractor, tmp_dockerfile):
        """COPY --from extracts sources correctly."""
        content = """FROM builder AS builder
COPY --from=builder /app/dist /dist
FROM python:3.11
COPY --from=frontend /dist /app
"""
        path = tmp_dockerfile(content)
        facts = extractor.extract(path)
        copy_facts = [f for f in facts if f.name == "copy"]
        # Should have multiple COPY facts
        assert len(copy_facts) >= 2
