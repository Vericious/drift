"""Tests for typescript extractor."""

from pathlib import Path

import pytest

from drift.extractors.typescript import TypeScriptExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_typescript.ts"


class TestTypeScriptExtractorCanHandle:
    """Test .can_handle() method."""

    def test_handles_ts_file(self):
        ext = TypeScriptExtractor()
        assert ext.can_handle(Path("foo.ts")) is True

    def test_handles_tsx_file(self):
        ext = TypeScriptExtractor()
        assert ext.can_handle(Path("foo.tsx")) is True

    def test_rejects_py_file(self):
        ext = TypeScriptExtractor()
        assert ext.can_handle(Path("foo.py")) is False

    def test_rejects_js_file(self):
        ext = TypeScriptExtractor()
        assert ext.can_handle(Path("foo.js")) is False


class TestInterfaceExtraction:
    """Test interface extraction."""

    def test_basic_interface(self):
        """User interface is extracted with correct properties."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        assert user_fact.metadata["ts_kind"] == "TS_INTERFACE"
        assert "id" in user_fact.metadata["properties"]
        assert "name" in user_fact.metadata["properties"]
        assert "email" in user_fact.metadata["properties"]

    def test_interface_with_extends(self):
        """AdminUser extends User is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        admin_fact = next((f for f in facts if f.name == "AdminUser"), None)
        assert admin_fact is not None
        assert admin_fact.metadata["ts_kind"] == "TS_INTERFACE"
        assert admin_fact.metadata["extends"] == "User"
        assert "role" in admin_fact.metadata["properties"]

    def test_nested_interface(self):
        """Address interface is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        address_fact = next((f for f in facts if f.name == "Address"), None)
        assert address_fact is not None
        assert address_fact.metadata["ts_kind"] == "TS_INTERFACE"
        assert "street" in address_fact.metadata["properties"]
        assert "city" in address_fact.metadata["properties"]


class TestTypeAliasExtraction:
    """Test type alias extraction."""

    def test_object_type_alias(self):
        """UserProfile type alias is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        profile_fact = next((f for f in facts if f.name == "UserProfile"), None)
        assert profile_fact is not None
        assert profile_fact.metadata["ts_kind"] == "TS_TYPE"
        assert "username" in profile_fact.metadata["properties"]

    def test_union_type_alias(self):
        """Status union type alias is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        status_fact = next((f for f in facts if f.name == "Status"), None)
        assert status_fact is not None
        assert status_fact.metadata["ts_kind"] == "TS_TYPE"

    def test_primitive_type_alias(self):
        """UserId primitive type alias is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        userid_fact = next((f for f in facts if f.name == "UserId"), None)
        assert userid_fact is not None
        assert userid_fact.metadata["ts_kind"] == "TS_TYPE"


class TestEnumExtraction:
    """Test enum extraction."""

    def test_string_enum(self):
        """Color string enum is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        color_fact = next((f for f in facts if f.name == "Color"), None)
        assert color_fact is not None
        assert color_fact.metadata["ts_kind"] == "TS_ENUM"
        assert "Red" in color_fact.metadata["members"]
        assert "Green" in color_fact.metadata["members"]
        assert color_fact.metadata["is_const"] is False

    def test_numeric_enum(self):
        """Direction numeric enum is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        dir_fact = next((f for f in facts if f.name == "Direction"), None)
        assert dir_fact is not None
        assert dir_fact.metadata["ts_kind"] == "TS_ENUM"
        assert "Up" in dir_fact.metadata["members"]
        assert "Down" in dir_fact.metadata["members"]

    def test_const_enum(self):
        """Priority const enum is extracted."""
        ext = TypeScriptExtractor()
        facts = ext.extract(FIXTURE)

        priority_fact = next((f for f in facts if f.name == "Priority"), None)
        assert priority_fact is not None
        assert priority_fact.metadata["ts_kind"] == "TS_ENUM"
        assert priority_fact.metadata["is_const"] is True


class TestTsxFile:
    """Test .tsx file extension."""

    def test_tsx_extension(self):
        """TypeScriptExtractor handles .tsx files."""
        ext = TypeScriptExtractor()
        assert ext.can_handle(Path("component.tsx")) is True
