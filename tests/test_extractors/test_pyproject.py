"""Tests for PyprojectExtractor — DRIFT-253."""

from pathlib import Path

from drift.extractors.pyproject import PyprojectExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_pyproject.toml"


class TestPyprojectCanHandle:
    """Test can_handle() method."""

    def test_handles_pyproject_toml(self):
        ext = PyprojectExtractor()
        assert ext.can_handle(Path("pyproject.toml")) is True

    def test_rejects_other_file(self):
        ext = PyprojectExtractor()
        assert ext.can_handle(Path("foo.toml")) is False

    def test_rejects_py_file(self):
        ext = PyprojectExtractor()
        assert ext.can_handle(Path("foo.py")) is False

    def test_rejects_config_toml(self):
        ext = PyprojectExtractor()
        assert ext.can_handle(Path("config.toml")) is False


class TestPyprojectExtraction:
    """Test extraction of pyproject.toml keys."""

    def test_extracts_project_name(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "project.name" in names

    def test_extracts_project_version(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "project.version" in names

    def test_extracts_project_description(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "project.description" in names

    def test_extracts_project_requires_python(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "project.requires-python" in names

    def test_extracts_project_license(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "project.license" in names

    def test_extracts_project_authors(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert any("project.authors." in n for n in names)

    def test_extracts_script_entry_point(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "project.scripts.mycli" in names

    def test_extracts_build_system_requires(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert any("build-system.requires." in n for n in names)

    def test_extracts_build_system_backend(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "build-system.build-backend" in names

    def test_kind_is_config_key(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        assert all(f.kind.value == "config_key" for f in facts)

    def test_extracts_tool_sections(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert any("tool.pytest" in n for n in names)

    def test_extracts_optional_dependencies(self):
        ext = PyprojectExtractor()
        facts = ext.extract(FIXTURE)
        names = {f.name for f in facts}
        assert any("project.optional-dependencies." in n for n in names)