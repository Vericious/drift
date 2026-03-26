"""Tests for the Drift CLI."""
import pytest
from click.testing import CliRunner

from drift.cli import main


@pytest.fixture
def cli_runner():
    """Return a Click CLI test runner."""
    return CliRunner()


def test_version(cli_runner):
    """`drift --version` returns 0 and contains version string."""
    result = cli_runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert "0.2.0" in result.output


def test_help(cli_runner):
    """`drift --help` returns 0."""
    result = cli_runner.invoke(main, ["--help"])
    assert result.exit_code == 0


def test_scan_with_temp_dir(cli_runner, tmp_path):
    """`drift scan` with a temp directory returns 0 and shows no drift."""
    result = cli_runner.invoke(main, ["scan", str(tmp_path)])
    assert result.exit_code == 0
    assert "No drift detected" in result.output
    assert "0 facts" in result.output
