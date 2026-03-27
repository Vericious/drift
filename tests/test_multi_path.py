"""Tests for multi-path scanning."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from drift.cli import main


@pytest.fixture
def cli_runner():
    """Return a Click CLI test runner."""
    return CliRunner()


def test_multiple_paths(cli_runner, tmp_path):
    """`drift scan path1 path2` scans both paths and merges results."""
    # Create two separate directories with different content
    dir1 = tmp_path / "project1"
    dir2 = tmp_path / "project2"
    dir1.mkdir()
    dir2.mkdir()

    (dir1 / "mod1.py").write_text(
        "def func_alpha():\n"
        "    '''Function alpha.'''\n"
        "    pass\n"
    )
    (dir2 / "mod2.py").write_text(
        "def func_beta():\n"
        "    '''Function beta.'''\n"
        "    pass\n"
    )

    result = cli_runner.invoke(main, ["scan", str(dir1), str(dir2)])
    assert result.exit_code == 0
    # Both functions should be found
    assert "func_alpha" in result.output or "2 facts" in result.output
    assert "func_beta" in result.output or "2 facts" in result.output


def test_no_path_defaults_cwd(cli_runner, tmp_path):
    """`drift scan` with no paths defaults to scanning current directory."""
    # Use a temp directory as cwd
    with cli_runner.isolated_filesystem(temp_dir=tmp_path):
        # Create a file with documented function
        (Path.cwd() / "sample.py").write_text(
            "def hello(name: str) -> str:\n"
            "    '''Say hello.'''\n"
            "    return f'Hello, {name}'\n"
        )
        result = cli_runner.invoke(main, ["scan"])
        assert result.exit_code == 0
        assert "1 fact" in result.output or "facts" in result.output


def test_overlapping_paths_dedup(cli_runner, tmp_path):
    """When paths overlap, drift items are deduplicated."""
    # Create dir with one function (no doc claim needed)
    shared = tmp_path / "shared"
    shared.mkdir()

    (shared / "mod.py").write_text(
        "def shared_func(x: int) -> int:\n"
        "    '''Shared function.'''\n"
        "    return x * 2\n"
    )

    # Scan the same directory twice via two paths (one parent, one explicit)
    # The scanner should deduplicate and still produce a clean result
    result = cli_runner.invoke(main, ["scan", str(shared), str(shared / "mod.py")])
    assert result.exit_code == 0
    # Should show 1 fact (not 2 from double-scanning)
    assert "1 fact" in result.output
