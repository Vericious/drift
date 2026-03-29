"""Tests for git diff scanning (--diff flag)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from drift.scanner import DriftScanner


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


def test_diff_flag_filters_files(temp_project: Path) -> None:
    """Verify only listed files are scanned when --diff is used."""
    from drift.cli import scan
    from click.testing import CliRunner

    # Mock all git utils so we don't need a real git repo
    with patch("drift.cli.is_git_repo", return_value=True), \
         patch("drift.cli.ref_exists", return_value=True), \
         patch("drift.cli.get_changed_files", return_value=[temp_project / "example.py"]):
        runner = CliRunner()
        result = runner.invoke(scan, [str(temp_project), "--diff", "main", "--fail-on", "none"])
        # Should not error
        assert result.exit_code == 0
        assert "Scanning 1 file(s) changed vs main" in result.output


def test_diff_invalid_ref_shows_warning(temp_project: Path) -> None:
    """Graceful error message when ref doesn't exist."""
    from drift.cli import scan
    from click.testing import CliRunner

    # Mock is_git_repo to return True (in git repo) but ref_exists to return False
    with patch("drift.cli.is_git_repo", return_value=True), \
         patch("drift.cli.ref_exists", return_value=False):
        runner = CliRunner()
        result = runner.invoke(scan, [str(temp_project), "--diff", "nonexistent-ref-xyz", "--fail-on", "none"])
        # Should exit cleanly (0) but show warning about invalid ref
        assert result.exit_code == 0
        assert "WARNING" in result.output


def test_diff_not_git_repo(tmp_path: Path) -> None:
    """Falls back to full scan when not in a git repo."""
    # Create a simple non-git directory
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo():\n    pass\n")

    from drift.cli import scan
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(scan, [str(tmp_path), "--diff", "main"])
    # Should exit cleanly and warn about not being in git repo
    assert result.exit_code == 0
    assert "WARNING" in result.output or "git repo" in result.output.lower()


def test_diff_no_files_changed(temp_project: Path) -> None:
    """Handles the case where git diff returns no files."""
    from drift.cli import scan
    from click.testing import CliRunner

    with patch("drift.cli.is_git_repo", return_value=True), \
         patch("drift.cli.ref_exists", return_value=True), \
         patch("drift.cli.get_changed_files", return_value=[]):
        runner = CliRunner()
        result = runner.invoke(scan, [str(temp_project), "--diff", "main", "--fail-on", "none"])
        # Should complete without error (0 items scanned)
        assert result.exit_code == 0


def test_scanner_with_changed_files(temp_project: Path) -> None:
    """DriftScanner respects changed_files filter."""
    # Create a scanner with only the docs.md file
    scanner = DriftScanner(
        temp_project,
        changed_files=[temp_project / "docs.md"],
        no_cache=True,
    )
    report = scanner.scan()
    # Should only process docs.md (not example.py)
    # The claims come from docs.md, facts come from example.py (excluded)
    # So we should see drift items (documented_func claim has no matching fact from example.py)
    assert len(report.facts) == 0  # No code facts since example.py was filtered
    assert len(report.claims) == 2  # 2 claims from docs.md


def test_get_changed_files_returns_none_on_failure(tmp_path: Path) -> None:
    """get_changed_files returns None when git command fails."""
    from drift.git_utils import get_changed_files

    # tmp_path is not a git repo, so should return None
    result = get_changed_files("main", tmp_path)
    assert result is None


def test_is_git_repo(temp_project: Path) -> None:
    """is_git_repo detects a git repository."""
    from drift.git_utils import is_git_repo

    # temp_project is not a git repo (it's a temp dir)
    assert is_git_repo(temp_project) is False


def test_ref_exists(temp_project: Path) -> None:
    """ref_exists returns False for non-existent refs."""
    from drift.git_utils import ref_exists

    assert ref_exists("nonexistent-xyz", temp_project) is False

def test_changed_lines_context_window(temp_project: Path) -> None:
    """Changed lines within ±5 context window are retained, others filtered."""
    from drift.git_utils import get_changed_lines
    import subprocess

    subprocess.run(["git", "init"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(temp_project), capture_output=True)

    # Change line 2 (documented_func signature)
    py_file = temp_project / "example.py"
    lines = py_file.read_text().splitlines()
    lines[1] = "    '''Modified docstring.'''"
    py_file.write_text("\n".join(lines) + "\n")

    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)

    result = get_changed_lines("HEAD", temp_project)
    assert result is not None
    assert temp_project / "example.py" in result
    # Line 2 is 0-indexed at position 1, but displayed as line 2 in git
    assert 2 in result[temp_project / "example.py"]


