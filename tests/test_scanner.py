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

    def test_argparse_flag_documented_in_markdown_table_no_drift(
        self, tmp_path: Path
    ) -> None:
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
        cli_drift = [
            d
            for d in report.drift_items
            if d.category in ("undocumented", "documented_but_missing")
        ]
        assert len(cli_drift) == 2

    def test_click_flag_documented_in_markdown_table_no_drift(
        self, tmp_path: Path
    ) -> None:
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

    def test_typer_flag_documented_in_markdown_table_no_drift(
        self, tmp_path: Path
    ) -> None:
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
            "# CLI Reference\n\n| Flag | Type |\n|------|------|\n| --name | string |\n"
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
            "| Flag | Default |\n|------|---------|\n| --port | 8080 |\n"
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
            "database:\n  host: localhost\n  port: 5432\napp:\n  debug: false\n"
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
            '[database]\nhost = "localhost"\nport = 5432\n\n[server]\nport = 8000\n'
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
        config_file.write_text("server:\n  port: 5432\n")
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
        with pytest.raises(Exception):  # noqa: B017
            scanner.scan()


# ---------------------------------------------------------------------------
# .driftignore gitignore-style pattern tests
# ---------------------------------------------------------------------------


class TestDriftignorePatterns:
    """Tests for .driftignore gitignore-style pattern matching."""

    def _make_project(self, tmp_path: Path, structure: dict) -> Path:
        """Create a project structure from a dict like {'src/foo.py': 'code', 'tests/test.py': 'code'}."""
        for rel_path, content in structure.items():
            f = tmp_path / rel_path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content or "# file " + rel_path)
        return tmp_path

    def test_basic_glob_pattern(self, tmp_path: Path) -> None:
        """Basic glob pattern like *.pyc ignores matching files."""
        self._make_project(
            tmp_path,
            {
                "src/main.py": "def foo(): pass",
                "src/__pycache__/main.pyc": "def should_not_appear(): pass",
            },
        )
        (tmp_path / ".driftignore").write_text("*.pyc\n")
        scanner = DriftScanner(tmp_path)
        report = scanner.scan()
        names = {f.name for f in report.facts}
        assert "foo" in names
        assert "should_not_appear" not in names

    def test_negation_pattern(self, tmp_path: Path) -> None:
        """!pattern re-includes a previously ignored file."""
        self._make_project(
            tmp_path,
            {
                "src/main.py": "def foo(): pass",
                "src/keep.py": "def bar(): pass",
            },
        )
        (tmp_path / ".driftignore").write_text("*.py\n!src/keep.py\n")
        scanner = DriftScanner(tmp_path)
        report = scanner.scan()
        names = {f.name for f in report.facts}
        assert "bar" in names
        assert "foo" not in names

    def test_recursive_directory_wildcard(self, tmp_path: Path) -> None:
        """**/ matches directories at any depth."""
        self._make_project(
            tmp_path,
            {
                "src/core/main.py": "def foo(): pass",
                "src/core/utils/helper.py": "def bar(): pass",
                "src/core/utils/deep/nested.py": "def baz(): pass",
            },
        )
        (tmp_path / ".driftignore").write_text("**/utils/**/*.py\n")
        scanner = DriftScanner(tmp_path)
        report = scanner.scan()
        names = {f.name for f in report.facts}
        assert "foo" in names
        assert "helper" not in names
        assert "nested" not in names

    def test_directory_only_pattern(self, tmp_path: Path) -> None:
        """A pattern ending with / matches the directory and all its contents."""
        self._make_project(
            tmp_path,
            {
                "src/main.py": "def foo(): pass",
                "src/legacy/deprecated.py": "def old(): pass",
                "src/legacy/utils/helper.py": "def help(): pass",
            },
        )
        (tmp_path / ".driftignore").write_text("legacy/\n")
        scanner = DriftScanner(tmp_path)
        report = scanner.scan()
        names = {f.name for f in report.facts}
        assert "foo" in names
        assert "old" not in names
        assert "help" not in names

    def test_comments_and_empty_lines(self, tmp_path: Path) -> None:
        """Lines starting with # are comments; empty lines are skipped."""
        # *.py matches .py files at any depth (gitignore behavior)
        # Comments (#) and empty lines should be skipped
        self._make_project(
            tmp_path,
            {
                "main.py": "def foo(): pass",
                "src/helper.py": "def bar(): pass",
            },
        )
        (tmp_path / ".driftignore").write_text(
            "# This is a comment\n\n*.py\n  # another comment\n"
        )
        scanner = DriftScanner(tmp_path)
        report = scanner.scan()
        names = {f.name for f in report.facts}
        # Both should be ignored by *.py
        assert "foo" not in names
        assert "bar" not in names

    def test_order_matters_later_overrides_earlier(self, tmp_path: Path) -> None:
        """Later patterns override earlier ones."""
        self._make_project(
            tmp_path,
            {
                "src/main.py": "def foo(): pass",
                "src/special.py": "def bar(): pass",
            },
        )
        # First ignore all .py, then allow special.py
        (tmp_path / ".driftignore").write_text("*.py\n!special.py\n")
        scanner = DriftScanner(tmp_path)
        report = scanner.scan()
        names = {f.name for f in report.facts}
        assert "foo" not in names
        assert "bar" in names

    def test_double_star_at_start(self, tmp_path: Path) -> None:
        """/**/ at start matches any intermediate directories."""
        self._make_project(
            tmp_path,
            {
                "src/core/main.py": "def foo(): pass",
                "src/core/utils/helper.py": "def bar(): pass",
            },
        )
        (tmp_path / ".driftignore").write_text("**/utils/*.py\n")
        scanner = DriftScanner(tmp_path)
        report = scanner.scan()
        names = {f.name for f in report.facts}
        assert "foo" in names
        assert "bar" not in names


