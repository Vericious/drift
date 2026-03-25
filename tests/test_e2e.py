"""End-to-end integration tests for the Drift CLI.

These tests exercise the full CLI as a subprocess — not through imports —
to verify the complete user-facing workflow.
"""
import subprocess
import sys
from pathlib import Path

import pytest


DRIFT_CMD = [sys.executable, "-m", "drift"]


class TestDriftE2E:
    """E2E tests running the drift CLI as a subprocess."""

    def test_scan_clean_dir_no_drift(self, tmp_path: Path) -> None:
        """When no drift exists, exit code is 0."""
        # Create a Python file with a documented function
        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def with_params(a: int, b: str = 'hi') -> bool:\n"
            "    '''A useful function.'''\n"
            "    return True\n"
        )

        # Create a markdown file with correct documentation
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# API\n\n"
            "## with_params\n\n"
            "```python\n"
            "def with_params(a: int, b: str = 'hi') -> bool\n"
            "```\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Expected 0 (no drift), got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "No drift detected" in result.stdout

    def test_scan_with_drift_exit_code_1(self, tmp_path: Path) -> None:
        """When drift exists (error-severity), exit code is 1."""
        # Create a Python file with a function that has TWO params
        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def with_params(a: int, b: str = 'hi') -> bool:\n"
            "    '''A useful function.'''\n"
            "    return True\n"
        )

        # Create a markdown that documents only ONE param (missing b)
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# API\n\n"
            "Use `with_params(a: int)`.\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, f"Expected 1 (drift detected), got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "No drift detected" not in result.stdout

    def test_scan_json_output(self, tmp_path: Path) -> None:
        """--json flag outputs valid JSON."""
        # Clean directory
        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def foo(x: int) -> str:\n"
            "    return str(x)\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "```python\n"
            "def foo(x: int) -> str\n"
            "```\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--json"],
            capture_output=True,
            text=True,
        )

        import json
        data = json.loads(result.stdout)
        assert "scanned_path" in data
        assert "has_drift" in data
        assert "summary" in data
        assert data["has_drift"] is False

    def test_scan_with_drift_json_has_errors(self, tmp_path: Path) -> None:
        """When drift exists, JSON output has has_drift=True and errors > 0."""
        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def with_params(a: int, b: str = 'hi') -> bool:\n"
            "    return True\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "Use `with_params(a: int)`.\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--json"],
            capture_output=True,
            text=True,
        )

        import json
        data = json.loads(result.stdout)
        assert data["has_drift"] is True
        assert data["summary"]["errors"] >= 1

    def test_scan_missing_path_exits_2(self, tmp_path: Path) -> None:
        """Scanning a non-existent path exits with 2 (Click's standard error)."""
        result = subprocess.run(
            DRIFT_CMD + ["scan", "/nonexistent/path/that/does/not/exist"],
            capture_output=True,
            text=True,
        )
        # Click exits 2 when argument validation fails
        assert result.returncode == 2


class TestDriftIgnore:
    """Tests for .driftignore file support."""

    def test_driftignore_excludes_file(self, tmp_path: Path) -> None:
        """A file matching .driftignore is not scanned."""
        # Create a .driftignore file
        ignore_file = tmp_path / ".driftignore"
        ignore_file.write_text("bad_docs.md\n")

        # Create a Python file with a function
        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def my_func(x: int) -> bool:\n"
            "    return True\n"
        )

        # Create two markdown files:
        # - good_docs.md: correctly documents my_func → no drift
        # - bad_docs.md: documents my_func with wrong signature → drift
        #   (but bad_docs.md is ignored, so no drift is reported)
        good_md = tmp_path / "good_docs.md"
        good_md.write_text(
            "```python\n"
            "def my_func(x: int) -> bool\n"
            "```\n"
        )
        bad_md = tmp_path / "bad_docs.md"
        bad_md.write_text(
            "```python\n"
            "def my_func(x: int, extra: str) -> bool\n"
            "```\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        # Since bad_docs.md is ignored and good_docs.md is correct,
        # we should get no drift
        assert result.returncode == 0, f"Expected 0 (no drift), got {result.returncode}\nstdout: {result.stdout}"
        assert "No drift detected" in result.stdout

    def test_driftignore_with_glob_pattern(self, tmp_path: Path) -> None:
        """.driftignore supports glob patterns like README*.md."""
        ignore_file = tmp_path / ".driftignore"
        ignore_file.write_text("README*.md\n")  # Ignore README files only

        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def my_func(x: int) -> bool:\n"
            "    return True\n"
        )
        # This markdown correctly documents my_func
        good_md = tmp_path / "good_docs.md"
        good_md.write_text(
            "```python\n"
            "def my_func(x: int) -> bool\n"
            "```\n"
        )
        # This markdown would cause drift but is ignored via glob
        bad_md = tmp_path / "README_old.md"
        bad_md.write_text(
            "```python\n"
            "def my_func(x: int, extra: str) -> bool\n"
            "```\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        # Since README_old.md is ignored (matches README*.md) and good_docs.md is correct,
        # no drift should be found
        assert result.returncode == 0, f"Expected 0 (ignored), got {result.returncode}\nstdout: {result.stdout}"
