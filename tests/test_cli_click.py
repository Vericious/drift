"""Tests for cli_click module."""
from pathlib import Path

import pytest

from drift.extractors.cli_click import ClickExtractor


FIXTURE = Path(__file__).parent / "fixtures" / "sample_click.py"


class TestClickExtractor:
    """Test ClickExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = ClickExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_all_options_and_arguments(self):
        """Extracts path arg, --format, --verbose, --config from the fixture."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        assert len(facts) == 4

    def test_argument_captured(self):
        """Positional argument (path) is captured."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "path" in names

    def test_short_flag(self):
        """Short flags like -f, -v are captured."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        short_flags = {f.metadata.get("short_flag") for f in facts}
        assert "-f" in short_flags or "-v" in short_flags

    def test_verbose_is_flag(self):
        """--verbose is identified as a flag."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        verbose_fact = next((f for f in facts if "verbose" in f.name), None)
        assert verbose_fact is not None
        assert verbose_fact.metadata.get("is_flag") is True

    def test_format_choices(self):
        """--format choices (json, console) are captured."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        format_fact = next((f for f in facts if "format" in f.name), None)
        assert format_fact is not None
        assert set(format_fact.metadata.get("choices", [])) == {"json", "console"}

    def test_format_default(self):
        """--format default is 'console'."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        format_fact = next((f for f in facts if "format" in f.name), None)
        assert format_fact is not None
        assert format_fact.parameters[0].default == "'console'"

    def test_help_text(self):
        """Help text is captured."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        verbose_fact = next((f for f in facts if "verbose" in f.name), None)
        assert verbose_fact is not None
        assert "Verbose output" in (verbose_fact.metadata.get("help_text") or "")

    def test_no_click_returns_empty(self):
        """File with no click decorators returns empty list."""
        no_click = Path(__file__).parent.parent / "test_models.py"
        extractor = ClickExtractor()
        facts = extractor.extract(no_click)
        cli_facts = [f for f in facts if f.kind.value == "cli_flag"]
        assert cli_facts == []

    def test_kind_is_cli_flag(self):
        """All extracted facts have kind=cli_flag."""
        extractor = ClickExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "cli_flag" for f in facts)
