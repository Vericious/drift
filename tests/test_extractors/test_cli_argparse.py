"""Tests for cli_argparse module."""
import ast
from pathlib import Path

import pytest

from drift.extractors.cli_argparse import ArgparseExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_argparse.py"


class TestArgparseExtractor:
    """Test ArgparseExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = ArgparseExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_all_five_arguments(self):
        """Extracts all 5 arguments from the fixture."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        assert len(facts) == 5

    def test_positional_arg_captured(self):
        """Positional argument (input_file) is captured."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "input_file" in names or "<input_file>" in names

    def test_short_flag_extracted(self):
        """Short flags like -o, -v are captured."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        short_flags = {f.metadata.get("short_flag") for f in facts}
        assert "-o" in short_flags or "-v" in short_flags

    def test_verbose_is_flag(self):
        """--verbose is correctly identified as a flag."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        verbose_fact = next((f for f in facts if "verbose" in f.name), None)
        assert verbose_fact is not None
        assert verbose_fact.metadata.get("is_flag") is True

    def test_format_choices(self):
        """--format choices (json, csv, text) are captured."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        format_fact = next((f for f in facts if "format" in f.name), None)
        assert format_fact is not None
        assert format_fact.metadata.get("choices") == ["json", "csv", "text"]

    def test_count_required(self):
        """--count is required=True."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        count_fact = next((f for f in facts if "count" in f.name), None)
        assert count_fact is not None
        assert count_fact.metadata.get("required") is True

    def test_output_default(self):
        """--output has default='out.txt'."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        output_fact = next((f for f in facts if "output" in f.name), None)
        assert output_fact is not None
        assert output_fact.parameters[0].default == "'out.txt'"

    def test_output_type(self):
        """--output has type=str."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        output_fact = next((f for f in facts if "output" in f.name), None)
        assert output_fact is not None
        assert output_fact.parameters[0].type_annotation == "str"

    def test_help_text(self):
        """Help text is captured."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        output_fact = next((f for f in facts if "output" in f.name), None)
        assert output_fact is not None
        assert "Output file" in (output_fact.metadata.get("help_text") or "")

    def test_no_argparse_returns_empty(self):
        """File with no argparse returns empty list."""
        noarg = Path(__file__).parent.parent / "test_models.py"
        extractor = ArgparseExtractor()
        facts = extractor.extract(noarg)
        cli_facts = [f for f in facts if f.kind.value == "cli_flag"]
        assert cli_facts == []

    def test_kind_is_cli_flag(self):
        """All extracted facts have kind=cli_flag."""
        extractor = ArgparseExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "cli_flag" for f in facts)

    def test_subparsers_arguments_captured(self):
        """Arguments from subparsers are captured."""
        import tempfile
        subparser_code = '''import argparse
parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest='command')
subparser = subparsers.add_parser('scan')
subparser.add_argument('--path', help='Path to scan')
subparser.add_argument('--verbose', '-v', action='store_true')
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(subparser_code)
            path = Path(f.name)
        try:
            extractor = ArgparseExtractor()
            facts = extractor.extract(path)
            names = {f.name for f in facts}
            assert '--path' in names
            assert '--verbose' in names
            # Should have 2 facts (--path and --verbose), not just 1
            assert len(facts) == 2
        finally:
            path.unlink()
