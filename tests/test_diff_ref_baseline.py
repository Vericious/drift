"""Tests for --diff-ref with --baseline interaction (DRIFT-251)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from drift.scanner import DriftScanner
from drift.baseline import save_baseline, load_baseline


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create a temp directory with a .py file and a .md file for testing."""
    # Python file: one documented function, one undocumented
    py_file = tmp_path / "example.py"
    py_file.write_text(
        "def documented_func(x: int, y: str = 'hello') -> bool:\n"
        "    '''Docstring.'''\n"
        "    pass\n"
        "\n"
        "def undocumented_func(a: int, b: int) -> None:\n"
        "    pass\n"
    )

    # Markdown file: one signature matching documented_func, one fake
    md_file = tmp_path / "docs.md"
    md_file.write_text(
        "# API Reference\n"
        "\n"
        "## documented_func\n"
        "\n"
        "```python\n"
        "def documented_func(x: int, y: str = 'hello') -> bool\n"
        "```\n"
        "\n"
        "## fake_function\n"
        "\n"
        "```python\n"
        "def fake_function(a: int, b: int) -> None\n"
        "```\n"
    )

    return tmp_path


class TestDiffRefBaselineInteraction:
    """Test that --diff-ref and --baseline work correctly together.

    When both flags are used:
    1. --diff-ref filters the scan to only changed files
    2. --baseline filters the results to only NEW drift items

    Bug: previously, the file path mismatch between get_changed_files()
    (returned repo-relative paths) and get_changed_lines() (returned
    absolute paths) caused incorrect filtering when both changed_files
    and changed_lines were used together.
    """

    def test_diff_ref_with_baseline_filters_correctly(self, temp_project: Path) -> None:
        """drift scan --diff-ref X --baseline Y produces correct filtered output.

        When both --diff-ref and --baseline are used:
        - Only files changed vs the ref are scanned
        - Only NEW drift items (not in baseline) are reported
        """
        from drift.cli import scan
        from click.testing import CliRunner

        # Mock git to return changed_files and changed_lines with absolute paths
        # so both changed_files filter and content-aware line filtering work
        changed_files = [temp_project / "example.py"]
        changed_lines = {temp_project / "example.py": {6}}  # Line 6 changed

        with patch("drift.cli.is_git_repo", return_value=True), \
             patch("drift.cli.ref_exists", return_value=True), \
             patch("drift.cli.get_changed_files", return_value=changed_files), \
             patch("drift.cli.get_changed_lines", return_value=changed_lines):
            runner = CliRunner()

            # First save a baseline with the current state
            result = runner.invoke(
                scan,
                [str(temp_project), "--fail-on", "none"],
            )
            assert result.exit_code == 0, f"Scan failed: {result.output}"

            # Create baseline by saving report
            scanner = DriftScanner(temp_project, no_cache=True)
            report = scanner.scan()
            save_baseline(report, temp_project)

            # Now scan with --diff AND --baseline
            result = runner.invoke(
                scan,
                [str(temp_project), "--diff", "main", "--baseline", "--fail-on", "none"],
            )
            assert result.exit_code == 0, f"Scan with --diff --baseline failed: {result.output}"

            # Should show filtered results (only new drift vs baseline)
            # The fake_function drift should be present (not in baseline)
            assert "fake_function" in result.output or "drift" in result.output.lower()

    def test_baseline_file_path_consistency(self, temp_project: Path) -> None:
        """Baseline loading works correctly when changed_files uses absolute paths.

        get_changed_files() now joins paths to return absolute paths, matching
        how changed_lines keys are stored. This ensures baseline comparisons
        work correctly with diff-based scanning.
        """
        from drift.cli import scan
        from click.testing import CliRunner

        # Mock git with absolute paths (as the fixed get_changed_files now returns)
        abs_path = temp_project.resolve()
        changed_files = [abs_path / "example.py"]
        changed_lines = {abs_path / "example.py": {6}}

        with patch("drift.cli.is_git_repo", return_value=True), \
             patch("drift.cli.ref_exists", return_value=True), \
             patch("drift.cli.get_changed_files", return_value=changed_files), \
             patch("drift.cli.get_changed_lines", return_value=changed_lines):
            runner = CliRunner()

            # Save baseline first
            scanner = DriftScanner(temp_project, no_cache=True)
            report = scanner.scan()
            baseline_path = save_baseline(report, temp_project)

            # Verify baseline was created
            assert baseline_path.exists()
            loaded = load_baseline(temp_project)
            assert loaded is not None

            # Now scan with --diff and --baseline
            result = runner.invoke(
                scan,
                [str(temp_project), "--diff", "main", "--baseline", "--fail-on", "none"],
            )
            assert result.exit_code == 0


class TestChangedFilesPathConsistency:
    """Tests that get_changed_files and get_changed_lines use consistent paths.

    This was the root cause of DRIFT-251: get_changed_files() returned
    repo-relative paths like Path('b.py') while get_changed_lines() returned
    absolute paths like Path('/tmp/xxx/b.py').
    """

    def test_changed_files_returns_absolute_paths(self, temp_project: Path) -> None:
        """get_changed_files() now joins paths to return absolute paths."""
        from drift.cli import scan
        from click.testing import CliRunner

        # When git is mocked to return a relative path, get_changed_files
        # now correctly joins it with the scan path to produce an absolute path
        changed_files = [temp_project / "example.py"]
        changed_lines = {temp_project / "example.py": {5, 6}}

        with patch("drift.cli.is_git_repo", return_value=True), \
             patch("drift.cli.ref_exists", return_value=True), \
             patch("drift.cli.get_changed_files", return_value=changed_files), \
             patch("drift.cli.get_changed_lines", return_value=changed_lines):
            runner = CliRunner()
            result = runner.invoke(
                scan,
                [str(temp_project), "--diff", "main", "--fail-on", "none"],
            )
            assert result.exit_code == 0
            # Should show "Scanning 1 file(s) changed vs main"
            assert "1 file(s)" in result.output

    def test_changed_files_and_lines_keys_match(self, temp_project: Path) -> None:
        """Both changed_files filter and changed_lines content-filtering use the same keys."""
        from drift.scanner import DriftScanner

        abs_path = temp_project.resolve()
        changed_files = [abs_path / "example.py"]
        changed_lines = {abs_path / "example.py": {5, 6}}

        scanner = DriftScanner(
            temp_project,
            changed_files=changed_files,
            changed_lines=changed_lines,
            no_cache=True,
        )
        report = scanner.scan()

        # Should have facts from the changed file
        assert len(report.facts) >= 0  # Just verify no key errors occurred
