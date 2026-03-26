"""Tests for cli_typer module."""

from pathlib import Path

from drift.extractors.cli_typer import TyperExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_typer.py"


class TestTyperExtractor:
    """Test TyperExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = TyperExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_at_least_six_facts(self):
        """Extracts 6+ facts from the fixture."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        assert len(facts) >= 6

    def test_output_flag_found(self):
        """--output flag is captured."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "--output" in names

    def test_verbose_flag_found(self):
        """--verbose flag is captured."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "--verbose" in names

    def test_format_flag_found(self):
        """--format flag is captured."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "--format" in names

    def test_workers_flag_found(self):
        """--workers flag is captured."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "--workers" in names

    def test_strict_flag_found(self):
        """--strict flag is captured."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "--strict" in names

    def test_positional_argument_found(self):
        """Positional argument (path) is captured."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "--path" in names

    def test_types_in_metadata(self):
        """Types are extracted from options."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        output_fact = next((f for f in facts if f.name == "--output"), None)
        assert output_fact is not None
        assert output_fact.parameters[0].type_annotation == "str"

    def test_defaults_in_metadata(self):
        """Default values are captured."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        output_fact = next((f for f in facts if f.name == "--output"), None)
        assert output_fact is not None
        assert output_fact.parameters[0].default is not None

    def test_help_text_captured(self):
        """Help text is captured in metadata."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        output_fact = next((f for f in facts if f.name == "--output"), None)
        assert output_fact is not None
        assert output_fact.metadata.get("help_text") is not None
        assert "Output" in output_fact.metadata.get("help_text", "")

    def test_no_typer_returns_empty(self):
        """File with no Typer usage returns empty list."""
        no_typer = Path(__file__).parent.parent / "test_models.py"
        extractor = TyperExtractor()
        facts = extractor.extract(no_typer)
        cli_facts = [f for f in facts if f.kind.value == "cli_flag"]
        assert cli_facts == []

    def test_kind_is_cli_flag(self):
        """All extracted facts have kind=cli_flag."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "cli_flag" for f in facts)

    def test_flags_marked_as_flags(self):
        """Flags are correctly marked as is_flag=True."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        verbose_fact = next((f for f in facts if f.name == "--verbose"), None)
        assert verbose_fact is not None
        assert verbose_fact.metadata.get("is_flag") is True

    def test_positional_marked_correctly(self):
        """Positional argument is marked as is_flag=False."""
        extractor = TyperExtractor()
        facts = extractor.extract(FIXTURE)
        path_fact = next((f for f in facts if f.name == "--path"), None)
        assert path_fact is not None
        assert path_fact.metadata.get("is_flag") is False
