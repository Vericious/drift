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


class TestEdgeCases:
    """Edge case tests for PythonExtractor coverage."""

    def test_nested_function_extracted(self, tmp_path: Path, extractor: PythonExtractor) -> None:
        """Nested function definitions are extracted."""
        py_file = tmp_path / "nested.py"
        py_file.write_text(
            "def outer():\n"
            "    def inner():\n"
            "        pass\n"
            "    return inner\n"
        )

        facts = extractor.extract(py_file)
        fact_names = [f.name for f in facts]
        # inner is not extracted (private to outer) — outer is extracted
        assert "outer" in fact_names
        assert "inner" not in fact_names

    def test_async_def_extracted(self, tmp_path: Path, extractor: PythonExtractor) -> None:
        """async def functions are extracted."""
        py_file = tmp_path / "async_func.py"
        py_file.write_text(
            "async def fetch_data(url: str) -> bytes:\n"
            "    pass\n"
        )

        facts = extractor.extract(py_file)
        fact_names = [f.name for f in facts]
        assert "fetch_data" in fact_names

    def test_property_decorator_extracted(self, tmp_path: Path, extractor: PythonExtractor) -> None:
        """Functions with @property decorator are extracted."""
        py_file = tmp_path / "prop.py"
        py_file.write_text(
            "class MyClass:\n"
            "    @property\n"
            "    def value(self) -> int:\n"
            "        return 42\n"
        )

        facts = extractor.extract(py_file)
        fact_names = [f.name for f in facts]
        assert "MyClass.value" in fact_names

    def test_classmethod_extracted(self, tmp_path: Path, extractor: PythonExtractor) -> None:
        """Functions with @classmethod decorator are extracted."""
        py_file = tmp_path / "cmethod.py"
        py_file.write_text(
            "class MyClass:\n"
            "    @classmethod\n"
            "    def from_dict(cls, data: dict) -> 'MyClass':\n"
            "        pass\n"
        )

        facts = extractor.extract(py_file)
        fact_names = [f.name for f in facts]
        assert "MyClass.from_dict" in fact_names

    def test_staticmethod_extracted(self, tmp_path: Path, extractor: PythonExtractor) -> None:
        """Functions with @staticmethod decorator are extracted."""
        py_file = tmp_path / "smethod.py"
        py_file.write_text(
            "class MyClass:\n"
            "    @staticmethod\n"
            "    def helper(x: int) -> int:\n"
            "        return x * 2\n"
        )

        facts = extractor.extract(py_file)
        fact_names = [f.name for f in facts]
        assert "MyClass.helper" in fact_names
