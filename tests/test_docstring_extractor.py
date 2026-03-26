"""Tests for the docstring extractor."""
import tempfile
from pathlib import Path

import pytest

from drift.extractors.docstring import (
    DocstringExtractor,
    extract_docstring_params,
    _parse_docstring,
    _parse_google_style,
    _parse_numpy_style,
    _parse_sphinx_style,
)


# ---------------------------------------------------------------------------
# Tests for extract_docstring_params helper
# ---------------------------------------------------------------------------

class TestExtractDocstringParams:
    """Tests for the extract_docstring_params function."""

    def test_matching_params_google_style(self):
        """Test function with matching Google-style docstring params."""

        def func(a: int, b: str, c: bool = False) -> None:
            """Do something.

            Args:
                a: First param
                b: Second param
                c: Third param
            """
            pass

        params = extract_docstring_params(func)
        assert set(params) == {"a", "b", "c"}

    def test_missing_params_google_style(self):
        """Test function with Google-style docstring missing some params."""

        def func(a: int, b: str, c: bool = False) -> None:
            """Do something.

            Args:
                a: First param
                b: Second param
            """
            pass

        params = extract_docstring_params(func)
        assert set(params) == {"a", "b"}

    def test_extra_params_google_style(self):
        """Test function with Google-style docstring having extra params."""

        def func(a: int, b: str) -> None:
            """Do something.

            Args:
                a: First param
                b: Second param
                c: Third param (doesn't exist!)
            """
            pass

        params = extract_docstring_params(func)
        assert set(params) == {"a", "b", "c"}

    def test_no_docstring(self):
        """Test function without docstring."""

        def func(a: int, b: str) -> None:
            pass

        params = extract_docstring_params(func)
        assert params == []

    def test_numpy_style(self):
        """Test function with NumPy-style docstring."""

        def func(a: int, b: str) -> None:
            """Do something.

            Parameters
            ----------
            a : int
                First param
            b : str
                Second param
            """
            pass

        params = extract_docstring_params(func)
        assert set(params) == {"a", "b"}

    def test_sphinx_style(self):
        """Test function with Sphinx-style docstring."""

        def func(a: int, b: str) -> None:
            """Do something.

            :param a: First param
            :param b: Second param
            """
            pass

        params = extract_docstring_params(func)
        assert set(params) == {"a", "b"}

    def test_google_style_with_types(self):
        """Test Google-style docstring with type annotations."""

        def func(a: int, b: str, c: list[int] = None) -> None:
            """Do something.

            Args:
                a (int): First param
                b (str): Second param
                c (list[int], optional): Third param
            """
            pass

        params = extract_docstring_params(func)
        assert set(params) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Tests for _parse_docstring (internal parser)
# ---------------------------------------------------------------------------

class TestParseDocstring:
    """Tests for the internal _parse_docstring function."""

    def test_google_style(self):
        """Test Google-style parsing."""
        doc = """Do something.

        Args:
            a: First param
            b: Second param
        """
        params = _parse_docstring(doc)
        assert set(params) == {"a", "b"}

    def test_numpy_style(self):
        """Test NumPy-style parsing."""
        doc = """Do something.

        Parameters
        ----------
        a : int
            First param
        b : str
            Second param
        """
        params = _parse_docstring(doc)
        assert set(params) == {"a", "b"}

    def test_sphinx_style(self):
        """Test Sphinx-style parsing."""
        doc = """Do something.

        :param a: First param
        :param b: Second param
        """
        params = _parse_docstring(doc)
        assert set(params) == {"a", "b"}

    def test_empty_docstring(self):
        """Test empty docstring."""
        assert _parse_docstring("") == []
        assert _parse_docstring("   ") == []
        assert _parse_docstring(None) == []

    def test_no_args_section(self):
        """Test docstring without Args section."""
        doc = """Just a description.

        No parameters documented here.
        """
        params = _parse_docstring(doc)
        assert params == []


# ---------------------------------------------------------------------------
# Tests for DocstringExtractor
# ---------------------------------------------------------------------------

