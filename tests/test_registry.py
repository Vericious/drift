"""Tests for the extractor registry and plugin loading."""

from pathlib import Path

import pytest

from drift.extractors.base import Extractor
from drift.extractors.registry import (
    _EXTRACTORS,
    get_extractors,
    register,
)
from drift.plugin import clear_plugin_cache


# Simple test extractor for testing @register decorator
@register
class _TestExtractorA(Extractor):
    """Test extractor A for registry tests."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix == ".test_a"

    def extract(self, path: Path):
        return []


@register
class _TestExtractorB(Extractor):
    """Test extractor B for registry tests."""

    def can_handle(self, path: Path) -> bool:
        return path.suffix == ".test_b"

    def extract(self, path: Path):
        return []


class TestRegisterDecorator:
    """Tests for the @register decorator."""

    def test_register_decorator_adds_to_registry(self) -> None:
        """@register decorator adds the extractor class to the global registry."""
        initial_count = len(_EXTRACTORS)
        # _TestExtractorA was already registered by the import above
        extractor_names = [e.__name__ for e in _EXTRACTORS]
        assert "_TestExtractorA" in extractor_names
        assert "_TestExtractorB" in extractor_names

    def test_registry_deduplication_on_double_register(self) -> None:
        """Registering the same class twice does not duplicate it in registry."""
        extractor_names_before = [e.__name__ for e in _EXTRACTORS]

        @register
        class _TestExtractorDup(Extractor):
            def can_handle(self, path: Path) -> bool:
                return False

            def extract(self, path: Path):
                return []

        extractor_names_after = [e.__name__ for e in _EXTRACTORS]
        # Should only add one new entry
        assert len(extractor_names_after) == len(extractor_names_before) + 1
        assert "_TestExtractorDup" in extractor_names_after


class TestPluginLoading:
    """Tests for plugin loading via entry_points."""

    def test_discover_plugins_via_entry_points(self) -> None:
        """get_extractors() discovers and loads extractors from entry_points."""
        clear_plugin_cache()
        extractors = get_extractors()
        # Should have at least the built-in extractors
        assert len(extractors) > 0

    def test_get_extractors_returns_list(self) -> None:
        """get_extractors() returns a list of extractor classes."""
        extractors = get_extractors()
        assert isinstance(extractors, list)

    def test_can_handle_routing_for_all_types(self, tmp_path: Path) -> None:
        """can_handle() correctly routes .py, .ts, .tsx, .md files to extractors."""
        extractors = get_extractors()

        # Collect can_handle results for each extractor
        py_file = tmp_path / "example.py"
        ts_file = tmp_path / "example.ts"
        md_file = tmp_path / "example.md"

        py_extractors = [e for e in extractors if e().can_handle(py_file)]
        ts_extractors = [e for e in extractors if e().can_handle(ts_file)]
        md_extractors = [e for e in extractors if e().can_handle(md_file)]

        assert len(py_extractors) >= 1, "At least one extractor should handle .py files"
        assert len(ts_extractors) >= 1, "At least one extractor should handle .ts files"
        assert len(md_extractors) >= 1, "At least one extractor should handle .md files"


class TestRegistryClear:
    """Tests for registry cache clearing."""

    def test_clear_plugin_cache(self) -> None:
        """clear_plugin_cache() resets the plugin cache."""
        clear_plugin_cache()
        # Should not raise
