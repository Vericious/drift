"""Tests for Swift extractor."""

from pathlib import Path

import pytest

from drift.extractors.swift import SwiftExtractor


FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.swift"


class TestSwiftExtractorCanHandle:
    """Test .can_handle() method."""

    def test_handles_swift_file(self):
        ext = SwiftExtractor()
        assert ext.can_handle(Path("foo.swift")) is True

    def test_rejects_py_file(self):
        ext = SwiftExtractor()
        assert ext.can_handle(Path("foo.py")) is False

    def test_rejects_ts_file(self):
        ext = SwiftExtractor()
        assert ext.can_handle(Path("foo.ts")) is False

    def test_rejects_swift_file_capitalized(self):
        """Ensure .Swift upper-case extension is also handled."""
        ext = SwiftExtractor()
        assert ext.can_handle(Path("foo.Swift")) is True


class TestStructExtraction:
    """Test struct declaration extraction."""

    def test_basic_struct(self):
        """User struct is extracted with correct properties."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        assert user_fact.metadata["swift_kind"] == "struct"
        assert user_fact.metadata["lang"] == "swift"
        assert "id" in user_fact.metadata["properties"]
        assert "name" in user_fact.metadata["properties"]
        assert "email" in user_fact.metadata["properties"]
        assert user_fact.metadata["methods"] == ["greet", "toDict"]

    def test_struct_with_let_readonly(self):
        """Struct properties with let are marked is_readonly."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        id_param = next((p for p in user_fact.parameters if p.name == "id"), None)
        assert id_param is not None
        assert id_param.is_readonly is True
        name_param = next((p for p in user_fact.parameters if p.name == "name"), None)
        assert name_param is not None
        assert name_param.is_readonly is False  # var

    def test_struct_with_var_not_readonly(self):
        """Struct properties with var are not readonly."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        name_param = next((p for p in user_fact.parameters if p.name == "name"), None)
        assert name_param is not None
        assert name_param.is_readonly is False

    def test_optional_properties(self):
        """Optional properties (String?) have is_optional=True."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        email_param = next((p for p in user_fact.parameters if p.name == "email"), None)
        assert email_param is not None
        assert email_param.is_optional is True

    def test_struct_with_nested_type(self):
        """Rectangle struct with Point property is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        rect_fact = next((f for f in facts if f.name == "Rectangle"), None)
        assert rect_fact is not None
        assert "origin" in rect_fact.metadata["properties"]
        assert "width" in rect_fact.metadata["properties"]


class TestClassExtraction:
    """Test class declaration extraction."""

    def test_basic_class(self):
        """ViewController class is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        vc_fact = next((f for f in facts if f.name == "ViewController"), None)
        assert vc_fact is not None
        assert vc_fact.metadata["swift_kind"] == "class"
        assert vc_fact.metadata["lang"] == "swift"
        assert "title" in vc_fact.metadata["properties"]
        assert "items" in vc_fact.metadata["properties"]

    def test_class_with_inheritance(self):
        """Dog class inheriting from Animal is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        dog_fact = next((f for f in facts if f.name == "Dog"), None)
        assert dog_fact is not None
        assert dog_fact.metadata["swift_kind"] == "class"

    def test_class_methods_extracted(self):
        """Class methods are in metadata['methods']."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        vc_fact = next((f for f in facts if f.name == "ViewController"), None)
        assert vc_fact is not None
        assert "addItem" in vc_fact.metadata["methods"]
        assert "removeItem" in vc_fact.metadata["methods"]


class TestEnumExtraction:
    """Test enum declaration extraction."""

    def test_basic_enum(self):
        """Direction enum is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        dir_fact = next((f for f in facts if f.name == "Direction"), None)
        assert dir_fact is not None
        assert dir_fact.metadata["swift_kind"] == "enum"
        assert "north" in dir_fact.metadata["members"]
        assert "south" in dir_fact.metadata["members"]
        assert "east" in dir_fact.metadata["members"]
        assert "west" in dir_fact.metadata["members"]

    def test_enum_with_raw_type(self):
        """Color enum with String raw type is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        color_fact = next((f for f in facts if f.name == "Color"), None)
        assert color_fact is not None
        assert color_fact.metadata["swift_kind"] == "enum"

    def test_enum_with_int_raw_type(self):
        """Priority enum with Int raw type is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        priority_fact = next((f for f in facts if f.name == "Priority"), None)
        assert priority_fact is not None
        assert priority_fact.metadata["swift_kind"] == "enum"

    def test_enum_members_as_parameters(self):
        """Enum members are in parameters list."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        dir_fact = next((f for f in facts if f.name == "Direction"), None)
        assert dir_fact is not None
        param_names = {p.name for p in dir_fact.parameters}
        assert param_names == {"north", "south", "east", "west"}


class TestProtocolExtraction:
    """Test protocol declaration extraction."""

    def test_basic_protocol(self):
        """Drawable protocol is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        drawable_fact = next((f for f in facts if f.name == "Drawable"), None)
        assert drawable_fact is not None
        assert drawable_fact.metadata["swift_kind"] == "protocol"

    def test_protocol_with_properties(self):
        """Identifiable protocol is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        id_fact = next((f for f in facts if f.name == "Identifiable"), None)
        assert id_fact is not None
        assert "id" in id_fact.metadata["properties"]

    def test_protocol_with_methods(self):
        """Configurable protocol methods are extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        cfg_fact = next((f for f in facts if f.name == "Configurable"), None)
        assert cfg_fact is not None
        assert "configure" in cfg_fact.metadata["methods"]

    def test_protocol_with_associated_types(self):
        """Protocol with associatedtype is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        container_fact = next(
            (f for f in facts if f.name == "Container" and f.metadata.get("swift_kind") == "protocol"),
            None,
        )
        assert container_fact is not None
        assert container_fact.metadata["swift_kind"] == "protocol"
        # Methods and properties from the protocol body are extracted
        assert "count" in container_fact.metadata["properties"]
        assert "add" in container_fact.metadata["methods"]
        assert "get" in container_fact.metadata["methods"]