class TestDocstringExtractor:
    """Tests for the DocstringExtractor class."""

    @pytest.fixture
    def sample_python_file(self, tmp_path: Path) -> Path:
        """Create a sample Python file with docstrings for testing."""
        content = '''"""Sample module for testing the docstring extractor."""


def func_with_matching_docs(a: int, b: str, c: bool = False) -> None:
    """Do something.

    Args:
        a: First param
        b: Second param
        c: Third param
    """
    pass


def func_with_missing_docs(a: int, b: str, c: bool = False) -> None:
    """Do something.

    Args:
        a: First param
    """
    pass


def func_with_extra_docs(a: int, b: str) -> None:
    """Do something.

    Args:
        a: First param
        b: Second param
        c: Third param (doesn't exist!)
    """
    pass


def func_without_docs(a: int, b: str) -> None:
    """Just a docstring without args section."""
    pass


class MyClass:
    """A sample class."""

    def method_with_docs(self, x: int, y: str) -> None:
        """Do something.

        Args:
            x: First param
            y: Second param
        """
        pass

    def method_without_docs(self, x: int, y: str) -> None:
        pass
'''
        py_file = tmp_path / "sample_module.py"
        py_file.write_text(content)
        return py_file

    @pytest.fixture
    def extractor(self) -> DocstringExtractor:
        """Create a DocstringExtractor instance."""
        return DocstringExtractor()

    def test_can_handle_py_files(self, extractor):
        """Test that extractor handles Python files."""
        assert extractor.can_handle(Path("foo.py")) is True
        assert extractor.can_handle(Path("foo.PY")) is True
        assert extractor.can_handle(Path("foo.md")) is False

    def test_extract_matching_params(self, extractor, sample_python_file):
        """Test extraction with matching docstring params."""
        claims = extractor.extract(sample_python_file)

        # Find the func_with_matching_docs claim
        matching_claim = next((c for c in claims if c.name == "func_with_matching_docs"), None)
        assert matching_claim is not None
        assert set(p.name for p in matching_claim.parameters) == {"a", "b", "c"}

    def test_extract_missing_params(self, extractor, sample_python_file):
        """Test extraction with missing docstring params."""
        claims = extractor.extract(sample_python_file)

        # Find the func_with_missing_docs claim
        missing_claim = next((c for c in claims if c.name == "func_with_missing_docs"), None)
        assert missing_claim is not None
        assert set(p.name for p in missing_claim.parameters) == {"a"}

    def test_extract_extra_params(self, extractor, sample_python_file):
        """Test extraction with extra docstring params."""
        claims = extractor.extract(sample_python_file)

        # Find the func_with_extra_docs claim
        extra_claim = next((c for c in claims if c.name == "func_with_extra_docs"), None)
        assert extra_claim is not None
        assert set(p.name for p in extra_claim.parameters) == {"a", "b", "c"}

    def test_extract_no_docs(self, extractor, sample_python_file):
        """Test that functions without Args sections are not extracted."""
        claims = extractor.extract(sample_python_file)
        claim_names = [c.name for c in claims]

        # func_without_docs has a docstring but no Args section
        assert "func_without_docs" not in claim_names

    def test_extract_method_docs(self, extractor, sample_python_file):
        """Test extraction of method docstrings with qualified names."""
        claims = extractor.extract(sample_python_file)

        # Find the method claim with qualified name
        method_claim = next((c for c in claims if c.name == "MyClass.method_with_docs"), None)
        assert method_claim is not None
        assert set(p.name for p in method_claim.parameters) == {"x", "y"}

    def test_extract_empty_file(self, extractor, tmp_path):
        """Test extraction from empty Python file."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")

        claims = extractor.extract(empty_file)
        assert claims == []

    def test_extract_nonexistent_file(self, extractor, tmp_path):
        """Test extraction from nonexistent file."""
        claims = extractor.extract(tmp_path / "nonexistent.py")
        assert claims == []
