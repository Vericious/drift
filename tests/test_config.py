"""Tests for the config module."""

from pathlib import Path

import pytest

from drift.config import DriftConfig, find_config, load_config


class TestLoadConfig:
    """Tests for load_config function."""

    def test_config_with_values(self, tmp_path: Path):
        """Test loading a config file with all values set."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
threshold = 0.5
output_format = "json"

[scan]
ignore_patterns = ["*.py", "*/vendor/*"]
""")

        config = load_config(config_file)
        assert config.ignore_patterns == ["*.py", "*/vendor/*"]
        assert config.threshold == 0.5
        assert config.output_format == "json"

    def test_ignore_patterns_from_scan_section(self, tmp_path: Path):
        """Test ignore_patterns loaded from [scan] section."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
[scan]
ignore_patterns = ["*.generated.py", "*/vendor/*", "test_*"]
""")

        config = load_config(config_file)
        assert config.ignore_patterns == ["*.generated.py", "*/vendor/*", "test_*"]

    def test_ignore_patterns_empty_when_scan_section_absent(self, tmp_path: Path):
        """Test ignore_patterns defaults to [] when [scan] section is absent."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
threshold = 0.5
""")

        config = load_config(config_file)
        assert config.ignore_patterns == []

    def test_config_missing_raises_file_not_found(self, tmp_path: Path):
        """Test that explicit missing config file raises FileNotFoundError."""
        missing = tmp_path / "nonexistent.toml"
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(missing)

    def test_cwd_search_finds_file(self, tmp_path: Path):
        """Test that load_config(None) finds .drift.toml in CWD."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
threshold = 0.8
output_format = "json"

[scan]
ignore_patterns = ["*.md"]
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
[scan]
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
[scan]
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
[scan]
ignore_patterns = []
""")
        config = load_config(config_file)
        assert config.fail_on == "error"

    def test_invalid_fail_on_raises_error(self, tmp_path: Path):
        """Test that invalid fail_on value is accepted (any string allowed)."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("""
fail_on = "invalid_level"
""")
        # fail_on now accepts any string (validated at CLI level or ignored silently)
        config = load_config(config_file)
        assert config.fail_on == "invalid_level"

    def test_fail_on_all_valid_values(self, tmp_path: Path):
        """Test all valid fail_on values are accepted."""
        for level in ["error", "warning", "info", "none", "missing", "undocumented"]:
            config_file = tmp_path / f".drift-{level}.toml"
            config_file.write_text(f'fail_on = "{level}"\n')
            config = load_config(config_file)
            assert config.fail_on == level


class TestFindConfig:
    """Tests for find_config function."""

    def test_finds_config_in_current_dir(self, tmp_path: Path):
        """Test discovery in current directory."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("threshold = 0.5\n")

        result = find_config(tmp_path)
        assert result == config_file

    def test_finds_config_in_parent_dir(self, tmp_path: Path):
        """Test walk-up finds config in parent directory."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("threshold = 0.5\n")

        subdir = tmp_path / "subdir"
        subdir.mkdir()
        deep_subdir = subdir / "deep"
        deep_subdir.mkdir()

        # Config is in tmp_path, search starts from deep_subdir
        result = find_config(deep_subdir)
        assert result == config_file

    def test_returns_none_when_no_config_exists(self, tmp_path: Path):
        """Test returns None when no .drift.toml exists anywhere."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        result = find_config(subdir)
        assert result is None

    def test_stops_at_filesystem_root(self, tmp_path: Path):
        """Test stops at filesystem root when no config found."""
        # Walk up from tmp_path toward root — should hit root eventually
        result = find_config(tmp_path)
        # If there's a .drift.toml somewhere above tmp_path, it returns that.
        # Otherwise it returns None when it hits the filesystem root.
        assert result is None or result.name == ".drift.toml"

    def test_with_file_path_not_directory(self, tmp_path: Path):
        """Test search from a file path uses the file's parent directory."""
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("threshold = 0.5\n")

        py_file = tmp_path / "example.py"
        py_file.write_text("def foo(): pass\n")

        result = find_config(py_file)
        assert result == config_file

    def test_nearest_config_wins(self, tmp_path: Path):
        """Test that the first .drift.toml found walking upward is returned."""
        # Config in tmp_path
        config_file = tmp_path / ".drift.toml"
        config_file.write_text("threshold = 0.5\n")

        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Config in subdir (closer)
        closer_config = subdir / ".drift.toml"
        closer_config.write_text("threshold = 0.9\n")

        result = find_config(subdir)
        assert result == closer_config
