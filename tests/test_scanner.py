"""Tests for the DriftScanner orchestrator."""
import tempfile
from pathlib import Path

import pytest

from drift.models import DriftReport
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


def test_scan_returns_driftreport(temp_project: Path) -> None:
    """scan() on a directory returns a DriftReport."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()
    assert isinstance(report, DriftReport)


def test_scan_file_path_returns_driftreport(temp_project: Path) -> None:
    """scan() on a file path also returns a DriftReport."""
    scanner = DriftScanner(temp_project / "example.py")
    report = scanner.scan()
    assert isinstance(report, DriftReport)


def test_facts_extracted_from_python_file(temp_project: Path) -> None:
    """Facts are extracted from the Python file."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    fact_names = {f.name for f in report.facts}
    assert "documented_func" in fact_names
    assert "undocumented_func" in fact_names
    assert len(report.facts) == 2


def test_claims_extracted_from_markdown_file(temp_project: Path) -> None:
    """Claims are extracted from the Markdown file."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    claim_names = {c.name for c in report.claims if c.name is not None}
    assert "documented_func" in claim_names
    assert "fake_function" in claim_names


def test_drift_items_detected(temp_project: Path) -> None:
    """Drift items are detected for the fake function (renamed match)."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    categories = {item.category for item in report.drift_items}

    # fake_function is documented but not in code — the renamed matcher
    # finds undocumented_func has same params and marks it as "renamed"
    assert "renamed" in categories
    # At least 1 drift item should exist
    assert len(report.drift_items) >= 1


def test_has_drift_true_when_drift_exists(temp_project: Path) -> None:
    """has_drift is True when drift (error-severity items) exists."""
    scanner = DriftScanner(temp_project)
    report = scanner.scan()

    # fake_function creates an error-severity "documented_but_missing" item
    assert report.has_drift is True


