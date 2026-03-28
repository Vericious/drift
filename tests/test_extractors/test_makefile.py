"""Tests for MakefileExtractor."""

from pathlib import Path

import pytest

from drift.extractors.makefile import MakefileExtractor


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    """Return a MakefileExtractor instance."""
    return MakefileExtractor()


@pytest.fixture
def tmp_makefile(tmp_path):
    """Factory: create a Makefile with given content, return Path."""
    def _make(content: str, name: str = "Makefile") -> Path:
        f = tmp_path / name
        f.write_text(content)
        return f
    return _make


# ---------------------------------------------------------------------------
# can_handle tests
# ---------------------------------------------------------------------------


class TestCanHandle:
    """Tests for can_handle() method."""

    def test_can_handle_makefile(self, extractor, tmp_makefile):
        path = tmp_makefile("", "Makefile")
        assert extractor.can_handle(path) is True

    def test_can_handle_lowercase_makefile(self, extractor, tmp_makefile):
        path = tmp_makefile("", "makefile")
        assert extractor.can_handle(path) is True

    def test_can_handle_mk_extension(self, extractor, tmp_makefile):
        path = tmp_makefile("", "rules.mk")
        assert extractor.can_handle(path) is True

    def test_cannot_handle_other_files(self, extractor, tmp_makefile):
        assert extractor.can_handle(Path("makefile.py")) is False
        assert extractor.can_handle(Path("Makefile.bak")) is False
        assert extractor.can_handle(Path("makefile.txt")) is False
        assert extractor.can_handle(Path("make")) is False


# ---------------------------------------------------------------------------
# Basic extraction tests
# ---------------------------------------------------------------------------


class TestBasicExtraction:
    """Basic Makefile target extraction tests."""

    def test_single_target(self, extractor, tmp_makefile):
        path = tmp_makefile("build:\n\t@echo building")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "make:build"

    def test_multiple_targets(self, extractor, tmp_makefile):
        content = """build:
\t@echo building
test:
\t@echo testing
clean:
\t@echo cleaning
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "make:build" in names
        assert "make:test" in names
        assert "make:clean" in names

    def test_target_with_prerequisites(self, extractor, tmp_makefile):
        path = tmp_makefile("deploy: build test\n\t@echo deploying")
        facts = extractor.extract(path)
        deploy_fact = next(f for f in facts if f.name == "make:deploy")
        assert "build" in deploy_fact.metadata["prerequisites"]
        assert "test" in deploy_fact.metadata["prerequisites"]

    def test_target_with_dash(self, extractor, tmp_makefile):
        path = tmp_makefile("build-all:\n\t@echo building all")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "make:build-all"

    def test_target_with_underscore(self, extractor, tmp_makefile):
        path = tmp_makefile("build_lib:\n\t@echo building lib")
        facts = extractor.extract(path)
        assert len(facts) == 1
        assert facts[0].name == "make:build_lib"


# ---------------------------------------------------------------------------
# .PHONY targets
# ---------------------------------------------------------------------------


class TestPhonyTargets:
    """Tests for .PHONY directive."""

    def test_phony_targets_are_marked(self, extractor, tmp_makefile):
        content = """.PHONY: all build
all: build
build:
\t@echo building
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        all_fact = next(f for f in facts if f.name == "make:all")
        build_fact = next(f for f in facts if f.name == "make:build")
        # Targets listed in .PHONY should be marked as phony
        assert all_fact.metadata["phony"] is True
        assert build_fact.metadata["phony"] is True

    def test_phony_all_is_extracted(self, extractor, tmp_makefile):
        content = """.PHONY: all
all:
\t@echo all
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        names = {f.name for f in facts}
        assert "make:all" in names

    def test_non_phony_targets_not_marked(self, extractor, tmp_makefile):
        content = """build:
\t@echo building
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        build_fact = next(f for f in facts if f.name == "make:build")
        assert build_fact.metadata.get("phony") is not True


# ---------------------------------------------------------------------------
# Comments and descriptions
# ---------------------------------------------------------------------------