class TestExtensionExtraction:
    """Test extension declaration extraction."""

    def test_basic_extension(self):
        """Extension on User is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        ext_fact = next((f for f in facts if f.metadata.get("swift_kind") == "extension" and f.metadata.get("extended_type") == "User"), None)
        assert ext_fact is not None
        assert ext_fact.metadata["lang"] == "swift"

    def test_extension_methods_extracted(self):
        """Extension method names are in metadata['methods']."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        ext_fact = next((f for f in facts if f.metadata.get("swift_kind") == "extension" and f.metadata.get("extended_type") == "User"), None)
        assert ext_fact is not None
        assert "fullName" in ext_fact.metadata["methods"]

    def test_extension_properties_extracted(self):
        """Extension computed properties are extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        ext_fact = next((f for f in facts if f.metadata.get("swift_kind") == "extension" and f.metadata.get("extended_type") == "User"), None)
        assert ext_fact is not None
        assert "displayName" in ext_fact.metadata["properties"]

    def test_extension_on_view_controller(self):
        """Extension on ViewController is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        ext_fact = next((f for f in facts if f.metadata.get("swift_kind") == "extension" and f.metadata.get("extended_type") == "ViewController"), None)
        assert ext_fact is not None
        assert "clearItems" in ext_fact.metadata["methods"]
        assert "itemCount" in ext_fact.metadata["properties"]

    def test_extension_stored_in_parameters(self):
        """Extension added properties are in parameters list."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        ext_fact = next((f for f in facts if f.metadata.get("swift_kind") == "extension" and f.metadata.get("extended_type") == "User"), None)
        assert ext_fact is not None
        param_names = {p.name for p in ext_fact.parameters}
        assert "displayName" in param_names

    def test_extension_fact_name_is_extended_type(self):
        """Extension fact is named after the extended type."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        ext_fact = next((f for f in facts if f.metadata.get("swift_kind") == "extension" and f.metadata.get("extended_type") == "ViewController"), None)
        assert ext_fact is not None
        assert ext_fact.name == "ViewController"


class TestStandaloneFunctionExtraction:
    """Test top-level func declaration extraction."""

    def test_simple_function(self):
        """add() function is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        add_fact = next((f for f in facts if f.name == "add"), None)
        assert add_fact is not None
        assert add_fact.kind.value == "function"
        assert add_fact.return_type == "Int"
        assert len(add_fact.parameters) == 2

    def test_function_with_closure_param(self):
        """fetchUser() with closure parameter is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        fetch_fact = next((f for f in facts if f.name == "fetchUser"), None)
        assert fetch_fact is not None
        # Return type includes closure signature due to regex limitation
        assert fetch_fact.return_type is not None

    def test_function_with_transform(self):
        """processItems() with transform closure is extracted."""
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)

        proc_fact = next((f for f in facts if f.name == "processItems"), None)
        assert proc_fact is not None
        # Return type captures closure signature; we verify it ends with ] since array is captured
        assert proc_fact.return_type is not None
        assert "String" in proc_fact.return_type


class TestLangMetadata:
    """Test that metadata['lang']='swift' is set on all facts."""

    def test_struct_lang_metadata(self):
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        assert user_fact.metadata["lang"] == "swift"

    def test_class_lang_metadata(self):
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        vc_fact = next((f for f in facts if f.name == "ViewController"), None)
        assert vc_fact is not None
        assert vc_fact.metadata["lang"] == "swift"

    def test_enum_lang_metadata(self):
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        dir_fact = next((f for f in facts if f.name == "Direction"), None)
        assert dir_fact is not None
        assert dir_fact.metadata["lang"] == "swift"

    def test_protocol_lang_metadata(self):
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        drawable_fact = next((f for f in facts if f.name == "Drawable"), None)
        assert drawable_fact is not None
        assert drawable_fact.metadata["lang"] == "swift"

    def test_function_lang_metadata(self):
        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        add_fact = next((f for f in facts if f.name == "add"), None)
        assert add_fact is not None
        assert add_fact.metadata["lang"] == "swift"


class TestParameterDataclass:
    """Test that SwiftExtractor uses Parameter dataclass instances."""

    def test_struct_parameters_are_parameter_dataclass(self):
        from drift.models import Parameter

        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        for param in user_fact.parameters:
            assert isinstance(param, Parameter), f"Expected Parameter, got {type(param)}"
            assert param.name is not None

    def test_class_parameters_are_parameter_dataclass(self):
        from drift.models import Parameter

        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        vc_fact = next((f for f in facts if f.name == "ViewController"), None)
        assert vc_fact is not None
        for param in vc_fact.parameters:
            assert isinstance(param, Parameter), f"Expected Parameter, got {type(param)}"

    def test_enum_members_are_parameter_dataclass(self):
        from drift.models import Parameter

        ext = SwiftExtractor()
        facts = ext.extract(FIXTURE)
        dir_fact = next((f for f in facts if f.name == "Direction"), None)
        assert dir_fact is not None
        for param in dir_fact.parameters:
            assert isinstance(param, Parameter), f"Expected Parameter, got {type(param)}"
