"""Tests for tests/generate_fixtures.py script."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestFixturesGenerator:
    """Tests for the fixture generator script."""

    def test_generated_files_exist(self, tmp_path: Path) -> None:
        """Verify generated files exist after running the script."""
        # Run the generator script with tmp_path output
        result = subprocess.run(
            [sys.executable, "tests/generate_fixtures.py", "--output", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Script failed: {result.stderr}"

        # Check source files exist
        assert (tmp_path / "generated_python.py").exists()
        assert (tmp_path / "generated_typescript.ts").exists()
        assert (tmp_path / "generated_markdown.md").exists()

    def test_expected_json_valid_json(self, tmp_path: Path) -> None:
        """Verify .expected.json files are valid JSON."""
        # Run the generator script
        subprocess.run(
            [sys.executable, "tests/generate_fixtures.py", "--output", str(tmp_path)],
            check=True,
        )

        # Verify each expected JSON is valid
        for suffix in ["generated_python.py", "generated_typescript.ts", "generated_markdown.md"]:
            expected_path = tmp_path / f"{suffix}.expected.json"
            assert expected_path.exists(), f"Missing: {expected_path}"

            # Should be valid JSON
            with open(expected_path) as f:
                data = json.load(f)
            assert isinstance(data, dict)

    def test_expected_json_has_required_fields(self, tmp_path: Path) -> None:
        """Verify .expected.json files have required 'facts' and 'claims' fields."""
        # Run the generator script
        subprocess.run(
            [sys.executable, "tests/generate_fixtures.py", "--output", str(tmp_path)],
            check=True,
        )

        for suffix in ["generated_python.py", "generated_typescript.ts", "generated_markdown.md"]:
            expected_path = tmp_path / f"{suffix}.expected.json"
            with open(expected_path) as f:
                data = json.load(f)

            assert "facts" in data, f"{suffix}: missing 'facts' field"
            assert "claims" in data, f"{suffix}: missing 'claims' field"
            assert isinstance(data["facts"], list), f"{suffix}: 'facts' must be a list"
            assert isinstance(data["claims"], list), f"{suffix}: 'claims' must be a list"

    def test_python_fixture_has_facts(self, tmp_path: Path) -> None:
        """Verify Python fixture generates expected facts."""
        subprocess.run(
            [sys.executable, "tests/generate_fixtures.py", "--output", str(tmp_path)],
            check=True,
        )

        expected_path = tmp_path / "generated_python.py.expected.json"
        with open(expected_path) as f:
            data = json.load(f)

        # Python fixture should have facts (functions, classes)
        assert len(data["facts"]) > 0, "Python fixture should have facts"

        # Verify fact structure
        for fact in data["facts"]:
            assert "name" in fact
            assert "kind" in fact
            assert "parameters" in fact

    def test_typescript_fixture_has_facts(self, tmp_path: Path) -> None:
        """Verify TypeScript fixture generates expected facts."""
        subprocess.run(
            [sys.executable, "tests/generate_fixtures.py", "--output", str(tmp_path)],
            check=True,
        )

        expected_path = tmp_path / "generated_typescript.ts.expected.json"
        with open(expected_path) as f:
            data = json.load(f)

        # TypeScript fixture should have facts (interfaces, functions)
        assert len(data["facts"]) > 0, "TypeScript fixture should have facts"

    def test_markdown_fixture_has_claims(self, tmp_path: Path) -> None:
        """Verify Markdown fixture generates expected claims."""
        subprocess.run(
            [sys.executable, "tests/generate_fixtures.py", "--output", str(tmp_path)],
            check=True,
        )

        expected_path = tmp_path / "generated_markdown.md.expected.json"
        with open(expected_path) as f:
            data = json.load(f)

        # Markdown fixture should have claims (documented functions)
        assert len(data["claims"]) > 0, "Markdown fixture should have claims"