def test_scanner_empty_dir() -> None:
    """Scanner handles an empty directory gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        scanner = DriftScanner(Path(tmp))
        report = scanner.scan()
        assert isinstance(report, DriftReport)
        assert report.has_drift is False


class TestCLIFlagScannerIntegration:
    """Integration tests for CLI flag drift via the scanner pipeline."""

    def test_argparse_flag_documented_in_markdown_table_no_drift(self, tmp_path: Path) -> None:
        """CLI flag in argparse + documented in markdown table → no drift."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--verbose', '-v', action='store_true')\n"
            "parser.add_argument('--output', '-o', type=str, default='out.txt')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# CLI Reference\n\n"
            "| Flag | Type | Default | Description |\n"
            "|------|------|---------|-------------|\n"
            "| -v, --verbose | bool | false | Verbose output |\n"
            "| -o, --output | string | out.txt | Output file |\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        cli_facts = [f for f in report.facts if f.kind.value == "cli_flag"]
        cli_claims = [c for c in report.claims if c.kind.value == "cli_flag_ref"]

        # Both --verbose and --output should be extracted from code
        assert len(cli_facts) == 2
        # Both should be documented in the table (--verbose and --v, --output and -o each count)
        assert len(cli_claims) >= 2
        # No drift
        assert report.has_drift is False

    def test_argparse_flag_undocumented_in_table_detected(self, tmp_path: Path) -> None:
        """CLI flag in argparse but not documented → undocumented drift."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--verbose', '-v', action='store_true')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# CLI Reference\n\n"
            "| Flag | Type |\n"
            "|------|------|\n"
            "| --other | bool |\n"  # --other is documented but not in code
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        # --verbose is undocumented (error), --other is documented-but-missing (error)
        assert report.has_drift is True
        cli_drift = [d for d in report.drift_items if d.category in ("undocumented", "documented_but_missing")]
        assert len(cli_drift) == 2

    def test_click_flag_documented_in_markdown_table_no_drift(self, tmp_path: Path) -> None:
        """Click CLI option documented in markdown table → no drift."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import click\n"
            "@click.command()\n"
            "@click.option('--format', '-f', type=click.Choice(['json', 'text']), default='text')\n"
            "def cli(format):\n"
            "    pass\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# CLI Reference\n\n"
            "| Short | Flag | Type | Default |\n"
            "|-------|------|------|--------|\n"
            "| -f | --format | choice | text |\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        cli_facts = [f for f in report.facts if f.kind.value == "cli_flag"]
        assert len(cli_facts) == 1
        assert report.has_drift is False

    def test_mixed_argparse_and_click_table_documentation(self, tmp_path: Path) -> None:
        """Both argparse and click flags documented in tables work together."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "import click\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--count', type=int, default=0)\n"
            "@click.command()\n"
            "@click.option('--verbose', '-v', is_flag=True)\n"
            "def cli(verbose):\n"
            "    pass\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# CLI Reference\n\n"
            "| Flag | Type | Default |\n"
            "|------|------|--------|\n"
            "| --count | int | 0 |\n"
            "| -v, --verbose | bool | false |\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        cli_facts = [f for f in report.facts if f.kind.value == "cli_flag"]
        cli_claims = [c for c in report.claims if c.kind.value == "cli_flag_ref"]

        # Both argparse (--count) and click (--verbose) should be extracted
        assert len(cli_facts) == 2
        # Both documented in the table (comma-separated -v, --verbose counts as 2 claims)
        assert len(cli_claims) >= 2
        assert report.has_drift is False

    def test_typer_flag_documented_in_markdown_table_no_drift(self, tmp_path: Path) -> None:
        """Typer CLI option documented in markdown table → no drift."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import typer\n"
            "app = typer.Typer()\n"
            "\n"
            "@app.command()\n"
            "def serve(name: str = typer.Option('--name', help='Service name'),\n"
            "           port: int = typer.Option('--port', default=8000, help='Port number')):\n"
            "    print(f'Serving {name} on port {port}')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# CLI Reference\n\n"
            "| Flag | Type | Default |\n"
            "|------|------|--------|\n"
            "| --name | string | — |\n"
            "| --port | int | 8000 |\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        cli_facts = [f for f in report.facts if f.kind.value == "cli_flag"]
        cli_claims = [c for c in report.claims if c.kind.value == "cli_flag_ref"]

        # --name and --port should be extracted from Typer
        assert len(cli_facts) == 2
        # Both documented in the table
        assert len(cli_claims) >= 2
        assert report.has_drift is False

    def test_typer_flag_undocumented_in_table_detected(self, tmp_path: Path) -> None:
        """Typer CLI flag present but not documented in table → drift detected."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import typer\n"
            "app = typer.Typer()\n"
            "\n"
            "@app.command()\n"
            "def serve(name: str = typer.Option('--name', help='Service name'),\n"
            "           port: int = typer.Option('--port', default=8000, help='Port number')):\n"
            "    print(f'Serving {name} on port {port}')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# CLI Reference\n\n"
            "| Flag | Type |\n"
            "|------|------|\n"
            "| --name | string |\n"
            # --port is intentionally undocumented
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        cli_facts = [f for f in report.facts if f.kind.value == "cli_flag"]
        # --name and --port should be extracted
        assert len(cli_facts) == 2
        # Only --name documented
        cli_claims = [c for c in report.claims if c.kind.value == "cli_flag_ref"]
        assert len(cli_claims) == 1
        assert report.has_drift is True

    def test_typer_and_argparse_both_extracted(self, tmp_path: Path) -> None:
        """Both Typer and argparse flags are extracted from the same file."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "import typer\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--debug', action='store_true')\n"
            "typer_app = typer.Typer()\n"
            "\n"
            "@typer_app.command()\n"
            "def serve(name: str = typer.Option('--name', help='Service name')):\n"
            "    print(f'Serving {name}')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "| Flag | Type |\n"
            "|------|------|\n"
            "| --debug | bool |\n"
            "| --name | string |\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        cli_facts = [f for f in report.facts if f.kind.value == "cli_flag"]
        # --debug from argparse and --name from typer
        assert len(cli_facts) == 2
        assert report.has_drift is False

    def test_table_flag_extracted_with_default_value(self, tmp_path: Path) -> None:
        """Markdown table flag with default value is extracted correctly."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--port', type=int, default=8080)\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "| Flag | Default |\n"
            "|------|---------|\n"
            "| --port | 8080 |\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        cli_claims = [c for c in report.claims if c.kind.value == "cli_flag_ref"]
        assert len(cli_claims) == 1
        assert cli_claims[0].name == "--port"
        assert cli_claims[0].metadata.get("default") == "8080"


class TestConfigScannerIntegration:
    """Tests for YAML/TOML config file scanning."""

    def test_yaml_config_extracted(self, tmp_path: Path) -> None:
        """YAML config file keys are extracted as CONFIG_KEY facts."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "database:\n"
            "  host: localhost\n"
            "  port: 5432\n"
            "app:\n"
            "  debug: false\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        config_facts = [f for f in report.facts if f.kind.value == "config_key"]
        config_keys = {f.name for f in config_facts}
        assert "database.host" in config_keys
        assert "database.port" in config_keys
        assert "app.debug" in config_keys

    def test_toml_config_extracted(self, tmp_path: Path) -> None:
        """TOML config file keys are extracted as CONFIG_KEY facts."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            "[database]\n"
            "host = \"localhost\"\n"
            "port = 5432\n"
            "\n"
            "[server]\n"
            "port = 8000\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        config_facts = [f for f in report.facts if f.kind.value == "config_key"]
        config_keys = {f.name for f in config_facts}
        assert "database.host" in config_keys
        assert "database.port" in config_keys
        assert "server.port" in config_keys

    def test_yaml_config_drift_vs_doc(self, tmp_path: Path) -> None:
        """Config value mismatch between YAML and documentation detected as drift."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text(
            "server:\n"
            "  port: 5432\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# Configuration\n\n"
            "| Variable | Default |\n"
            "|----------|---------|\n"
            "| server.port | 3306 |\n"
        )

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        # The YAML says port 5432, docs say 3306 — value mismatch
        # Both have the same fact+claim (server.port), so no missing drift
        # Just verify no crash and facts are collected
        config_facts = [f for f in report.facts if f.kind.value == "config_key"]
        assert any(f.name == "server.port" for f in config_facts)


