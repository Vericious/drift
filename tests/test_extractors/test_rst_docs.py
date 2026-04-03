"""Tests for RSTDocsExtractor."""

import tempfile
from pathlib import Path

import pytest

from drift.extractors.rst_docs import RSTDocsExtractor
from drift.models import ClaimKind


@pytest.fixture
def extractor():
    return RSTDocsExtractor()


class TestRstExtractorCrossRefs:
    """Test cross-reference extraction (:func:, :class:, :meth:, :mod:)."""

    def test_func_cross_ref_produces_function_ref(self, extractor):
        """``:func:`module.func`` produces ClaimKind.FUNCTION_REF."""
        content = """
Test Module
===========

See :func:`my_module.my_func` for details.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            func_refs = [c for c in claims if c.kind == ClaimKind.FUNCTION_REF]
            assert len(func_refs) == 1
            assert func_refs[0].name == "my_func"
            assert func_refs[0].metadata.get("role") == "func"
            assert func_refs[0].metadata.get("target") == "my_module.my_func"
            assert func_refs[0].raw_text == ":func:`my_module.my_func`"
        finally:
            path.unlink()

    def test_class_cross_ref_produces_function_ref(self, extractor):
        """``:class:`MyClass`` produces ClaimKind.FUNCTION_REF."""
        content = """
Test Module
===========

See :class:`package.MyClass` for details.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            class_refs = [c for c in claims if c.kind == ClaimKind.FUNCTION_REF]
            assert len(class_refs) == 1
            assert class_refs[0].name == "MyClass"
            assert class_refs[0].metadata.get("role") == "class"
        finally:
            path.unlink()

    def test_meth_cross_ref_produces_function_ref(self, extractor):
        """``:meth:`ClassName.method_name`` produces ClaimKind.FUNCTION_REF."""
        content = """
Test Module
===========

See :meth:`MyClass.do_something` for details.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            meth_refs = [c for c in claims if c.kind == ClaimKind.FUNCTION_REF]
            assert len(meth_refs) == 1
            assert meth_refs[0].name == "do_something"
            assert meth_refs[0].metadata.get("role") == "meth"
        finally:
            path.unlink()

    def test_mod_cross_ref_produces_function_ref(self, extractor):
        """``:mod:`my_module`` produces ClaimKind.FUNCTION_REF."""
        content = """
Test Module
===========

See :mod:`my_package` for an overview.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            mod_refs = [c for c in claims if c.kind == ClaimKind.FUNCTION_REF]
            assert len(mod_refs) == 1
            assert mod_refs[0].name == "my_package"
            assert mod_refs[0].metadata.get("role") == "mod"
        finally:
            path.unlink()

    def test_multiple_cross_refs_in_line(self, extractor):
        """Multiple cross-refs on one line are all captured."""
        content = """
Test Module
===========

Use :func:`foo.bar` and :func:`baz.qux` together.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            func_refs = [c for c in claims if c.kind == ClaimKind.FUNCTION_REF]
            assert len(func_refs) == 2
            names = {c.name for c in func_refs}
            assert names == {"bar", "qux"}
        finally:
            path.unlink()


class TestRstExtractorAutomodule:
    """Test .. automodule:: directive extraction."""

    def test_automodule_produces_claim(self, extractor):
        """``.. automodule::`` produces a FUNCTION_REF claim."""
        content = """
API Reference
=============

.. automodule:: my_package
   :members:
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            mod_claims = [
                c
                for c in claims
                if c.kind == ClaimKind.FUNCTION_REF
                and c.metadata.get("source") == "automodule"
            ]
            assert len(mod_claims) >= 1
            mod_claim = next(
                (c for c in mod_claims if c.name == "my_package"), None
            )
            assert mod_claim is not None
            assert mod_claim.metadata.get("role") == "mod"
        finally:
            path.unlink()

    def test_automodule_with_symbols(self, extractor):
        """``.. automodule::`` with listed symbols emits per-symbol claims."""
        content = """
API Reference
============

.. automodule:: my_package

   helper_func
   inner_class
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            sym_claims = [
                c
                for c in claims
                if c.kind == ClaimKind.FUNCTION_REF
                and c.metadata.get("source") == "automodule"
                and c.metadata.get("role") == "func"
            ]
            names = {c.name for c in sym_claims}
            assert "helper_func" in names
            assert "inner_class" in names
        finally:
            path.unlink()


class TestRstExtractorPlainRst:
    """Test plain RST files without API references."""

    def test_plain_rst_without_api_refs_produces_no_function_ref_claims(
        self, extractor
    ):
        """Plain RST with no :func:/automodule produces no FUNCTION_REF claims."""
        content = """
Welcome
=======

This is just a plain document with no API references.

- Item one
- Item two

.. note::
   This is a note block.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            func_refs = [c for c in claims if c.kind == ClaimKind.FUNCTION_REF]
            assert len(func_refs) == 0
        finally:
            path.unlink()

    def test_can_handle_returns_true_for_rst(self, extractor):
        """can_handle returns True for .rst files."""
        assert extractor.can_handle(Path("foo.rst"))
        assert extractor.can_handle(Path("bar.RST"))

    def test_can_handle_returns_false_for_non_rst(self, extractor):
        """can_handle returns False for non-.rst files."""
        assert not extractor.can_handle(Path("foo.md"))
        assert not extractor.can_handle(Path("foo.py"))
        assert not extractor.can_handle(Path("foo.txt"))


class TestRstExtractorPyDirectives:
    """Test existing py:function/method/class directive extraction still works."""

    def test_py_function_directive(self, extractor):
        """``.. py:function::`` is still extracted."""
        content = """
Functions
=========

.. py:function:: my_func(arg1, arg2)

   A function.
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rst", delete=False
        ) as f:
            f.write(content)
            path = Path(f.name)

        try:
            claims = extractor.extract(path)
            sig_claims = [
                c for c in claims if c.kind == ClaimKind.FUNCTION_SIGNATURE
            ]
            assert len(sig_claims) >= 1
            func_claim = next(
                (c for c in sig_claims if c.name == "my_func"), None
            )
            assert func_claim is not None
        finally:
            path.unlink()
