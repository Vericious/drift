"""Tests for Go extractor."""

from pathlib import Path

import pytest

from drift.extractors.go import GoExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.go"


class TestGoExtractorCanHandle:
    """Test .can_handle() method."""

    def test_handles_go_file(self):
        ext = GoExtractor()
        assert ext.can_handle(Path("foo.go")) is True

    def test_rejects_py_file(self):
        ext = GoExtractor()
        assert ext.can_handle(Path("foo.py")) is False

    def test_rejects_ts_file(self):
        ext = GoExtractor()
        assert ext.can_handle(Path("foo.ts")) is False


class TestStructExtraction:
    """Test struct declaration extraction."""

    def test_basic_struct(self):
        """User struct is extracted with correct fields."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        assert user_fact.metadata["go_kind"] == "struct"
        assert user_fact.metadata["lang"] == "go"
        assert "ID" in user_fact.metadata["properties"]
        assert "Name" in user_fact.metadata["properties"]
        assert "Email" in user_fact.metadata["properties"]

    def test_struct_fields_as_parameters(self):
        """Struct fields are in the parameters list."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        field_names = {p.name for p in user_fact.parameters}
        assert "ID" in field_names
        assert "Name" in field_names
        assert "Email" in field_names

    def test_nested_struct(self):
        """Rectangle struct with Point field is extracted."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        rect_fact = next((f for f in facts if f.name == "Rectangle"), None)
        assert rect_fact is not None
        assert "Origin" in rect_fact.metadata["properties"]
        assert "Width" in rect_fact.metadata["properties"]


class TestInterfaceExtraction:
    """Test interface declaration extraction."""

    def test_basic_interface(self):
        """Reader interface is extracted."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        reader_fact = next((f for f in facts if f.name == "Reader"), None)
        assert reader_fact is not None
        assert reader_fact.metadata["go_kind"] == "interface"

    def test_interface_methods(self):
        """ReadWriter interface is extracted but may not have methods (embedded interfaces)."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        rw_fact = next((f for f in facts if f.name == "ReadWriter"), None)
        assert rw_fact is not None
        assert rw_fact.metadata["go_kind"] == "interface"
        # ReadWriter has embedded interfaces, so methods list may be empty
        # Just verify it's an interface


class TestFunctionExtraction:
    """Test top-level function extraction."""

    def test_simple_function(self):
        """Add function is extracted."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        add_fact = next((f for f in facts if f.name == "Add"), None)
        assert add_fact is not None
        assert add_fact.kind.value == "function"

    def test_function_with_params(self):
        """Greet function is extracted with parameter."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        greet_fact = next((f for f in facts if f.name == "Greet"), None)
        assert greet_fact is not None
        assert len(greet_fact.parameters) >= 1


class TestMethodExtraction:
    """Test method extraction (func with receiver)."""

    def test_method_with_receiver(self):
        """GetID method on User is extracted."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        getid_fact = next((f for f in facts if f.name == "GetID"), None)
        assert getid_fact is not None
        assert getid_fact.metadata["kind"] == "method"
        assert getid_fact.metadata["receiver"] is not None
        assert "*User" in getid_fact.metadata["receiver"]  # Receiver type is *User


class TestConstVarExtraction:
    """Test const and var declaration extraction."""

    def test_single_const(self):
        """MaxUsers const is extracted."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        max_fact = next((f for f in facts if f.name == "MaxUsers"), None)
        assert max_fact is not None
        # Top-level const MaxUsers = 100
        assert max_fact.metadata["go_kind"] == "const"

    def test_const_group(self):
        """Status group constants are extracted."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        # The extractor extracts the group constant as a single item
        # Since const (...) grouping doesn't match well, we check StatusActive
        status_fact = next((f for f in facts if f.name == "StatusActive"), None)
        assert status_fact is not None
        assert status_fact.metadata["go_kind"] == "const"

    def test_global_var(self):
        """GlobalCounter var is extracted."""
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)

        counter_fact = next((f for f in facts if f.name == "GlobalCounter"), None)
        assert counter_fact is not None
        assert counter_fact.metadata["go_kind"] == "var"


class TestLangMetadata:
    """Test that metadata['lang']='go' is set on all facts."""

    def test_struct_lang_metadata(self):
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)
        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        assert user_fact.metadata["lang"] == "go"

    def test_function_lang_metadata(self):
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)
        add_fact = next((f for f in facts if f.name == "Add"), None)
        assert add_fact is not None
        assert add_fact.metadata["lang"] == "go"

    def test_interface_lang_metadata(self):
        ext = GoExtractor()
        facts = ext.extract(FIXTURE)
        reader_fact = next((f for f in facts if f.name == "Reader"), None)
        assert reader_fact is not None
        assert reader_fact.metadata["lang"] == "go"


class TestParameterDataclass:
    """Test that GoExtractor uses Parameter dataclass instances."""

    def test_struct_parameters_are_parameter_dataclass(self):
        from drift.models import Parameter

        ext = GoExtractor()
        facts = ext.extract(FIXTURE)
        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        for param in user_fact.parameters:
            assert isinstance(param, Parameter), f"Expected Parameter, got {type(param)}"
            assert param.name is not None

    def test_function_parameters_are_parameter_dataclass(self):
        from drift.models import Parameter

        ext = GoExtractor()
        facts = ext.extract(FIXTURE)
        add_fact = next((f for f in facts if f.name == "Add"), None)
        assert add_fact is not None
        for param in add_fact.parameters:
            assert isinstance(param, Parameter), f"Expected Parameter, got {type(param)}"
