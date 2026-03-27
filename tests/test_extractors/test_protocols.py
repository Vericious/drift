"""Tests for protocols module."""

from pathlib import Path

from drift.extractors.protocols import ProtocolExtractor

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_protocols.py"


class TestProtocolExtractor:
    """Test ProtocolExtractor."""

    def test_protocol_extraction(self):
        """Extracts typing.Protocol method stubs."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        # Check SupportsClose protocol
        close = next((f for f in facts if f.name == "SupportsClose.close"), None)
        assert close is not None
        assert close.kind.value == "function"

        # Check DataReader protocol
        read = next((f for f in facts if f.name == "DataReader.read"), None)
        assert read is not None

        get_size = next((f for f in facts if f.name == "DataReader.get_size"), None)
        assert get_size is not None

    def test_abc_extraction(self):
        """Extracts abc.ABC @abstractmethod methods."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        process = next((f for f in facts if f.name == "AbstractBase.process"), None)
        assert process is not None

        validate = next((f for f in facts if f.name == "AbstractBase.validate"), None)
        assert validate is not None

    def test_mixed_abstract_concrete(self):
        """Only extracts abstract methods, not concrete ones."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        # AbstractBase has helper() which is concrete (no @abstractmethod) - should NOT be extracted
        helper = next((f for f in facts if f.name == "AbstractBase.helper"), None)
        assert helper is None

        # MixedBase has step_one (abstract) and step_two (concrete)
        step_one = next((f for f in facts if f.name == "MixedBase.step_one"), None)
        assert step_one is not None

        step_two = next((f for f in facts if f.name == "MixedBase.step_two"), None)
        assert step_two is None

    def test_runtime_checkable(self):
        """Extracts @runtime_checkable Protocol with correct metadata."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        close = next((f for f in facts if f.name == "SupportsClose.close"), None)
        assert close is not None
        assert close.metadata.get("is_runtime_checkable") is True

        # DataReader is not @runtime_checkable
        read = next((f for f in facts if f.name == "DataReader.read"), None)
        assert read is not None
        assert read.metadata.get("is_runtime_checkable") is False

    def test_protocol_stub_detection(self):
        """Protocol methods with ... body are detected as stubs."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        # Animal has name (property with ...) and speak (method with ...)
        animal_name = next((f for f in facts if f.name == "Animal.name"), None)
        assert animal_name is not None

        animal_speak = next((f for f in facts if f.name == "Animal.speak"), None)
        assert animal_speak is not None

    def test_method_parameters_extracted(self):
        """Method parameters are correctly extracted."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        read = next((f for f in facts if f.name == "DataReader.read"), None)
        assert read is not None
        param_names = [p.name for p in read.parameters]
        assert "n" in param_names
        assert read.return_type == "bytes"

    def test_abstract_method_parameters(self):
        """ABC abstract method parameters are extracted."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        process = next((f for f in facts if f.name == "AbstractBase.process"), None)
        assert process is not None
        param_names = [p.name for p in process.parameters]
        assert "data" in param_names
        assert process.return_type is None  # no return annotation in fixture

    def test_method_category_metadata(self):
        """Facts have correct method_category metadata."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        # Protocol stub
        close = next((f for f in facts if f.name == "SupportsClose.close"), None)
        assert close is not None
        assert close.metadata["method_category"] == "protocol_method"

        # ABC abstract method
        validate = next((f for f in facts if f.name == "AbstractBase.validate"), None)
        assert validate is not None
        assert validate.metadata["method_category"] == "abstract_method"

    def test_can_handle_py_files(self):
        """can_handle returns True for .py files."""
        extractor = ProtocolExtractor()
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.pyi")) is False
        assert extractor.can_handle(Path("foo.txt")) is False

    def test_concrete_implementation_not_extracted(self):
        """Concrete implementations of ABC are not double-extracted."""
        extractor = ProtocolExtractor()
        facts = extractor.extract(FIXTURE)

        # ConcreteImplementation is NOT a Protocol or ABC itself
        # It just inherits from AbstractBase but is not ABC
        impl_process = next((f for f in facts if f.name == "ConcreteImplementation.process"), None)
        assert impl_process is None
