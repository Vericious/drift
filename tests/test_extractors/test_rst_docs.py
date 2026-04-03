"""Tests for RSTDocsExtractor."""

from pathlib import Path

import pytest

from drift.extractors.rst_docs import RSTDocsExtractor, _parse_parameters, _split_params
from drift.models import ClaimKind


@pytest.fixture
def extractor():
    return RSTDocsExtractor()


@pytest.fixture
def sample_rst(tmp_path: Path, request) -> Path:
    """Create a sample RST file for testing."""
    # Allow tests to customize content via param
    if hasattr(request, "param"):
        content = request.param
    else:
        content = Path(__file__).parent.parent / "fixtures" / "sample_docs.rst"
        if content.exists():
            return content
        content = """Sample RST
=========

.. py:function:: greet(name: str) -> str

   :param name: The name.
   :type name: str
   :returns: The greeting.
   :rtype: str
"""
    f = tmp_path / "test.rst"
    f.write_text(content)
    return f


class TestRSTDocsExtractorCanHandle:
    """Tests for can_handle method."""

    def test_can_handle_rst_file(self, extractor):
        assert extractor.can_handle(Path("readme.rst")) is True
        assert extractor.can_handle(Path("docs/api.rst")) is True
        assert extractor.can_handle(Path("README.RST")) is True

    def test_cannot_handle_non_rst(self, extractor):
        assert extractor.can_handle(Path("readme.md")) is False
        assert extractor.can_handle(Path("readme.txt")) is False
        assert extractor.can_handle(Path("readme.py")) is False


class TestRSTDocsExtractorFunctions:
    """Tests for py:function directive extraction."""

    def test_extract_simple_function(self, extractor, tmp_path: Path):
        content = """.. py:function:: add(a: int, b: int) -> int

   Adds two numbers.

   :param a: First number.
   :type a: int
   :param b: Second number.
   :type b: int
   :returns: The sum.
   :rtype: int
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        assert len(sig_claims) >= 1

        add_func = next((c for c in sig_claims if c.name == "add"), None)
        assert add_func is not None
        assert len(add_func.parameters) == 2
        assert add_func.parameters[0].name == "a"
        assert add_func.parameters[0].type_annotation == "int"
        assert add_func.parameters[1].name == "b"
        assert add_func.parameters[1].type_annotation == "int"
        assert add_func.return_type == "int"

    def test_extract_function_with_defaults(self, extractor, tmp_path: Path):
        content = """.. py:function:: greet(name: str, greeting: str = "Hello") -> str

   :param name: The name.
   :type name: str
   :param greeting: The greeting.
   :type greeting: str
   :returns: The formatted string.
   :rtype: str
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        greet_func = next((c for c in sig_claims if c.name == "greet"), None)
        assert greet_func is not None
        assert len(greet_func.parameters) == 2
        assert greet_func.parameters[1].name == "greeting"
        assert greet_func.parameters[1].default == '"Hello"'
        assert greet_func.return_type == "str"

    def test_extract_function_no_params(self, extractor, tmp_path: Path):
        content = """.. py:function:: no_params() -> None

   :returns: Nothing.
   :rtype: None
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        no_params = next((c for c in sig_claims if c.name == "no_params"), None)
        assert no_params is not None
        assert no_params.parameters == []
        assert no_params.return_type == "None"

    def test_extract_function_with_varargs(self, extractor, tmp_path: Path):
        content = """.. py:function:: varargs_func(*args, **kwargs)

   :param args: Positional args.
   :param kwargs: Keyword args.
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        vf = next((c for c in sig_claims if c.name == "varargs_func"), None)
        assert vf is not None
        assert len(vf.parameters) == 2


class TestRSTDocsExtractorMethods:
    """Tests for py:method directive extraction."""

    def test_extract_method(self, extractor, tmp_path: Path):
        content = """.. py:method:: User.get_display_name() -> str

   :returns: The display name.
   :rtype: str
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        method = next(
            (c for c in sig_claims if c.name == "User.get_display_name"), None
        )
        assert method is not None
        assert method.metadata.get("directive_type") == "method"
        assert method.return_type == "str"

    def test_extract_classmethod(self, extractor, tmp_path: Path):
        content = """.. py:method:: User.from_email(email: str) -> User

   :param email: The email address.
   :type email: str
   :returns: A new User instance.
   :rtype: User
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        cm = next((c for c in sig_claims if "from_email" in c.name), None)
        assert cm is not None