class TestComments:
    """Tests for comment/description extraction."""

    def test_target_description_from_comment(self, extractor, tmp_makefile):
        content = """# Build the project
build:
\t@echo building
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        build_fact = next(f for f in facts if f.name == "make:build")
        assert build_fact.metadata["description"] == "Build the project"

    def test_target_without_comment_has_default_description(self, extractor, tmp_makefile):
        path = tmp_makefile("build:\n\t@echo building")
        facts = extractor.extract(path)
        build_fact = next(f for f in facts if f.name == "make:build")
        assert "build" in build_fact.metadata["description"]

    def test_multiline_comment_spans_preceding_lines(self, extractor, tmp_makefile):
        content = """# First line
# Second line
build:
\t@echo building
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        build_fact = next(f for f in facts if f.name == "make:build")
        assert "First line" in build_fact.metadata["description"]

    def test_comment_after_target_does_not_attach(self, extractor, tmp_makefile):
        content = """build:
\t@echo building
# This is a comment after
test:
\t@echo testing
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        test_fact = next(f for f in facts if f.name == "make:test")
        # Comment should not be "This is a comment after"
        assert test_fact.metadata["description"] == "Makefile target: test"


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


class TestPrerequisites:
    """Tests for target prerequisites."""

    def test_single_prerequisite(self, extractor, tmp_makefile):
        path = tmp_makefile("deploy: build\n\t@echo deploying")
        facts = extractor.extract(path)
        deploy_fact = next(f for f in facts if f.name == "make:deploy")
        assert deploy_fact.metadata["prerequisites"] == ["build"]

    def test_multiple_prerequisites(self, extractor, tmp_makefile):
        path = tmp_makefile("package: build test lint\n\t@echo packaging")
        facts = extractor.extract(path)
        package_fact = next(f for f in facts if f.name == "make:package")
        assert set(package_fact.metadata["prerequisites"]) == {"build", "test", "lint"}

    def test_prerequisite_with_variable(self, extractor, tmp_makefile):
        path = tmp_makefile("deploy: $(BINARY)\n\t@echo deploying")
        facts = extractor.extract(path)
        deploy_fact = next(f for f in facts if f.name == "make:deploy")
        # Variable is preserved as-is
        assert "$(BINARY)" in deploy_fact.metadata["prerequisites"]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_makefile(self, extractor, tmp_makefile):
        path = tmp_makefile("")
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_only_comments(self, extractor, tmp_makefile):
        content = """# This is a comment
# Another comment
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        assert len(facts) == 0

    def test_only_variables(self, extractor, tmp_makefile):
        content = """CC=gcc
CFLAGS=-Wall
BUILD=build
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        # Variables are not targets
        assert len(facts) == 0

    def test_recipe_lines_not_extracted(self, extractor, tmp_makefile):
        content = """build:
\t@echo building
\trm -rf dist
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        assert len(facts) == 1

    def test_target_with_empty_body(self, extractor, tmp_makefile):
        content = """all:
"""
        path = tmp_makefile(content)
        facts = extractor.extract(path)
        assert len(facts) == 1


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestIntegration:
    """Integration tests."""

    def test_extracts_all_targets_from_sample(self, extractor):
        """Sample Makefile is parsed correctly."""
        fixture = Path(__file__).parent.parent / "fixtures" / "sample_makefile.mk"
        if not fixture.exists():
            pytest.skip("Sample Makefile fixture not found")

        facts = extractor.extract(fixture)
        names = {f.name for f in facts}

        # Check we have expected targets
        expected_targets = {
            "make:all", "make:build", "make:test", "make:lint",
            "make:format", "make:clean", "make:install",
            "make:coverage", "make:docker-build", "make:deploy",
        }
        for target in expected_targets:
            assert target in names, f"Missing target: {target}"

    def test_makefile_extractor_registered(self):
        """MakefileExtractor is registered in the extractor registry."""
        from drift.extractors.registry import get_extractors
        extractor_classes = get_extractors()
        class_names = [cls.__name__ for cls in extractor_classes]
        assert "MakefileExtractor" in class_names

    def test_descriptions_from_comments(self, extractor):
        """Targets with preceding comments have correct descriptions."""
        fixture = Path(__file__).parent.parent / "fixtures" / "sample_makefile.mk"
        if not fixture.exists():
            pytest.skip("Sample Makefile fixture not found")

        facts = extractor.extract(fixture)
        build_fact = next((f for f in facts if f.name == "make:build"), None)
        if build_fact:
            assert "Build" in build_fact.metadata["description"]