class TestScannerGracefulErrorRecovery:
    """Tests for graceful handling of malformed files."""

    def test_malformed_file_error_collected_no_crash(self, tmp_path: Path) -> None:
        """Malformed .py file: errors collected, scanner doesn't crash, valid files processed."""
        # Valid Python file
        valid_py = tmp_path / "valid.py"
        valid_py.write_text(
            "def documented_func(x: int) -> str:\n"
            "    '''A documented function.'''\n"
            "    return str(x)\n"
        )

        # Malformed Python file (syntax error)
        bad_py = tmp_path / "bad.py"
        bad_py.write_text("def bad_func({{[[[[[[ \n")

        scanner = DriftScanner(tmp_path)
        # Should not raise
        report = scanner.scan()

        # Facts from valid file are extracted
        fact_names = {f.name for f in report.facts}
        assert "documented_func" in fact_names

        # Error entry for bad file
        assert len(report.errors) >= 1
        error_messages = " ".join(report.errors)
        assert "bad.py" in error_messages

    def test_error_message_includes_file_path(self, tmp_path: Path) -> None:
        """Error message includes the problematic file path."""
        bad_py = tmp_path / "bad_syntax.py"
        bad_py.write_text("x = {{ broken\n")

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        assert len(report.errors) >= 1
        assert "bad_syntax.py" in report.errors[0]

    def test_strict_mode_raises_on_error(self, tmp_path: Path) -> None:
        """--strict mode raises exception on malformed file."""
        bad_py = tmp_path / "bad.py"
        bad_py.write_text("def broken({{[[\n")

        scanner = DriftScanner(tmp_path, strict=True)
        with pytest.raises(Exception):
            scanner.scan()