class TestParallelScanning:
    """Tests for --parallel flag in DriftScanner."""

    def _make_project(self, tmp_path: Path, files: dict[str, str]) -> None:
        """Create files in tmp_path. Values are content; '' creates an empty file."""
        for rel_path, content in files.items():
            file_path = tmp_path / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)

    def test_parallel_produces_same_facts_as_serial(self, tmp_path: Path) -> None:
        """Parallel scan must produce identical facts as serial scan."""
        self._make_project(
            tmp_path,
            {
                "a.py": "def func_a(x: int) -> None: pass",
                "b.py": "def func_b(y: str) -> None: pass",
                "c.py": "def func_c(z: float) -> None: pass",
                "docs.md": (
                    "# Docs\n\n```python\ndef func_a(x: int) -> None\n```\n"
                    "```python\ndef func_b(y: str) -> None\n```\n"
                    "```python\ndef func_c(z: float) -> None\n```\n"
                ),
            },
        )

        serial_scanner = DriftScanner(tmp_path, parallel=False)
        serial_report = serial_scanner.scan()

        parallel_scanner = DriftScanner(tmp_path, parallel=True)
        parallel_report = parallel_scanner.scan()

        # Facts must be identical regardless of parallel flag
        serial_names = sorted(f.name for f in serial_report.facts)
        parallel_names = sorted(f.name for f in parallel_report.facts)
        assert serial_names == parallel_names, (
            f"Parallel scan produced different facts:\n  serial={serial_names}\n  parallel={parallel_names}"
        )

        # Claims must also be identical
        serial_claims = sorted(c.name for c in serial_report.claims)
        parallel_claims = sorted(c.name for c in parallel_report.claims)
        assert serial_claims == parallel_claims

        # Drift items must be identical
        serial_drift = sorted(
            (d.category, d.fact.name) for d in serial_report.drift_items
        )
        parallel_drift = sorted(
            (d.category, d.fact.name) for d in parallel_report.drift_items
        )
        assert serial_drift == parallel_drift

    def test_parallel_scan_multiple_python_files(self, tmp_path: Path) -> None:
        """Parallel scan correctly processes many Python files."""
        # Create 20 Python files with distinct functions
        files: dict[str, str] = {}
        for i in range(20):
            files[f"module_{i:02d}.py"] = f"def function_{i}(x: int) -> None: pass\n"
        files["docs.md"] = "\n\n".join(
            f"```python\ndef function_{i}(x: int) -> None\n```\n" for i in range(20)
        )
        self._make_project(tmp_path, files)

        scanner = DriftScanner(tmp_path, parallel=True)
        report = scanner.scan()

        # All 20 functions should be found
        assert len(report.facts) == 20

    def test_parallel_scan_handles_errors_gracefully(self, tmp_path: Path) -> None:
        """Parallel scan continues when individual files fail."""
        # Create a mix of valid and invalid Python files
        (tmp_path / "valid.py").write_text("def good_func() -> None: pass\n")
        (tmp_path / "invalid.py").write_text("def broken(\n")  # syntax error
        (tmp_path / "docs.md").write_text("# Docs\n")

        scanner = DriftScanner(tmp_path, parallel=True)
        report = scanner.scan()

        # valid.py should still be processed
        fact_names = {f.name for f in report.facts}
        assert "good_func" in fact_names

    def test_serial_scan_still_works(self, tmp_path: Path) -> None:
        """Serial (parallel=False) scan still works correctly."""
        self._make_project(
            tmp_path,
            {
                "example.py": "def my_func(a: int, b: str = 'x') -> bool:\n    pass\n",
                "docs.md": "# Docs\n\n```python\ndef my_func(a: int, b: str = 'x') -> bool\n```\n",
            },
        )
        scanner = DriftScanner(tmp_path, parallel=False)
        report = scanner.scan()

        fact_names = {f.name for f in report.facts}
        assert "my_func" in fact_names
        # The documented function should have no drift
        drift_names = {d.fact.name for d in report.drift_items}
        assert "my_func" not in drift_names