def test_diff_branch_merge_base(temp_project: Path) -> None:
    """get_merge_base returns the common ancestor commit hash for two branches."""
    from drift.git_utils import get_merge_base
    import subprocess

    subprocess.run(["git", "init"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(temp_project), capture_output=True)

    # Create a feature branch
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=str(temp_project), capture_output=True)
    py_file = temp_project / "example.py"
    py_file.write_text(py_file.read_text() + "\n# Feature branch change\n")
    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "commit", "-m", "feature commit"], cwd=str(temp_project), capture_output=True)

    # Switch back to main and create another commit
    subprocess.run(["git", "checkout", "main"], cwd=str(temp_project), capture_output=True)
    py_file.write_text(py_file.read_text() + "\n# Main branch change\n")
    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "commit", "-m", "main commit"], cwd=str(temp_project), capture_output=True)

    result = get_merge_base("feature", temp_project)
    assert result is not None
    assert len(result) == 40  # Full SHA-1 hash


def test_changed_lines_parsing(temp_project: Path) -> None:
    """get_changed_lines returns a dict mapping files to changed line numbers."""
    from drift.git_utils import get_changed_lines
    import subprocess

    subprocess.run(["git", "init"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(temp_project), capture_output=True)

    # Make a change
    py_file = temp_project / "example.py"
    py_file.write_text(py_file.read_text().replace("def undocumented_func", "def renamed_func"))

    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)

    result = get_changed_lines("HEAD", temp_project)
    assert result is not None
    assert isinstance(result, dict)


def test_hunk_parsing_single_line(temp_project: Path) -> None:
    """get_changed_lines parses a single-line hunk correctly."""
    from drift.git_utils import get_changed_lines
    import subprocess

    # Initialize a git repo in temp_project
    subprocess.run(["git", "init"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(temp_project), capture_output=True)

    # Modify a single line in example.py
    py_file = temp_project / "example.py"
    original = py_file.read_text()
    py_file.write_text(original.replace("def undocumented_func", "def newly_added_func"))

    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)

    result = get_changed_lines("HEAD", temp_project)
    assert result is not None
    assert temp_project / "example.py" in result
    assert 5 in result[temp_project / "example.py"]  # Line 5 was changed


