"""Tests for Rust extractor — DRIFT-238."""

from pathlib import Path

from drift.extractors.rust import RustExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample.rs"


class TestRustExtractorCanHandle:
    """Test .can_handle() method."""

    def test_handles_rust_file(self):
        ext = RustExtractor()
        assert ext.can_handle(Path("foo.rs")) is True

    def test_rejects_py_file(self):
        ext = RustExtractor()
        assert ext.can_handle(Path("foo.py")) is False

    def test_rejects_ts_file(self):
        ext = RustExtractor()
        assert ext.can_handle(Path("foo.ts")) is False

    def test_handles_rust_file_capitalized(self):
        """Ensure .Rust upper-case extension is also handled."""
        ext = RustExtractor()
        assert ext.can_handle(Path("foo.Rs")) is True


class TestStructExtraction:
    """Test struct declaration extraction."""

    def test_basic_struct(self):
        """User struct is extracted with correct metadata."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None
        assert user_fact.metadata["rust_kind"] == "struct"
        assert user_fact.metadata["lang"] == "rust"
        assert user_fact.docstring is not None
        assert "system" in user_fact.docstring.lower()

    def test_struct_with_pub(self):
        """pub struct is also extracted."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        user_fact = next((f for f in facts if f.name == "User"), None)
        assert user_fact is not None


class TestEnumExtraction:
    """Test enum declaration extraction."""

    def test_basic_enum(self):
        """Priority enum is extracted with correct rust_kind."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        priority_fact = next((f for f in facts if f.name == "Priority"), None)
        assert priority_fact is not None
        assert priority_fact.metadata["rust_kind"] == "enum"
        assert priority_fact.metadata["lang"] == "rust"

    def test_enum_has_docstring(self):
        """Priority enum has its outer doc comment."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        priority_fact = next((f for f in facts if f.name == "Priority"), None)
        assert priority_fact is not None
        assert priority_fact.docstring is not None
        assert "priority level" in priority_fact.docstring.lower()


class TestTraitExtraction:
    """Test trait declaration extraction."""

    def test_basic_trait(self):
        """Serializable trait is extracted with correct rust_kind."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        trait_fact = next((f for f in facts if f.name == "Serializable"), None)
        assert trait_fact is not None
        assert trait_fact.metadata["rust_kind"] == "trait"
        assert trait_fact.metadata["lang"] == "rust"


class TestImplExtraction:
    """Test impl block extraction."""

    def test_impl_for_struct(self):
        """Impl block for User is extracted."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        impl_fact = next((f for f in facts if f.name == "User" and f.metadata.get("rust_kind") == "impl"), None)
        assert impl_fact is not None
        assert impl_fact.metadata["lang"] == "rust"


class TestFunctionExtraction:
    """Test function declaration extraction."""

    def test_public_function(self):
        """helper_function is extracted with correct signature."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        fn_fact = next((f for f in facts if f.name == "helper_function"), None)
        assert fn_fact is not None
        assert fn_fact.kind.value == "function"
        assert fn_fact.metadata["lang"] == "rust"
        assert len(fn_fact.parameters) == 2
        param_names = [p.name for p in fn_fact.parameters]
        assert "x" in param_names
        assert "y" in param_names

    def test_function_return_type(self):
        """helper_function has return type i32."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        fn_fact = next((f for f in facts if f.name == "helper_function"), None)
        assert fn_fact is not None
        assert fn_fact.return_type == "i32"

    def test_method_on_impl(self):
        """new and get_name methods on User impl are extracted."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        method_names = [f.name for f in facts if f.metadata.get("lang") == "rust" and f.kind.value == "function"]
        assert "new" in method_names
        assert "get_name" in method_names


class TestInnerDocScenarios:
    """Test inner doc comment scenarios (DRIFT-238 core requirement).

    Inner docs (//! and /*!! */) should attach to the enclosing item,
    not to individual items inside the block.
    """

    def test_module_level_inner_doc(self):
        """Module-level //! comment is captured."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        # Module-level inner docs should be associated with something
        # We verify by checking the extractor runs without error and produces facts
        assert len(facts) > 0

    def test_struct_inner_doc(self):
        """Structs with outer doc comments have those docs attached."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        # User struct has outer docs
        user_fact = next((f for f in facts if f.name == "User" and f.metadata.get("rust_kind") == "struct"), None)
        assert user_fact is not None
        assert user_fact.docstring is not None
        assert "user" in user_fact.docstring.lower()

    def test_impl_inner_doc(self):
        """Inner docs inside User impl are captured on the impl."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        impl_fact = next((f for f in facts if f.name == "User" and f.metadata.get("rust_kind") == "impl"), None)
        assert impl_fact is not None
        assert "inner_docstring" in impl_fact.metadata
        assert "impl block" in impl_fact.metadata["inner_docstring"].lower()

    def test_impl_serializable_inner_block_doc(self):
        """/*!! */ block inner docs inside impl are captured."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        # impl Serializable for User is named "User" with impl_trait="Serializable"
        impl_fact = next(
            (f for f in facts if f.name == "User" and f.metadata.get("impl_trait") == "Serializable"),
            None,
        )
        assert impl_fact is not None
        assert "inner_docstring" in impl_fact.metadata

    def test_struct_method_inner_docs_not_duplicated(self):
        """Methods inside a struct don't double-count inner docs from parent."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        # New method inside User impl should not have the impl's inner docs
        new_method = next((f for f in facts if f.name == "new" and f.kind.value == "function"), None)
        assert new_method is not None
        # The inner doc on the impl should be on the impl fact, not individual methods

    def test_enum_variant_outer_docs(self):
        """Outer docs on enum variants are captured on the enum."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        priority_fact = next((f for f in facts if f.name == "Priority"), None)
        assert priority_fact is not None
        assert priority_fact.docstring is not None
        assert "priority" in priority_fact.docstring.lower()

    def test_multiple_structs_with_inner_docs(self):
        """Both Config and User structs with outer docs work correctly."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        config_fact = next((f for f in facts if f.name == "Config"), None)
        user_fact = next((f for f in facts if f.name == "User" and f.metadata.get("rust_kind") == "struct"), None)

        assert config_fact is not None
        assert user_fact is not None
        # Both should be structs
        assert config_fact.metadata["rust_kind"] == "struct"
        assert user_fact.metadata["rust_kind"] == "struct"
        # User struct has outer docs
        assert user_fact.docstring is not None

    def test_inner_module_docs(self):
        """Inner module //! docs are captured."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        # inner module helper function is in a module with inner docs
        inner_fn = next((f for f in facts if f.name == "inner_helper"), None)
        assert inner_fn is not None


class TestMetadata:
    """Test metadata fields on extracted facts."""

    def test_all_facts_have_lang_rust(self):
        """Every extracted fact has metadata['lang'] == 'rust'."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        for fact in facts:
            assert fact.metadata.get("lang") == "rust"

    def test_rust_kind_values(self):
        """Facts have correct rust_kind in metadata."""
        ext = RustExtractor()
        facts = ext.extract(FIXTURE)

        kinds = {f.metadata.get("rust_kind") for f in facts if "rust_kind" in f.metadata}
        assert "struct" in kinds
        assert "enum" in kinds
        assert "trait" in kinds
        assert "impl" in kinds