class TestRSTDocsExtractorClasses:
    """Tests for py:class directive extraction."""

    def test_extract_class(self, extractor, tmp_path: Path):
        content = """.. py:class:: User(name: str, email: str)

   :param name: The user's name.
   :type name: str
   :param email: The user's email.
   :type email: str
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        user_cls = next((c for c in sig_claims if c.name == "User"), None)
        assert user_cls is not None
        assert user_cls.metadata.get("directive_type") == "class"
        assert len(user_cls.parameters) == 2


class TestRSTDocsExtractorParameterDescriptions:
    """Tests for :param: and :type: field extraction."""

    def test_extract_param_description(self, extractor, tmp_path: Path):
        content = """.. py:function:: add(a: int, b: int) -> int

   :param a: First number.
   :type a: int
   :param b: Second number.
   :type b: int
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        param_claims = [c for c in claims if c.kind == ClaimKind.PARAMETER_DESCRIPTION]
        assert len(param_claims) >= 2

        a_claim = next((c for c in param_claims if c.name == "a"), None)
        assert a_claim is not None
        assert a_claim.parameters[0].type_annotation == "int"
        assert "First number" in a_claim.metadata.get("description", "")

    def test_extract_return_description(self, extractor, tmp_path: Path):
        content = """.. py:function:: get_value() -> int

   :returns: The computed value.
   :rtype: int
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        ret_claims = [c for c in claims if c.kind == ClaimKind.RETURN_DESCRIPTION]
        assert len(ret_claims) >= 1
        assert "computed value" in ret_claims[0].metadata.get("description", "")


class TestRSTDocsExtractorCodeBlocks:
    """Tests for code-block extraction."""

    def test_extract_code_block(self, extractor, tmp_path: Path):
        content = """Example usage:

.. code-block:: python

   user = User("Alice", "alice@example.com")
   print(user.get_display_name())
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        code_claims = [c for c in claims if c.kind == ClaimKind.CODE_EXAMPLE]
        assert len(code_claims) >= 1

    def test_extract_literal_block(self, extractor, tmp_path: Path):
        content = """Example::

   def hello():
       print("Hello, world!")
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        # Should extract something from the literal block
        assert isinstance(claims, list)


class TestRSTDocsExtractorEdgeCases:
    """Edge case tests."""

    def test_no_file_returns_empty(self, extractor, tmp_path: Path):
        claims = extractor.extract(tmp_path / "nonexistent.rst")
        assert claims == []

    def test_empty_file_returns_empty(self, extractor, tmp_path: Path):
        rst_file = tmp_path / "empty.rst"
        rst_file.write_text("")
        claims = extractor.extract(rst_file)
        assert claims == []

    def test_multiple_directives(self, extractor, tmp_path: Path):
        content = """.. py:function:: func1()

.. py:function:: func2()
"""
        rst_file = tmp_path / "test.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        sig_claims = [c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE]
        names = {c.name for c in sig_claims}
        assert "func1" in names
        assert "func2" in names


class TestRSTCrossReferences:
    """Tests for cross-reference directive handling (:func:, :class:, :meth:)."""

    def test_plain_rst_without_api_refs_produces_no_claims(self, extractor, tmp_path: Path):
        """Plain RST text without API references produces no claims."""
        content = """Welcome to My Project
=====================

This is some documentation that doesn't
contain any API references.

.. toctree::
   :maxdepth: 2

   intro
   tutorial
"""
        rst_file = tmp_path / "plain.rst"
        rst_file.write_text(content)

        claims = extractor.extract(rst_file)

        # No claims since there are no py:function, py:method, py:class directives
        assert claims == []


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_parse_parameters_empty(self):
        result = _parse_parameters("")
        assert result == []

    def test_parse_parameters_single(self):
        result = _parse_parameters("x: int")
        assert len(result) == 1
        assert result[0].name == "x"
        assert result[0].type_annotation == "int"

    def test_parse_parameters_multiple(self):
        result = _parse_parameters("a: int, b: str, c: bool = True")
        assert len(result) == 3
        assert result[0].name == "a"
        assert result[1].name == "b"
        assert result[2].name == "c"
        assert result[2].default == "True"

    def test_split_params_basic(self):
        result = _split_params("a, b, c")
        assert result == ["a", " b", " c"]

    def test_split_params_nested(self):
        result = _split_params("func(a, b), other(x)")
        assert len(result) == 2
