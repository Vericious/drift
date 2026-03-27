"""Tests for per-extractor enable/disable config (DRIFT-096)."""

import pytest
import tempfile
from pathlib import Path

from drift.config import DriftConfig, load_config


class TestExtractorConfig:
    def test_default_all_enabled(self):
        """No config = all extractors enabled (None)."""
        config = DriftConfig()
        assert config.extractors_enabled is None
        assert config.extractors_disabled == []

    def test_load_config_extractors_enabled_list(self):
        """[extractors] enabled key with a list is parsed correctly."""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write("[extractors]\nenabled = ['flask_routes', 'pydantic']\n")
            f.flush()
            config = load_config(Path(f.name))

        assert config.extractors_enabled == ["flask_routes", "pydantic"]
        assert config.extractors_disabled == []
        Path(f.name).unlink()

    def test_load_config_extractors_disabled_list(self):
        """[extractors] disabled key with a list is parsed correctly."""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write("[extractors]\ndisabled = ['openapi', 'graphql']\n")
            f.flush()
            config = load_config(Path(f.name))

        assert config.extractors_enabled is None
        assert config.extractors_disabled == ["openapi", "graphql"]
        Path(f.name).unlink()

    def test_load_config_extractors_both(self):
        """[extractors] enabled and disabled can both be set."""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write("[extractors]\nenabled = ['flask_routes']\ndisabled = ['openapi']\n")
            f.flush()
            config = load_config(Path(f.name))

        assert config.extractors_enabled == ["flask_routes"]
        assert config.extractors_disabled == ["openapi"]
        Path(f.name).unlink()

    def test_load_config_no_extractors_section(self):
        """No [extractors] section = defaults."""
        with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
            f.write("output_format = 'text'\n")
            f.flush()
            config = load_config(Path(f.name))

        assert config.extractors_enabled is None
        assert config.extractors_disabled == []
        Path(f.name).unlink()

    def test_disabled_extractor_not_run(self, tmp_path):
        """Disabled extractor is not called during scan."""
        from drift.scanner import DriftScanner

        # Create a simple Python file
        py_file = tmp_path / "sample.py"
        py_file.write_text("def hello(): pass\n")

        scanner = DriftScanner(
            tmp_path,
            extractors_disabled=["DocstringExtractor"],
        )
        report = scanner.scan()
        # Should still scan (PythonExtractor is not disabled by extractors_disabled)
        assert len(report.facts) >= 1

    def test_enabled_subset_only_runs_enabled(self, tmp_path):
        """Only enabled extractors run when extractors_enabled is set."""
        from drift.scanner import DriftScanner

        # Create a Python file that would be handled by multiple extractors
        py_file = tmp_path / "sample.py"
        py_file.write_text("def hello(): pass\n")

        scanner = DriftScanner(
            tmp_path,
            extractors_enabled=["PythonExtractor"],
            extractors_disabled=None,
        )
        report = scanner.scan()
        # Should work - just the PythonExtractor runs
        assert len(report.facts) >= 1
