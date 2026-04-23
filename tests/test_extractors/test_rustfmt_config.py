"""Tests for rustfmt_config extractor — DRIFT-249."""

from pathlib import Path

from drift.extractors.rustfmt_config import RustfmtConfigExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_rustfmt.toml"


class TestRustfmtConfigCanHandle:
    """Test can_handle() method."""

    def test_handles_rustfmt_toml(self):
        ext = RustfmtConfigExtractor()
        assert ext.can_handle(Path("rustfmt.toml")) is True

    def test_rejects_pyproject_toml(self):
        ext = RustfmtConfigExtractor()
        assert ext.can_handle(Path("pyproject.toml")) is False

    def test_rejects_regular_toml(self):
        ext = RustfmtConfigExtractor()
        assert ext.can_handle(Path("config.toml")) is False

    def test_rejects_rust_source_file(self):
        ext = RustfmtConfigExtractor()
        assert ext.can_handle(Path("src/lib.rs")) is False


class TestRustfmtConfigExtraction:
    """Test extraction of rustfmt.toml keys."""

    def test_extracts_edition(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.edition" in names

    def test_extracts_max_width(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.max_width" in names

    def test_extracts_tab_spaces(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.tab_spaces" in names

    def test_extracts_hard_tabs(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.hard_tabs" in names

    def test_extracts_comment_width(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.comment_width" in names

    def test_extracts_newline_style(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.newline_style" in names

    def test_extracts_reorder_imports(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.reorder_imports" in names

    def test_extracts_merge_derives(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "rustfmt.merge_derives" in names

    def test_kind_is_config_key(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        assert all(f.kind.value == "config_key" for f in facts)

    def test_all_facts_have_rustfmt_section(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        for fact in facts:
            assert fact.metadata.get("section") == "rustfmt"

    def test_int_values_have_int_type(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        max_width = next((f for f in facts if f.name == "rustfmt.max_width"), None)
        assert max_width is not None
        assert max_width.metadata.get("value_type") == "int"

    def test_bool_values_have_bool_type(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        hard_tabs = next((f for f in facts if f.name == "rustfmt.hard_tabs"), None)
        assert hard_tabs is not None
        assert hard_tabs.metadata.get("value_type") == "bool"

    def test_str_values_have_str_type(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        newline = next((f for f in facts if f.name == "rustfmt.newline_style"), None)
        assert newline is not None
        assert newline.metadata.get("value_type") == "str"

    def test_edition_value_is_2021(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        edition = next((f for f in facts if f.name == "rustfmt.edition"), None)
        assert edition is not None
        assert "2021" in edition.metadata.get("value", "")

    def test_max_width_value_is_100(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        max_width = next((f for f in facts if f.name == "rustfmt.max_width"), None)
        assert max_width is not None
        assert "100" in max_width.metadata.get("value", "")

    def test_tab_spaces_value_is_4(self):
        ext = RustfmtConfigExtractor()
        facts = ext.extract(FIXTURE)
        tab_spaces = next((f for f in facts if f.name == "rustfmt.tab_spaces"), None)
        assert tab_spaces is not None
        assert "4" in tab_spaces.metadata.get("value", "")

    def test_empty_rustfmt_toml_returns_empty(self):
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix="rustfmt.toml", mode="w", delete=False
        ) as f:
            f.write("")
            tmp = Path(f.name)
        try:
            ext = RustfmtConfigExtractor()
            facts = ext.extract(tmp)
            assert facts == []
        finally:
            tmp.unlink()