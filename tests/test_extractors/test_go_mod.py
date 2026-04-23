"""Tests for GoModExtractor — DRIFT-250."""

from pathlib import Path

from drift.extractors.go_mod import GoModExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_go.mod"


class TestGoModCanHandle:
    """Test can_handle() method."""

    def test_handles_go_mod(self):
        ext = GoModExtractor()
        assert ext.can_handle(Path("go.mod")) is True

    def test_rejects_go_source_file(self):
        ext = GoModExtractor()
        assert ext.can_handle(Path("foo.go")) is False

    def test_rejects_pyproject_toml(self):
        ext = GoModExtractor()
        assert ext.can_handle(Path("pyproject.toml")) is False

    def test_rejects_other_toml(self):
        ext = GoModExtractor()
        assert ext.can_handle(Path("rustfmt.toml")) is False


class TestGoModExtraction:
    """Test extraction of go.mod keys."""

    def test_extracts_module_name(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "go.mod.module" in names

    def test_extracts_go_version(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "go.mod.go_version" in names

    def test_extracts_require_dependencies(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert any("go.mod.require." in n for n in names)

    def test_extracts_replace_directive(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert any("go.mod.replace." in n for n in names)

    def test_extracts_exclude_directive(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert any("go.mod.exclude." in n for n in names)

    def test_kind_is_config_key(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        assert all(f.kind.value == "config_key" for f in facts)

    def test_module_value_contains_github(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        mod = next((f for f in facts if f.name == "go.mod.module"), None)
        assert mod is not None
        assert "github.com" in mod.metadata.get("value", "")

    def test_go_version_value_is_1_21(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        go_ver = next((f for f in facts if f.name == "go.mod.go_version"), None)
        assert go_ver is not None
        assert "1.21" in go_ver.metadata.get("value", "")

    def test_require_module_has_section(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        require_facts = [f for f in facts if f.name.startswith("go.mod.require.")]
        assert len(require_facts) > 0
        for fact in require_facts:
            assert fact.metadata.get("section") == "go.mod.require"

    def test_indirect_dep_has_indirect_flag(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        # golang.org/x/text is indirect
        text_fact = next(
            (f for f in facts if "golang.org/x/text" in f.name),
            None,
        )
        assert text_fact is not None
        assert text_fact.metadata.get("indirect") is True

    def test_direct_dep_has_no_indirect_flag(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        pkg_fact = next(
            (f for f in facts if "github.com/pkg/errors" in f.name),
            None,
        )
        assert pkg_fact is not None
        assert pkg_fact.metadata.get("indirect") is False

    def test_replace_fact_has_original_and_replacement(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        replace_facts = [f for f in facts if f.name.startswith("go.mod.replace.")]
        assert len(replace_facts) > 0
        for fact in replace_facts:
            assert "original" in fact.metadata
            assert fact.metadata.get("original") == "github.com/pkg/errors"

    def test_exclude_fact_has_module_and_version(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        exclude_facts = [f for f in facts if f.name.startswith("go.mod.exclude.")]
        assert len(exclude_facts) > 0
        for fact in exclude_facts:
            assert "module" in fact.metadata

    def test_empty_go_mod_returns_empty(self):
        import tempfile

        with tempfile.NamedTemporaryFile(
            suffix="go.mod", mode="w", delete=False
        ) as f:
            f.write("")
            tmp = Path(f.name)
        try:
            ext = GoModExtractor()
            facts = ext.extract(tmp)
            assert facts == []
        finally:
            tmp.unlink()

    def test_line_numbers_are_1_indexed(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        # First fact should be at line 1 (module github.com/...)
        module_fact = next((f for f in facts if f.name == "go.mod.module"), None)
        assert module_fact is not None
        assert module_fact.line_number == 1

    def test_facts_have_value_type_metadata(self):
        ext = GoModExtractor()
        facts = ext.extract(FIXTURE)
        for fact in facts:
            assert "value_type" in fact.metadata