"""Tests for the plugin system (entry_points-based extractor loading)."""

import sys
from pathlib import Path
from unittest.mock import patch

# Ensure the test plugin is importable
_plugin_path = Path(__file__).parent / "plugins" / "test_drift_example"
sys.path.insert(0, str(_plugin_path.parent))


class FakeEP:
    """Fake entry_point object for mocking importlib.metadata.entry_points."""

    def __init__(self, name: str, value: str, module_name: str):
        self.name = name
        self.value = value
        self._module_name = module_name

    def load(self):
        import importlib

        return importlib.import_module(self._module_name)


class TestPluginDiscovery:
    """Tests for drift.plugin module."""

    def test_load_plugins_discovers_entry_points(self) -> None:
        """load_plugins() finds and loads extractors from drift.extractors entry point group."""
        from drift.plugin import clear_plugin_cache, load_plugins

        clear_plugin_cache()

        # Mock entry_points to return our test plugin
        fake_eps = [
            FakeEP(
                name="todo-extractor",
                value="test_drift_example.extractor:TodoCommentExtractor",
                module_name="test_drift_example.extractor",
            )
        ]

        with patch("drift.plugin.entry_points") as mock_eps:
            mock_eps.return_value = fake_eps

            plugins = load_plugins()

        assert len(plugins) == 1
        assert plugins[0].__name__ == "TodoCommentExtractor"

        # Cache should be populated
        from drift.plugin import get_plugins

        assert len(get_plugins()) == 1

    def test_load_plugins_handles_missing_entry_points_group(self) -> None:
        """load_plugins() gracefully handles missing entry point group."""
        from drift.plugin import clear_plugin_cache, load_plugins

        clear_plugin_cache()

        # Simulate entry_points raising (e.g. no drift.extractors group)
        with patch("drift.plugin.entry_points") as mock_eps:
            mock_eps.side_effect = AttributeError("no drift.extractors group")
            plugins = load_plugins()

        assert plugins == []

    def test_clear_plugin_cache(self) -> None:
        """clear_plugin_cache() resets the plugin cache."""
        from drift.plugin import clear_plugin_cache, load_plugins

        clear_plugin_cache()

        fake_eps = [
            FakeEP(
                name="todo-extractor",
                value="test_drift_example.extractor:TodoCommentExtractor",
                module_name="test_drift_example.extractor",
            )
        ]

        with patch("drift.plugin.entry_points") as mock_eps:
            mock_eps.return_value = fake_eps
            load_plugins()

        from drift.plugin import get_plugins

        assert len(get_plugins()) == 1

        clear_plugin_cache()
        assert get_plugins() == []

    def test_plugin_extractor_registered_in_registry(self) -> None:
        """Plugin extractors loaded via load_plugins() are available in get_extractors()."""
        from drift.extractors.registry import _DISCOVERY_DONE, _EXTRACTORS
        from drift.plugin import clear_plugin_cache, load_plugins

        # Save state
        original_discovery = _DISCOVERY_DONE
        original_extractors = list(_EXTRACTORS)

        clear_plugin_cache()

        fake_eps = [
            FakeEP(
                name="todo-extractor",
                value="test_drift_example.extractor:TodoCommentExtractor",
                module_name="test_drift_example.extractor",
            )
        ]

        with patch("drift.plugin.entry_points") as mock_eps:
            mock_eps.return_value = fake_eps
            load_plugins()

        from drift.extractors.registry import get_extractors

        extractors = get_extractors()
        names = [e.__name__ for e in extractors]
        assert "TodoCommentExtractor" in names

        # Restore
        _DISCOVERY_DONE = original_discovery
        _EXTRACTORS[:] = original_extractors


class TestListExtractorsCommand:
    """Tests for the drift list-extractors CLI command."""

    def test_list_extractors_shows_builtin_and_plugin(self) -> None:
        """--list-extractors shows built-in and plugin extractors."""
        from click.testing import CliRunner

        from drift.cli import main

        runner = CliRunner()

        fake_eps = [
            FakeEP(
                name="todo-extractor",
                value="test_drift_example.extractor:TodoCommentExtractor",
                module_name="test_drift_example.extractor",
            )
        ]

        with patch("drift.plugin.entry_points") as mock_eps:
            mock_eps.return_value = fake_eps

            result = runner.invoke(main, ["list-extractors"])

        assert result.exit_code == 0
        assert "TodoCommentExtractor" in result.output
        assert "plugin" in result.output

        # Built-ins should be marked as built-in
        assert "DocstringExtractor" in result.output
        assert "built-in" in result.output


class TestPluginExtractorIntegration:
    """Integration test: plugin extractor is used during scanning."""

    def test_plugin_extractor_used_in_scan(self, tmp_path: Path) -> None:
        """A Python file with a TODO comment is scanned by the plugin extractor."""
        import importlib

        from drift.extractors.registry import _DISCOVERY_DONE, _EXTRACTORS
        from drift.plugin import clear_plugin_cache, load_plugins

        # Save registry state
        saved_discovery = _DISCOVERY_DONE
        saved_extractors = list(_EXTRACTORS)

        clear_plugin_cache()
        _DISCOVERY_DONE = False
        # Don't clear _EXTRACTORS — clearing it loses the built-in extractors
        # registered by prior module imports. Instead, just set _DISCOVERY_DONE
        # to False and let discovery re-run (it will append plugin extractors
        # to the existing built-in list).

        fake_eps = [
            FakeEP(
                name="todo-extractor",
                value="test_drift_example.extractor:TodoCommentExtractor",
                module_name="test_drift_example.extractor",
            )
        ]

        # Patch entry_points for the duration of discovery
        with patch("drift.plugin.entry_points") as mock_eps:
            mock_eps.return_value = fake_eps
            # Reload the plugin module to re-trigger @register
            if "test_drift_example.extractor" in sys.modules:
                importlib.reload(sys.modules["test_drift_example.extractor"])
            load_plugins()

        # Verify plugin was loaded into _EXTRACTORS
        extractor_names = [e.__name__ for e in _EXTRACTORS]
        assert "TodoCommentExtractor" in extractor_names

        # Write a Python file with a TODO
        py_file = tmp_path / "example.py"
        py_file.write_text("""\
def hello():
    # TODO: make this actually say hello
    pass
""")

        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path, strict=False)
        report = scanner.scan()

        # The TODO comment should be found by the plugin extractor
        claim_names = [c.name for c in report.claims]
        assert "//TODO" in claim_names

        # Restore registry state
        _DISCOVERY_DONE = saved_discovery
        _EXTRACTORS[:] = saved_extractors
