"""Tests for watch mode (DRIFT-042)."""

import pytest
import tempfile
import time
from pathlib import Path

from drift.cli import _get_watch_files, _file_mtimes


class TestWatchMode:
    def test_get_watch_files_py_md_rst_toml_yaml(self, tmp_path):
        """_get_watch_files returns py, md, rst, toml, yaml files."""
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.md").write_text("")
        (tmp_path / "c.rst").write_text("")
        (tmp_path / "d.toml").write_text("")
        (tmp_path / "e.yaml").write_text("")
        (tmp_path / "f.yml").write_text("")
        # Should be ignored
        (tmp_path / "g.pyc").write_text("")
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("")

        files = _get_watch_files(tmp_path)
        basenames = {f.name for f in files}
        assert "a.py" in basenames
        assert "b.md" in basenames
        assert "c.rst" in basenames
        assert "d.toml" in basenames
        assert "e.yaml" in basenames
        assert "f.yml" in basenames
        assert "g.pyc" not in basenames

    def test_get_watch_files_excludes_pycache(self, tmp_path):
        """Files under __pycache__ are excluded."""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "a.pyc").write_text("")
        (tmp_path / "b.py").write_text("")

        files = _get_watch_files(tmp_path)
        basenames = {f.name for f in files}
        assert "b.py" in basenames
        assert "a.pyc" not in basenames

    def test_get_watch_files_single_file(self, tmp_path):
        """If scan_path is a file, returns just that file."""
        f = tmp_path / "sample.py"
        f.write_text("")
        files = _get_watch_files(f)
        assert len(files) == 1
        assert files[0] == f

    def test_file_mtimes_returns_mtimes(self, tmp_path):
        """_file_mtimes returns current mtimes."""
        f = tmp_path / "a.py"
        f.write_text("")
        mtimes = _file_mtimes([f])
        assert f in mtimes
        assert mtimes[f] > 0

    def test_file_mtimes_nonexistent_file(self, tmp_path):
        """_file_mtimes returns 0 for nonexistent files."""
        nonexistent = tmp_path / "doesnotexist.py"
        mtimes = _file_mtimes([nonexistent])
        assert mtimes[nonexistent] == 0

    def test_file_mtimes_detects_change(self, tmp_path):
        """File mtime changes when file is modified."""
        f = tmp_path / "a.py"
        f.write_text("v1")
        time.sleep(0.1)  # ensure mtime difference
        mtimes_before = _file_mtimes([f])

        f.write_text("v2")
        time.sleep(0.1)
        mtimes_after = _file_mtimes([f])

        assert mtimes_after[f] > mtimes_before[f]

    def test_get_watch_files_nested(self, tmp_path):
        """_get_watch_files finds files in subdirectories."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.py").write_text("")
        (tmp_path / "root.py").write_text("")

        files = _get_watch_files(tmp_path)
        basenames = {f.name for f in files}
        assert "nested.py" in basenames
        assert "root.py" in basenames

    def test_watch_flag_accepted_by_scan(self):
        """--watch flag is accepted by the scan command (CLI smoke test)."""
        from click.testing import CliRunner
        from drift.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["scan", "--help"])
        assert "--watch" in result.output