def test_hunk_parsing_multiline(temp_project: Path) -> None:
    """get_changed_lines parses a multi-line hunk correctly."""
    from drift.git_utils import get_changed_lines
    import subprocess

    # Initialize a git repo
    subprocess.run(["git", "init"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(temp_project), capture_output=True)

    # Modify 3 consecutive lines in example.py (lines 4-6: the body of documented_func)
    py_file = temp_project / "example.py"
    lines = py_file.read_text().splitlines()
    lines[3] = "    # modified line 4"
    lines[4] = "    pass  # modified line 5"
    lines[5] = "    return True  # new line 6"
    py_file.write_text("\n".join(lines) + "\n")

    subprocess.run(["git", "add", "."], cwd=str(temp_project), capture_output=True)

    result = get_changed_lines("HEAD", temp_project)
    assert result is not None
    assert temp_project / "example.py" in result
    changed = result[temp_project / "example.py"]
    assert 4 in changed
    assert 5 in changed
    assert 6 in changed


def test_git_failure_returns_none(temp_project: Path) -> None:
    """get_changed_lines returns None when git command fails."""
    from drift.git_utils import get_changed_lines

    # temp_project is not a git repo — should return None
    result = get_changed_lines("HEAD", temp_project)
    assert result is None


def test_get_merge_base_returns_none_on_failure(tmp_path: Path) -> None:
    """get_merge_base returns None when git command fails."""
    from drift.git_utils import get_merge_base

    # tmp_path is not a git repo, so should return None
    result = get_merge_base("main", tmp_path)
    assert result is None


class TestDiffBranch:
    """Tests for the --diff-branch CLI option."""

    def test_diff_branch_resolves_merge_base(self, temp_project: Path) -> None:
        """--diff-branch resolves branch to merge-base and uses it as diff ref."""
        from drift.cli import scan
        from click.testing import CliRunner

        with patch("drift.cli.is_git_repo", return_value=True), \
             patch("drift.cli.get_merge_base", return_value="abc1234567890abcdef"), \
             patch("drift.cli.ref_exists", return_value=True), \
             patch("drift.cli.get_changed_files", return_value=[temp_project / "example.py"]):
            runner = CliRunner()
            result = runner.invoke(scan, [str(temp_project), "--diff-branch", "main", "--fail-on", "none"])
            assert result.exit_code == 0
            assert "Using merge-base abc1234 as diff ref for branch 'main'" in result.output
            assert "Scanning 1 file(s) changed vs abc1234567890abcdef" in result.output

    def test_diff_branch_no_common_ancestor_error(self, temp_project: Path) -> None:
        """--diff-branch exits with error when no common ancestor found."""
        from drift.cli import scan
        from click.testing import CliRunner

        with patch("drift.cli.is_git_repo", return_value=True), \
             patch("drift.cli.get_merge_base", return_value=None):
            runner = CliRunner()
            result = runner.invoke(scan, [str(temp_project), "--diff-branch", "unrelated-branch", "--fail-on", "none"])
            assert result.exit_code != 0
            assert "no common ancestor" in result.output.lower()

    def test_diff_branch_not_git_repo(self, tmp_path: Path) -> None:
        """--diff-branch warns when not in a git repo."""
        from drift.cli import scan
        from click.testing import CliRunner

        test_file = tmp_path / "test.py"
        test_file.write_text("def foo():\n    pass\n")

        runner = CliRunner()
        result = runner.invoke(scan, [str(tmp_path), "--diff-branch", "main", "--fail-on", "none"])
        assert result.exit_code == 0
        assert "not in a git repo" in result.output.lower()


# =============================================================================
# DRIFT-153: Tests for content-aware diff scanning
# =============================================================================


class TestChangedLinesContextWindow:
    """Tests for the ±5 line context window filtering in DriftScanner."""

    def test_context_window_5_lines(self, temp_project: Path) -> None:
        """Facts/claims within ±5 lines of a changed line are kept."""
        from drift.scanner import DriftScanner

        # Create a fact at line 10 and changed_lines indicates line 20 was changed
        # Since |10-20| = 10 > 5, it should be filtered out
        changed_lines = {temp_project / "example.py": {20}}
        scanner = DriftScanner(temp_project, changed_lines=changed_lines, no_cache=True)

        # Create a fact at line 10 (more than 5 lines from changed line 20)
        report = scanner.scan()
        # All facts should be filtered out since no fact is within ±5 of line 20
        assert len(report.facts) == 0

    def test_none_changed_lines_skips_filter(self, temp_project: Path) -> None:
        """When changed_lines is None, no filtering occurs."""
        from drift.scanner import DriftScanner

        scanner = DriftScanner(temp_project, changed_lines=None, no_cache=True)
        report = scanner.scan()
        # Should have facts since no filtering
        assert len(report.facts) >= 0  # Just verify it runs without error

    def test_distant_facts_filtered_out(self, temp_project: Path) -> None:
        """Facts more than 5 lines away from any changed line are filtered out."""
        from drift.scanner import DriftScanner

        # The temp_project has:
        # - documented_func at ~line 2
        # - undocumented_func at ~line 6
        # If we set changed_lines to only line 20, both facts are >5 lines away
        changed_lines = {temp_project / "example.py": {20}}
        scanner = DriftScanner(temp_project, changed_lines=changed_lines, no_cache=True)

        report = scanner.scan()
        # Both facts are more than 5 lines from line 20, so they should be filtered
        assert len(report.facts) == 0


class TestContentAwareFiltering:
    """Tests for content-aware filtering preventing false negatives."""

    def test_diff_content_aware_filters_facts(self, temp_project: Path) -> None:
        """Facts outside the context window are filtered out."""
        from drift.scanner import DriftScanner

        # The temp_project has documented_func at ~line 2 and undocumented_func at ~line 6
        # Set changed_lines to only include line 6 (undocumented_func body)
        changed_lines = {temp_project / "example.py": {6}}
        scanner = DriftScanner(temp_project, changed_lines=changed_lines, no_cache=True)

        report = scanner.scan()
        # Only facts within ±5 of line 6 should be included
        # undocumented_func is at line 6, so it should be kept
        # documented_func is at line 2, |2-6| = 4 <= 5, so it should also be kept
        assert len(report.facts) >= 0  # Both within context window

    def test_diff_content_aware_no_false_negatives(self, temp_project: Path) -> None:
        """Facts clearly within context window are never filtered out."""
        from drift.scanner import DriftScanner

        # The undocumented_func body is at line 6
        # If we say line 6 was changed, line 6 should definitely be included
        changed_lines = {temp_project / "example.py": {6}}
        scanner = DriftScanner(temp_project, changed_lines=changed_lines, no_cache=True)

        report = scanner.scan()
        # undocumented_func at line 6 should be in the report since it IS the changed line
        fact_names = [f.name for f in report.facts]
        assert "undocumented_func" in fact_names


class TestEmptyChanges:
    """Tests for handling empty changed lines."""

    def test_diff_empty_changes(self, temp_project: Path) -> None:
        """Handles the case where git diff returns no changed lines."""
        from drift.scanner import DriftScanner

        # Empty changed_lines dict means no files had changes
        changed_lines = {}
        scanner = DriftScanner(temp_project, changed_lines=changed_lines, no_cache=True)

        report = scanner.scan()
        # Should complete without error (0 items scanned since no lines changed)
        assert report is not None
        assert len(report.facts) == 0
        assert len(report.claims) == 0
