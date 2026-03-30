"""Tests for PythonExtractor."""

from pathlib import Path

import pytest

from drift.models import FactKind
from drift.python_extractor import PythonExtractor


@pytest.fixture
def sample_python_file(tmp_path: Path) -> Path:
    """Create a sample Python file for testing."""
    content = '''
"""Sample module for testing the Python extractor."""

def public_function(x: int, y: str = "hello") -> bool:
    """A public function with params and return type."""
    pass


def another_public():
    """A public function without params or return type."""
    pass


class MyClass:
    """A sample class with methods."""

    def public_method(self, data: list[str], verbose: bool = False) -> None:
        """A public method with params and return type."""
        pass

    def _private_method(self, secret: int) -> str:
        """A private method on the class."""
        return str(secret)


def _private_function():
    """A private function that should be skipped."""
    pass
'''
    py_file = tmp_path / "sample_module.py"
    py_file.write_text(content)
    return py_file


@pytest.fixture
def extractor() -> PythonExtractor:
    """Create a PythonExtractor instance."""
    return PythonExtractor()


class TestFunctionExtraction:
    """Test extraction of functions."""

    def test_extract_function_with_params_and_return_type(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test extracting a function with params and return type."""
        facts = extractor.extract(sample_python_file)
        funcs = [f for f in facts if f.kind == FactKind.FUNCTION]

        assert len(funcs) >= 1
        public_func = next(f for f in funcs if f.name == "public_function")
        assert public_func is not None
        assert public_func.kind == FactKind.FUNCTION
        assert public_func.name == "public_function"
        assert len(public_func.parameters) == 2
        assert public_func.return_type == "bool"

    def test_extract_function_without_params(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test extracting a function without params."""
        facts = extractor.extract(sample_python_file)
        funcs = [f for f in facts if f.kind == FactKind.FUNCTION]

        another_func = next(f for f in funcs if f.name == "another_public")
        assert another_func is not None
        assert another_func.kind == FactKind.FUNCTION
        assert len(another_func.parameters) == 0
        assert another_func.return_type is None

    def test_function_parameter_names(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test that parameter names are extracted correctly."""
        facts = extractor.extract(sample_python_file)
        funcs = [f for f in facts if f.kind == FactKind.FUNCTION]

        public_func = next(f for f in funcs if f.name == "public_function")
        param_names = [p.name for p in public_func.parameters]
        assert "x" in param_names
        assert "y" in param_names

    def test_function_parameter_types(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test that parameter types are extracted correctly."""
        facts = extractor.extract(sample_python_file)
        funcs = [f for f in facts if f.kind == FactKind.FUNCTION]

        public_func = next(f for f in funcs if f.name == "public_function")
        x_param = next(p for p in public_func.parameters if p.name == "x")
        assert x_param.type_annotation == "int"

    def test_function_parameter_defaults(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test that parameter defaults are extracted correctly."""
        facts = extractor.extract(sample_python_file)
        funcs = [f for f in facts if f.kind == FactKind.FUNCTION]

        public_func = next(f for f in funcs if f.name == "public_function")
        y_param = next(p for p in public_func.parameters if p.name == "y")
        assert y_param.default in ('"hello"', "'hello'")


class TestClassExtraction:
    """Test extraction of classes."""

    def test_extract_class(self, extractor: PythonExtractor, sample_python_file: Path):
        """Test extracting a class."""
        facts = extractor.extract(sample_python_file)
        classes = [f for f in facts if f.kind == FactKind.CLASS]

        assert len(classes) == 1
        cls = classes[0]
        assert cls.kind == FactKind.CLASS
        assert cls.name == "MyClass"


class TestMethodExtraction:
    """Test extraction of methods."""

    def test_extract_public_method(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test extracting a public method."""
        facts = extractor.extract(sample_python_file)
        methods = [f for f in facts if f.kind == FactKind.METHOD]

        assert len(methods) >= 1
        public_method = next(f for f in methods if f.name == "MyClass.public_method")
        assert public_method is not None
        assert public_method.kind == FactKind.METHOD
        assert public_method.name == "MyClass.public_method"
        # Parameters include 'self' which is part of the method signature
        assert len(public_method.parameters) == 3
        param_names = [p.name for p in public_method.parameters]
        assert "self" in param_names
        assert "data" in param_names
        assert "verbose" in param_names

    def test_method_with_params_and_return_type(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test method with params and return type."""
        facts = extractor.extract(sample_python_file)
        methods = [f for f in facts if f.kind == FactKind.METHOD]

        public_method = next(f for f in methods if f.name == "MyClass.public_method")
        param_names = [p.name for p in public_method.parameters]
        assert "self" in param_names
        assert "data" in param_names
        assert "verbose" in param_names
        assert public_method.return_type == "None"


class TestPrivateHandling:
    """Test handling of private functions and methods."""

    def test_skip_private_function_at_module_level(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test that private functions at module level are skipped."""
        facts = extractor.extract(sample_python_file)
        names = [f.name for f in facts]

        # Private function at module level should be skipped
        assert "_private_function" not in names

    def test_include_private_method_on_public_class(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test that private methods on public classes are included."""
        facts = extractor.extract(sample_python_file)
        names = [f.name for f in facts]

        # Private method on a public class should be included
        assert "MyClass._private_method" in names


class TestReturnTypeAnnotation:
    """Test return type annotation extraction."""

    def test_return_type_annotation_bool(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test return type annotation of bool."""
        facts = extractor.extract(sample_python_file)
        funcs = [f for f in facts if f.kind == FactKind.FUNCTION]

        public_func = next(f for f in funcs if f.name == "public_function")
        assert public_func.return_type == "bool"

    def test_return_type_annotation_none(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test return type annotation of None."""
        facts = extractor.extract(sample_python_file)
        methods = [f for f in facts if f.kind == FactKind.METHOD]

        public_method = next(f for f in methods if f.name == "MyClass.public_method")
        assert public_method.return_type == "None"

    def test_no_return_type_annotation(
        self, extractor: PythonExtractor, sample_python_file: Path
    ):
        """Test function without return type annotation."""
        facts = extractor.extract(sample_python_file)
        funcs = [f for f in facts if f.kind == FactKind.FUNCTION]

        another_func = next(f for f in funcs if f.name == "another_public")
        assert another_func.return_type is None


class TestFileWithSrcPrefix:
    """Test extraction when file is under a src/ directory structure."""

    def test_derive_module_from_src_path(
        self, tmp_path: Path, extractor: PythonExtractor
    ):
        """Test module derivation from src/foo/bar.py -> foo.bar."""
        src_dir = tmp_path / "src"
        foo_dir = src_dir / "foo"
        foo_dir.mkdir(parents=True)

        content = """
def my_function(x: int) -> str:
    pass
"""
        py_file = foo_dir / "bar.py"
        py_file.write_text(content)

        facts = extractor.extract(py_file)
        assert len(facts) == 1
        assert facts[0].module == "foo"


class TestPythonExtractorRegistry:
    """Tests for PythonExtractor registration in the registry."""

    def test_python_extractor_in_registry(self):
        """PythonExtractor is registered in the extractor registry."""
        from drift.extractors.registry import get_extractors

        extractors = get_extractors()
        extractor_names = [cls.__name__ for cls in extractors]
        assert "PythonExtractor" in extractor_names

    def test_python_files_dispatched_via_registry(self, tmp_path: Path):
        """Python files are processed through the registry dispatch."""
        from drift.extractors.registry import get_extractors

        # Create a Python file with a function
        content = """
def registry_test_func(x: int) -> str:
    '''A test function.'''
    return str(x)
"""
        py_file = tmp_path / "registry_test.py"
        py_file.write_text(content)

        # Verify PythonExtractor can handle .py files
        extractors = get_extractors()
        python_extractor = next(
            cls for cls in extractors if cls.__name__ == "PythonExtractor"
        )
        assert python_extractor().can_handle(py_file)
        assert python_extractor().can_handle(tmp_path / "test.py")

        # Verify non-Python files are not handled
        assert not python_extractor().can_handle(tmp_path / "test.md")
        assert not python_extractor().can_handle(tmp_path / "test.ts")

    def test_python_extraction_results_unchanged(self, tmp_path: Path):
        """PythonExtractor via registry produces same results as direct extraction."""
        from drift.extractors.registry import get_extractors

        # Create a Python file with various constructs
        content = """
class TestClass:
    '''A test class.'''

    def method_one(self, x: int) -> str:
        '''First method.'''
        return str(x)


def standalone_func(a: str, b: int = 10) -> bool:
    '''A standalone function.'''
    return True
"""
        py_file = tmp_path / "equivalence_test.py"
        py_file.write_text(content)

        # Get results via registry
        extractors = get_extractors()
        python_extractor_cls = next(
            cls for cls in extractors if cls.__name__ == "PythonExtractor"
        )
        registry_facts = python_extractor_cls().extract(py_file)

        # Get results directly
        direct_extractor = PythonExtractor()
        direct_facts = direct_extractor.extract(py_file)

        # Should produce identical results
        assert len(registry_facts) == len(direct_facts)
        registry_names = sorted(f.name for f in registry_facts)
        direct_names = sorted(f.name for f in direct_facts)
        assert registry_names == direct_names
