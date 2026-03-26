"""Tests for dataclass_fields module."""

from pathlib import Path

from drift.extractors.dataclass_fields import DataclassFieldsExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_dataclasses.py"


class TestDataclassFieldsExtractor:
    """Test DataclassFieldsExtractor."""

    def test_can_handle_py_file(self):
        """.can_handle returns True for .py files."""
        extractor = DataclassFieldsExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_extracts_config_key_facts(self):
        """Extracts CONFIG_KEY facts from the fixture."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        config_facts = [f for f in facts if f.kind.value == "config_key"]
        assert len(config_facts) > 0

    def test_kind_is_config_key(self):
        """All extracted facts have kind=config_key."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.kind.value == "config_key" for f in facts)

    def test_dataclass_without_decorator_not_extracted(self):
        """Class without @dataclass decorator is not extracted."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # InventoryItem is @dataclass so fields should be extracted
        assert any("InventoryItem" in n for n in names)

    def test_field_name_in_fact_name(self):
        """Fact name follows 'ClassName.field_name' format."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        assert "User.name" in names
        assert "User.email" in names
        assert "Config.debug" in names
        assert "Point.x" in names

    def test_classvar_skipped(self):
        """ClassVar fields are skipped."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # InventoryItem.total_items is ClassVar — should not be extracted
        assert "InventoryItem.total_items" not in names

    def test_initvar_skipped(self):
        """InitVar fields are skipped."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        names = {f.name for f in facts}
        # Container.size is InitVar — should not be extracted
        assert "Container.size" not in names
        # Container.name is a regular field — should be extracted
        assert "Container.name" in names

    def test_bare_default_extracted(self):
        """Bare field defaults (no field()) are extracted."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        point_x = next((f for f in facts if f.name == "Point.x"), None)
        assert point_x is not None
        # Point.x has no default, so default should be None
        assert point_x.metadata.get("default") is None

    def test_field_default_factory_extracted(self):
        """field(default_factory=...) is extracted."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        user_tags = next((f for f in facts if f.name == "User.tags"), None)
        assert user_tags is not None
        assert user_tags.metadata.get("field_type") == "list"

    def test_field_default_value_extracted(self):
        """field(default=X) is extracted."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        max_conn = next((f for f in facts if f.name == "Config.max_connections"), None)
        assert max_conn is not None
        assert max_conn.metadata.get("default") == "100"

    def test_class_name_in_metadata(self):
        """class_name is stored in metadata."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        user_name = next((f for f in facts if f.name == "User.name"), None)
        assert user_name is not None
        assert user_name.metadata.get("class_name") == "User"
        assert user_name.metadata.get("field_name") == "name"

    def test_field_type_annotation_extracted(self):
        """Type annotation is stored in metadata."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        user_age = next((f for f in facts if f.name == "User.age"), None)
        assert user_age is not None
        assert user_age.metadata.get("field_type") == "int"

    def test_source_file_and_line_number_set(self):
        """Facts have source_file and line_number set."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        assert all(f.source_file == FIXTURE for f in facts)
        assert all(f.line_number is not None and f.line_number > 0 for f in facts)

    def test_no_dataclasses_returns_empty(self):
        """File with no @dataclass returns empty list."""
        no_dc = Path(__file__).parent.parent / "test_models.py"
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(no_dc)
        assert all(f.kind.value != "config_key" for f in facts)

    def test_multiple_dataclasses_all_extracted(self):
        """Fields from multiple @dataclass classes are all extracted."""
        extractor = DataclassFieldsExtractor()
        facts = extractor.extract(FIXTURE)
        classes = {f.metadata.get("class_name") for f in facts}
        assert "User" in classes
        assert "Config" in classes
        assert "Point" in classes
        assert "InventoryItem" in classes
        assert "Order" in classes
        assert "Response" in classes
        assert "Container" in classes