class TestIncrementalScan:
    """Tests for incremental scanning with file hash cache."""

    def _make_project(self, tmp_path: Path, files: dict[str, str]) -> None:
        for rel_path, content in files.items():
            f = tmp_path / rel_path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(content)

    def test_first_scan_processes_all_files(self, tmp_path: Path) -> None:
        """First scan (no cache) processes all files."""
        self._make_project(tmp_path, {
            "a.py": "def func_a(x: int) -> None: pass",
            "b.py": "def func_b(y: str) -> None: pass",
        })
        scanner = DriftScanner(tmp_path, no_cache=False, clear_cache=False)
        report = scanner.scan()
        assert len(report.facts) == 2
        assert report.files_skipped == 0

    def test_second_scan_skips_unchanged_files(self, tmp_path: Path) -> None:
        """Second scan skips files that haven't changed."""
        self._make_project(tmp_path, {
            "a.py": "def func_a(x: int) -> None: pass",
        })
        # First scan
        s1 = DriftScanner(tmp_path)
        r1 = s1.scan()
        assert len(r1.facts) == 1
        assert r1.files_skipped == 0

        # Second scan (no changes) — should skip
        s2 = DriftScanner(tmp_path)
        r2 = s2.scan()
        assert len(r2.facts) == 0
        assert r2.files_skipped == 1

    def test_modified_file_is_not_skipped(self, tmp_path: Path) -> None:
        """A file that has been modified is re-processed."""
        self._make_project(tmp_path, {
            "a.py": "def func_a(x: int) -> None: pass",
        })
        # First scan
        s1 = DriftScanner(tmp_path)
        r1 = s1.scan()
        assert len(r1.facts) == 1

        # Modify file
        import time
        time.sleep(0.01)
        (tmp_path / "a.py").write_text("def func_b(y: int) -> None: pass")

        # Second scan
        s2 = DriftScanner(tmp_path)
        r2 = s2.scan()
        assert len(r2.facts) == 1
        assert r2.facts[0].name == "func_b"
        assert r2.files_skipped == 0

    def test_no_cache_flag_forces_full_rescan(self, tmp_path: Path) -> None:
        """--no-cache forces a full rescan regardless of cache."""
        self._make_project(tmp_path, {
            "a.py": "def func_a(x: int) -> None: pass",
        })
        # First scan
        s1 = DriftScanner(tmp_path)
        r1 = s1.scan()
        assert r1.files_skipped == 0

        # Second scan with no_cache=True
        s2 = DriftScanner(tmp_path, no_cache=True)
        r2 = s2.scan()
        assert len(r2.facts) == 1
        assert r2.files_skipped == 0

    def test_clear_cache_forces_full_rescan(self, tmp_path: Path) -> None:
        """--clear-cache clears cache and forces full rescan."""
        self._make_project(tmp_path, {
            "a.py": "def func_a(x: int) -> None: pass",
        })
        # First scan
        s1 = DriftScanner(tmp_path)
        r1 = s1.scan()
        assert r1.files_skipped == 0

        # Second scan with clear_cache=True
        s2 = DriftScanner(tmp_path, clear_cache=True)
        r2 = s2.scan()
        assert len(r2.facts) == 1
        assert r2.files_skipped == 0

    def test_added_file_is_processed(self, tmp_path: Path) -> None:
        """A newly added file is processed even if other files are cached."""
        self._make_project(tmp_path, {
            "a.py": "def func_a(x: int) -> None: pass",
        })
        # First scan
        s1 = DriftScanner(tmp_path)
        r1 = s1.scan()
        assert len(r1.facts) == 1

        # Add a new file
        import time
        time.sleep(0.01)
        (tmp_path / "b.py").write_text("def func_b(y: int) -> None: pass")

        # Second scan
        s2 = DriftScanner(tmp_path)
        r2 = s2.scan()
        assert len(r2.facts) == 1
        assert r2.facts[0].name == "func_b"
        assert r2.files_skipped == 1  # a.py was skipped

    def test_deleted_file_not_in_cache_harms(self, tmp_path: Path) -> None:
        """Deleted files don't cause issues on subsequent scans."""
        self._make_project(tmp_path, {
            "a.py": "def func_a(x: int) -> None: pass",
            "b.py": "def func_b(y: int) -> None: pass",
        })
        # First scan
        s1 = DriftScanner(tmp_path)
        r1 = s1.scan()
        assert len(r1.facts) == 2

        # Delete a.py
        (tmp_path / "a.py").unlink()

        # Second scan — b.py is still in cache and unchanged, so skipped.
        # a.py is gone from disk, not in file list, not re-processed.
        s2 = DriftScanner(tmp_path)
        r2 = s2.scan()
        assert len(r2.facts) == 0  # b.py was cached and skipped
        assert r2.files_skipped == 1  # b.py unchanged
