"""Tests for Kotlin extractor — DRIFT-235."""

from pathlib import Path

import pytest

from drift.extractors.kotlin import KotlinExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.kt"


class TestKotlinExtractorCanHandle:
    """Test .can_handle() method."""

    def test_handles_kt_file(self):
        ext = KotlinExtractor()
        assert ext.can_handle(Path("foo.kt")) is True

    def test_handles_kts_file(self):
        ext = KotlinExtractor()
        assert ext.can_handle(Path("foo.kts")) is True

    def test_rejects_py_file(self):
        ext = KotlinExtractor()
        assert ext.can_handle(Path("foo.py")) is False

    def test_rejects_go_file(self):
        ext = KotlinExtractor()
        assert ext.can_handle(Path("foo.go")) is False

    def test_handles_kt_capitalized(self):
        """Ensure .KT upper-case extension is also handled."""
        ext = KotlinExtractor()
        assert ext.can_handle(Path("foo.KT")) is True


class TestDataClassExtraction:
    """Test data class extraction."""

    def test_data_class_user(self):
        """User data class is extracted with correct kotlin_kind."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User" and f.metadata.get("kotlin_kind") == "data_class"), None)
        assert user_fact is not None
        assert user_fact.metadata["lang"] == "kotlin"
        assert user_fact.kind.value == "class"

    def test_data_class_fields_as_parameters(self):
        """Data class fields are in the parameters list."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        field_names = {p.name for p in user_fact.parameters}
        assert "id" in field_names
        assert "name" in field_names
        assert "email" in field_names


class TestClassExtraction:
    """Test regular class extraction."""

    def test_config_class(self):
        """Config class is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        config_fact = next((f for f in facts if f.name == "Config"), None)
        assert config_fact is not None
        assert config_fact.metadata["kotlin_kind"] == "class"
        assert config_fact.metadata["lang"] == "kotlin"

    def test_outer_class(self):
        """Outer class is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        outer_fact = next((f for f in facts if f.name == "Outer"), None)
        assert outer_fact is not None
        assert outer_fact.metadata["kotlin_kind"] == "class"


class TestSealedClassExtraction:
    """Test sealed class extraction."""

    def test_sealed_class_result(self):
        """Result sealed class is extracted with sealed_class kotlin_kind."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        result_fact = next((f for f in facts if f.name == "Result" and f.metadata.get("kotlin_kind") == "sealed_class"), None)
        assert result_fact is not None
        assert result_fact.kind.value == "class"
        assert result_fact.metadata["lang"] == "kotlin"


class TestAbstractClassExtraction:
    """Test abstract class extraction."""

    def test_abstract_class(self):
        """BaseService abstract class is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        base_fact = next((f for f in facts if f.name == "BaseService"), None)
        assert base_fact is not None
        assert base_fact.metadata["kotlin_kind"] == "abstract_class"
        assert base_fact.metadata["lang"] == "kotlin"


class TestInterfaceExtraction:
    """Test interface extraction."""

    def test_interface_repository(self):
        """Repository interface is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        repo_fact = next((f for f in facts if f.name == "Repository"), None)
        assert repo_fact is not None
        assert repo_fact.metadata["kotlin_kind"] == "interface"
        assert repo_fact.metadata["lang"] == "kotlin"
        assert repo_fact.kind.value == "class"


class TestObjectExtraction:
    """Test object (singleton) extraction."""

    def test_object_logger(self):
        """Logger object is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        logger_fact = next((f for f in facts if f.name == "Logger"), None)
        assert logger_fact is not None
        assert logger_fact.metadata["kotlin_kind"] == "object"
        assert logger_fact.metadata["lang"] == "kotlin"


class TestEnumClassExtraction:
    """Test enum class extraction."""

    def test_enum_class_priority(self):
        """Priority enum class is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        priority_fact = next((f for f in facts if f.name == "Priority"), None)
        assert priority_fact is not None
        assert priority_fact.metadata["kotlin_kind"] == "enum_class"
        assert priority_fact.metadata["lang"] == "kotlin"


class TestFunctionExtraction:
    """Test function extraction."""

    def test_top_level_function(self):
        """helper function is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        fn_fact = next((f for f in facts if f.name == "helper"), None)
        assert fn_fact is not None
        assert fn_fact.kind.value == "function"
        assert fn_fact.metadata["lang"] == "kotlin"
        assert fn_fact.metadata["kotlin_kind"] == "function"
        assert len(fn_fact.parameters) == 2

    def test_function_parameters(self):
        """helper function has x and y parameters."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        fn_fact = next((f for f in facts if f.name == "helper"), None)
        param_names = {p.name for p in fn_fact.parameters}
        assert "x" in param_names
        assert "y" in param_names

    def test_function_return_type(self):
        """helper function has Int return type."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        fn_fact = next((f for f in facts if f.name == "helper"), None)
        assert fn_fact.return_type == "Int"

    def test_extension_function(self):
        """displayName extension function on User is extracted."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        fn_fact = next((f for f in facts if f.name == "displayName"), None)
        assert fn_fact is not None
        assert fn_fact.kind.value == "function"
        assert fn_fact.metadata["kotlin_kind"] == "extension_function"
        assert fn_fact.metadata["receiver"] == "User"
        assert fn_fact.return_type == "String"


class TestMetadata:
    """Test metadata fields on extracted facts."""

    def test_all_facts_have_lang_kotlin(self):
        """Every extracted fact has metadata['lang'] == 'kotlin'."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        for fact in facts:
            assert fact.metadata.get("lang") == "kotlin"

    def test_kotlin_kind_values(self):
        """Facts have expected kotlin_kind values."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        kinds = {f.metadata.get("kotlin_kind") for f in facts}
        assert "data_class" in kinds
        assert "sealed_class" in kinds
        assert "abstract_class" in kinds
        assert "interface" in kinds
        assert "object" in kinds
        assert "enum_class" in kinds
        assert "class" in kinds
        assert "function" in kinds
        assert "extension_function" in kinds


class TestLineNumbers:
    """Test that line numbers are correctly computed."""

    def test_user_data_class_line(self):
        """User data class is at line 5."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        assert user_fact.line_number == 5

    def test_helper_function_line(self):
        """helper function is at line 26."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        fn_fact = next((f for f in facts if f.name == "helper"), None)
        assert fn_fact is not None
        assert fn_fact.line_number == 26

    def test_logger_object_line(self):
        """Logger object is at line 29."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        logger_fact = next((f for f in facts if f.name == "Logger"), None)
        assert logger_fact is not None
        assert logger_fact.line_number == 29

    def test_repository_interface_line(self):
        """Repository interface is at line 51."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        repo_fact = next((f for f in facts if f.name == "Repository"), None)
        assert repo_fact is not None
        assert repo_fact.line_number == 51

    def test_priority_enum_line(self):
        """Priority enum is at line 78."""
        ext = KotlinExtractor()
        facts = ext.extract(FIXTURE)

        priority_fact = next((f for f in facts if f.name == "Priority"), None)
        assert priority_fact is not None
        assert priority_fact.line_number == 78
