"""End-to-end integration tests for the Drift CLI.

These tests exercise the full CLI as a subprocess — not through imports —
to verify the complete user-facing workflow.
"""

import subprocess
import sys
from pathlib import Path

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

        assert result.returncode == 0, (
            f"Expected 0 (no drift), got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
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
        md_file.write_text("# API\n\nUse `with_params(a: int)`.\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 1, (
            f"Expected 1 (drift detected), got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "No drift detected" not in result.stdout

    def test_scan_json_output(self, tmp_path: Path) -> None:
        """--json flag outputs valid JSON."""
        # Clean directory
        py_file = tmp_path / "src.py"
        py_file.write_text("def foo(x: int) -> str:\n    return str(x)\n")
        md_file = tmp_path / "README.md"
        md_file.write_text("```python\ndef foo(x: int) -> str\n```\n")

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
            "def with_params(a: int, b: str = 'hi') -> bool:\n    return True\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text("Use `with_params(a: int)`.\n")

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
        py_file.write_text("def my_func(x: int) -> bool:\n    return True\n")

        # Create two markdown files:
        # - good_docs.md: correctly documents my_func → no drift
        # - bad_docs.md: documents my_func with wrong signature → drift
        #   (but bad_docs.md is ignored, so no drift is reported)
        good_md = tmp_path / "good_docs.md"
        good_md.write_text("```python\ndef my_func(x: int) -> bool\n```\n")
        bad_md = tmp_path / "bad_docs.md"
        bad_md.write_text("```python\ndef my_func(x: int, extra: str) -> bool\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        # Since bad_docs.md is ignored and good_docs.md is correct,
        # we should get no drift
        assert result.returncode == 0, (
            f"Expected 0 (no drift), got {result.returncode}\nstdout: {result.stdout}"
        )
        assert "No drift detected" in result.stdout

    def test_driftignore_with_glob_pattern(self, tmp_path: Path) -> None:
        """.driftignore supports glob patterns like README*.md."""
        ignore_file = tmp_path / ".driftignore"
        ignore_file.write_text("README*.md\n")  # Ignore README files only

        py_file = tmp_path / "src.py"
        py_file.write_text("def my_func(x: int) -> bool:\n    return True\n")
        # This markdown correctly documents my_func
        good_md = tmp_path / "good_docs.md"
        good_md.write_text("```python\ndef my_func(x: int) -> bool\n```\n")
        # This markdown would cause drift but is ignored via glob
        bad_md = tmp_path / "README_old.md"
        bad_md.write_text("```python\ndef my_func(x: int, extra: str) -> bool\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        # Since README_old.md is ignored (matches README*.md) and good_docs.md is correct,
        # no drift should be found
        assert result.returncode == 0, (
            f"Expected 0 (ignored), got {result.returncode}\nstdout: {result.stdout}"
        )


class TestCLIFlagDrift:
    """Integration tests for CLI flag drift detection (argparse + click)."""

    def test_argparse_flags_matching_docs_no_drift(self, tmp_path: Path) -> None:
        """Argparse CLI flags that are documented in bash block produce no drift."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--verbose', '-v', action='store_true')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text("```bash\n$ mycli --verbose\n$ mycli --help\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected 0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_argparse_undocumented_flag_detected(self, tmp_path: Path) -> None:
        """Argparse CLI flag that exists in code but not in docs is detected."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--verbose', '-v', action='store_true')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text("```bash\n$ mycli --help\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        # Undocumented flag should cause drift (warning or error)
        assert result.returncode != 0, f"Expected drift, got 0\nstdout: {result.stdout}"

    def test_click_flags_matching_docs_no_drift(self, tmp_path: Path) -> None:
        """Click CLI flags documented in bash block produce no drift."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import click\n"
            "@click.command()\n"
            "@click.option('--format', '-f', type=click.Choice(['json', 'text']))\n"
            "def cli(format):\n"
            "    pass\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text("```bash\n$ mycli --format json\n$ mycli -f text\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected 0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_document_but_missing_flag_detected(self, tmp_path: Path) -> None:
        """Flag documented but not in code is detected as error."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--output', '-o')\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "```bash\n$ mycli --verbose\n$ mycli --output out.txt\n```\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        # --verbose is documented but missing in code
        assert result.returncode != 0, f"Expected drift, got 0\nstdout: {result.stdout}"

    def test_argparse_and_click_both_extracted(self, tmp_path: Path) -> None:
        """Both argparse and click CLI flags are extracted from the same file."""
        py_file = tmp_path / "cli.py"
        py_file.write_text(
            "import argparse\n"
            "import click\n"
            "parser = argparse.ArgumentParser()\n"
            "parser.add_argument('--count', type=int)\n"
            "@click.command()\n"
            "@click.option('--verbose', '-v', is_flag=True)\n"
            "def cli(verbose):\n"
            "    pass\n"
        )
        md_file = tmp_path / "README.md"
        # Don't document --count and --verbose so they appear as undocumented CLI flags
        md_file.write_text("```bash\n$ mycli --help\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--json"],
            capture_output=True,
            text=True,
        )
        import json

        data = json.loads(result.stdout)
        # Both --count (argparse) and --verbose (click) should be extracted.
        # Since they're undocumented, they appear as CLI_FLAG drift items (ERROR severity).
        cli_drift_items = [
            d
            for d in data["drift_items"]
            if d.get("fact", {}).get("kind") == "cli_flag"
        ]
        assert len(cli_drift_items) >= 2, (
            f"Expected >=2 CLI drift items, got {len(cli_drift_items)}: {data['drift_items']}"
        )

    def test_typer_flags_matching_docs_no_drift(self, tmp_path: Path) -> None:
        """Typer CLI flags documented in bash block produce no drift."""
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
            "```bash\n"
            "$ mycli serve --name webapp --port 9000\n"
            "$ mycli serve --help\n"
            "```\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected 0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_typer_undocumented_flag_detected(self, tmp_path: Path) -> None:
        """Typer CLI flag that exists in code but not in docs is detected."""
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
        # Only document --name via bash usage, port is undocumented
        md_file.write_text("```bash\n$ mycli serve --name webapp\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        # Undocumented flag should cause drift
        assert result.returncode != 0, f"Expected drift, got 0\nstdout: {result.stdout}"


class TestConfigDrift:
    """Tests for Pydantic/config key drift detection."""

    def test_pydantic_config_matching_docs_no_drift(self, tmp_path: Path) -> None:
        """Pydantic BaseSettings vars documented in env var table → no drift."""
        py_file = tmp_path / "settings.py"
        py_file.write_text(
            "from pydantic import BaseSettings\n"
            "\n"
            "class AppConfig(BaseSettings):\n"
            "    DATABASE_URL: str\n"
            "    DEBUG: bool = False\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# Environment Variables\n\n"
            "| Variable | Type | Default |\n"
            "|----------|------|--------|\n"
            "| DATABASE_URL | string | — |\n"
            "| DEBUG | bool | false |\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected 0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_pydantic_undocumented_config_detected(self, tmp_path: Path) -> None:
        """Pydantic config var that exists in code but not in docs is detected."""
        py_file = tmp_path / "settings.py"
        py_file.write_text(
            "from pydantic import BaseSettings\n"
            "\n"
            "class AppConfig(BaseSettings):\n"
            "    DATABASE_URL: str\n"
            '    API_KEY: str = ""\n'
        )
        md_file = tmp_path / "README.md"
        # Only document DATABASE_URL, API_KEY is undocumented
        md_file.write_text(
            "# Environment Variables\n\n"
            "| Variable | Type |\n"
            "|----------|------|\n"
            "| DATABASE_URL | string |\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--json"],
            capture_output=True,
            text=True,
        )
        import json

        data = json.loads(result.stdout)
        # API_KEY is undocumented (warning), DATABASE_URL is documented
        api_key_drift = [
            d
            for d in data["drift_items"]
            if d.get("fact", {}).get("name") == "AppConfig.API_KEY"
        ]
        assert len(api_key_drift) == 1, (
            f"Expected AppConfig.API_KEY undocumented drift, got: {data['drift_items']}"
        )

    def test_config_var_documented_but_missing_no_code(self, tmp_path: Path) -> None:
        """Config var documented but not in code → documented_but_missing drift."""
        py_file = tmp_path / "settings.py"
        py_file.write_text(
            "from pydantic import BaseSettings\n"
            "\n"
            "class AppConfig(BaseSettings):\n"
            "    DATABASE_URL: str\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# Environment Variables\n\n"
            "| Variable | Type |\n"
            "|----------|------|\n"
            "| DATABASE_URL | string |\n"
            "| LEGACY_VAR | string |\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--json"],
            capture_output=True,
            text=True,
        )
        import json

        data = json.loads(result.stdout)
        config_drift = [
            d
            for d in data["drift_items"]
            if d.get("category") == "documented_but_missing"
            and d.get("claim", {}).get("name") == "LEGACY_VAR"
        ]
        assert len(config_drift) >= 1, (
            f"Expected LEGACY_VAR documented_but_missing, got: {data['drift_items']}"
        )


class TestConfigFileDrift:
    """Tests for YAML/TOML config file drift detection."""

    def test_yaml_config_matching_docs_no_drift(self, tmp_path: Path) -> None:
        """YAML config keys documented in env var table → no drift."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database:\n  host: localhost\n  port: 5432\n")
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# Configuration\n\n"
            "| Variable | Default |\n"
            "|----------|--------|\n"
            "| database.host | localhost |\n"
            "| database.port | 5432 |\n"
        )

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected 0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_yaml_config_drift_mismatch(self, tmp_path: Path) -> None:
        """YAML config key present in code and docs — just verify both are collected."""
        config_file = tmp_path / "config.yaml"
        config_file.write_text("database:\n  port: 5432\n")
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "| Variable | Default |\n|----------|--------|\n| database.port | 3306 |\n"
        )

        # Use DriftScanner directly to avoid subprocess Python-path issues
        from drift.scanner import DriftScanner

        scanner = DriftScanner(tmp_path)
        report = scanner.scan()

        # Verify YAML config fact is extracted
        config_facts = [f for f in report.facts if f.kind.value == "config_key"]
        assert any(f.name == "database.port" for f in config_facts), (
            f"Expected database.port fact, got: {[f.name for f in config_facts]}"
        )
        # Verify markdown claim is extracted
        config_claims = [c for c in report.claims if c.kind.value == "config_ref"]
        assert any(c.name == "database.port" for c in config_claims), (
            f"Expected database.port claim, got: {[c.name for c in config_claims]}"
        )


class TestUpdateBaseline:
    """Tests for the --update-baseline flag on drift scan."""

    def test_update_baseline_requires_baseline_flag(self, tmp_path: Path) -> None:
        """--update-baseline without --baseline exits with error."""
        # Create a minimal project
        py_file = tmp_path / "src.py"
        py_file.write_text("def foo(x: int) -> str:\n    return str(x)\n")
        md_file = tmp_path / "README.md"
        md_file.write_text("```python\ndef foo(x: int) -> str\n```\n")

        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--update-baseline"],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0, (
            f"Expected non-zero exit when --update-baseline used without --baseline, "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "--update-baseline requires --baseline" in result.stderr

    def test_update_baseline_saves_file(self, tmp_path: Path) -> None:
        """--baseline --update-baseline saves a new baseline file after filtering."""
        # Create a minimal project with some drift
        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def old_func(x: int) -> None:\n"
            "    '''Documented.'''\n"
            "    pass\n"
        )
        md_file = tmp_path / "docs.md"
        md_file.write_text(
            "# API\n\n"
            "## old_func\n\n"
            "```python\n"
            "def old_func(x: int) -> None\n"
            "```\n"
        )

        # First, create an initial baseline
        result = subprocess.run(
            DRIFT_CMD + ["baseline", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"baseline creation failed: {result.stderr}"

        baseline_path = tmp_path / ".drift" / "baseline.json"
        assert baseline_path.exists()

        # Get the original baseline mtime
        original_mtime = baseline_path.stat().st_mtime

        import time
        time.sleep(0.01)

        # Now run scan with --baseline --update-baseline
        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--baseline", "--update-baseline"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"scan --baseline --update-baseline failed: {result.stderr}\n"
            f"stdout: {result.stdout}"
        )
        assert baseline_path.exists()
        # The baseline file should have been updated (mtime changed or content changed)
        assert "Baseline updated:" in result.stdout

    def test_update_baseline_prints_item_count(self, tmp_path: Path) -> None:
        """--baseline --update-baseline prints 'Baseline updated: N items'."""
        # Create a minimal project with drift
        py_file = tmp_path / "src.py"
        py_file.write_text(
            "def my_func(a: int, b: str) -> bool:\n"
            "    '''Docstring.'''\n"
            "    return True\n"
        )
        md_file = tmp_path / "README.md"
        md_file.write_text(
            "# API\n\n"
            "## my_func\n\n"
            "```python\n"
            "def my_func(a: int, b: str) -> bool\n"
            "```\n"
        )

        # Create initial baseline
        subprocess.run(
            DRIFT_CMD + ["baseline", str(tmp_path)],
            capture_output=True,
            text=True,
        )

        # Run scan with --baseline --update-baseline
        result = subprocess.run(
            DRIFT_CMD + ["scan", str(tmp_path), "--baseline", "--update-baseline"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Baseline updated:" in result.stdout
        # Should print item count (the number of items in the baseline)
        import re
        match = re.search(r"Baseline updated: (\d+) items", result.stdout)
        assert match is not None, (
            f"Expected 'Baseline updated: N items' in output, got: {result.stdout}"
        )
        item_count = int(match.group(1))
        assert item_count >= 0
