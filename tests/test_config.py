"""Tests for the config module."""

from pathlib import Path

import pytest

from drift.config import DriftConfig, load_config


class TestLoadConfig:
    """Tests for load_config function."""

    def test_config_with_values(self, tmp_path: Path):
        """Test loading a config file with all values set."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
ignore_patterns = ["*.py", "test_*"]
threshold = 0.5
output_format = "json"
""")

        config = load_config(config_file)
        assert config.ignore_patterns == ["*.py", "test_*"]
        assert config.threshold == 0.5
        assert config.output_format == "json"

    def test_config_missing_raises_file_not_found(self, tmp_path: Path):
        """Test that explicit missing config file raises FileNotFoundError."""
        missing = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(missing)

    def test_cwd_search_finds_file(self, tmp_path: Path):
        """Test that load_config(None) finds .drift.toml in CWD."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
ignore_patterns = ["*.md"]
threshold = 0.8
output_format = "json"
""")

        old_cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)
            config = load_config(None)
            assert config.ignore_patterns == ["*.md"]
            assert config.threshold == 0.8
            assert config.output_format == "json"
        finally:
            os.chdir(old_cwd)

    def test_cwd_search_missing_returns_defaults(self, tmp_path: Path):
        """Test that load_config(None) returns defaults when no .drift.toml."""
        old_cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)
            config = load_config(None)
            assert config.ignore_patterns == []
            assert config.threshold == 0.0
            assert config.output_format == "text"
        finally:
            os.chdir(old_cwd)

    def test_invalid_toml_error_message(self, tmp_path: Path):
        """Test that invalid TOML produces a helpful error message."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
ignore_patterns = "not a list"
""")

        with pytest.raises(ValueError, match="must be a list"):
            load_config(config_file)

    def test_invalid_threshold(self, tmp_path: Path):
        """Test that threshold must be a number."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
threshold = "not a number"
""")

        with pytest.raises(ValueError, match="must be a number"):
            load_config(config_file)

    def test_threshold_out_of_range(self, tmp_path: Path):
        """Test that threshold must be between 0.0 and 1.0."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
threshold = 1.5
""")

        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            load_config(config_file)

    def test_invalid_output_format(self, tmp_path: Path):
        """Test that output_format must be 'text' or 'json'."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
output_format = "yaml"
""")

        with pytest.raises(ValueError, match="must be 'text' or 'json'"):
            load_config(config_file)

    def test_partial_config_uses_defaults(self, tmp_path: Path):
        """Test that missing keys use defaults."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
ignore_patterns = ["*.py"]
""")

        config = load_config(config_file)
        assert config.ignore_patterns == ["*.py"]
        assert config.threshold == 0.0
        assert config.output_format == "text"

    def test_config_with_empty_values(self, tmp_path: Path):
        """Test config with empty lists and zero threshold."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
ignore_patterns = []
threshold = 0.0
output_format = "text"
""")

        config = load_config(config_file)
        assert config.ignore_patterns == []
        assert config.threshold == 0.0
        assert config.output_format == "text"


class TestDriftConfig:
    """Tests for DriftConfig dataclass."""

    def test_default_values(self):
        """Test DriftConfig default values."""
        config = DriftConfig()
        assert config.ignore_patterns == []
        assert config.threshold == 0.0
        assert config.output_format == "text"

    def test_custom_values(self):
        """Test DriftConfig with custom values."""
        config = DriftConfig(
            ignore_patterns=["*.py", "*.md"],
            threshold=0.7,
            output_format="json",
        )
        assert config.ignore_patterns == ["*.py", "*.md"]
        assert config.threshold == 0.7
        assert config.output_format == "json"


class TestFailOnConfig:
    """Tests for fail_on field in DriftConfig."""

    def test_default_fail_on_is_error(self):
        """Test DriftConfig default fail_on is 'error'."""
        config = DriftConfig()
        assert config.fail_on == "error"

    def test_fail_on_custom_value(self):
        """Test DriftConfig with custom fail_on value."""
        config = DriftConfig(fail_on="warning")
        assert config.fail_on == "warning"

    def test_load_fail_on_from_config(self, tmp_path: Path):
        """Test loading fail_on from TOML config file."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
fail_on = "warning"
""")
        config = load_config(config_file)
        assert config.fail_on == "warning"

    def test_load_fail_on_none_from_config(self, tmp_path: Path):
        """Test loading fail_on = 'none' (CI info-only mode) from config."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
fail_on = "none"
""")
        config = load_config(config_file)
        assert config.fail_on == "none"

    def test_load_fail_on_info_from_config(self, tmp_path: Path):
        """Test loading fail_on = 'info' from config."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
fail_on = "info"
""")
        config = load_config(config_file)
        assert config.fail_on == "info"

    def test_fail_on_defaults_to_error_when_missing(self, tmp_path: Path):
        """Test fail_on defaults to 'error' when not in config."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
ignore_patterns = []
""")
        config = load_config(config_file)
        assert config.fail_on == "error"

    def test_invalid_fail_on_raises_error(self, tmp_path: Path):
        """Test that invalid fail_on value raises ValueError."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
fail_on = "invalid_level"
""")
        with pytest.raises(ValueError, match="fail_on must be"):
            load_config(config_file)

    def test_fail_on_all_valid_values(self, tmp_path: Path):
        """Test all valid fail_on values are accepted."""
        for level in ["error", "warning", "info", "none"]:
            config_file = tmp_path / f".drift-{level}.toml"
            config_file.write_text(f'fail_on = "{level}"\n')
            config = load_config(config_file)
            assert config.fail_on == level
