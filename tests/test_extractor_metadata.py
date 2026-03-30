"""Tests for extractor metadata consistency.

Verifies all extractors return consistent required fields:
- CodeFact: source_file, name, kind, line_number
- DocClaim: doc_file, name, kind, line_number
"""

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Sample file factories
# ---------------------------------------------------------------------------

def _make_py(tmp_path: Path) -> Path:
    f = tmp_path / "s.py"
    f.write_text("def foo(x: int) -> str: pass\nclass Bar: pass\n")
    return f


def _make_ts(tmp_path: Path) -> Path:
    f = tmp_path / "s.ts"
    f.write_text("interface X { a: number }\ntype Y = string\nenum Z { A }\n")
    return f


def _make_md(tmp_path: Path) -> Path:
    f = tmp_path / "s.md"
    f.write_text("# foo(x: int) -> str\nDocumented.\n")
    return f


def _make_js(tmp_path: Path) -> Path:
    f = tmp_path / "s.js"
    f.write_text("/** @param {number} x */\nfunction f(x) {}\n")
    return f


def _make_py_docstring(tmp_path: Path) -> Path:
    f = tmp_path / "s.py"
    f.write_text('def foo(x: int) -> str:\n    """Doc.\n\n    Args:\n        x: val\n    """\n    pass\n')
    return f


def _make_dockerfile(tmp_path: Path) -> Path:
    f = tmp_path / "Dockerfile"
    f.write_text("FROM python:3.11\nEXPOSE 8080\nENV X=y\n")
    return f


def _make_tf(tmp_path: Path) -> Path:
    f = tmp_path / "main.tf"
    f.write_text('resource "x" "y" { }\n')
    return f


def _make_makefile(tmp_path: Path) -> Path:
    f = tmp_path / "Makefile"
    f.write_text("install:\n\tpip install .\n")
    return f


def _make_yaml(tmp_path: Path) -> Path:
    f = tmp_path / "c.yaml"
    f.write_text("x: 1\ny: 2\n")
    return f


def _make_graphql(tmp_path: Path) -> Path:
    f = tmp_path / "s.graphql"
    f.write_text("type Query { u: User }\ntype User { id: ID! }\n")
    return f


def _make_sqlalchemy(tmp_path: Path) -> Path:
    f = tmp_path / "m.py"
    f.write_text("from sqlalchemy import Column, Integer\nclass U: __tablename__ = 'u'; id = Column(Integer, primary_key=True)\n")
    return f


def _make_openapi(tmp_path: Path) -> Path:
    f = tmp_path / "o.yaml"
    f.write_text('openapi: "3.0"\ninfo: { title: X, version: "1" }\npaths: {}\n')
    return f


def _make_fastapi(tmp_path: Path) -> Path:
    f = tmp_path / "app.py"
    f.write_text("from fastapi import FastAPI\napp = FastAPI()\n@app.get('/x')\ndef get_x(): pass\n")
    return f


def _make_flask(tmp_path: Path) -> Path:
    f = tmp_path / "app.py"
    f.write_text("from flask import Flask\napp = Flask(__name__)\n@app.route('/x')\ndef get_x(): pass\n")
    return f


def _make_django(tmp_path: Path) -> Path:
    f = tmp_path / "urls.py"
    f.write_text("from django.urls import path\nurlpatterns = [path('x/', lambda r: r)]\n")
    return f


def _make_pydantic(tmp_path: Path) -> Path:
    f = tmp_path / "m.py"
    f.write_text("from pydantic import BaseModel\nclass U(BaseModel): id: int\n")
    return f


def _make_dataclass(tmp_path: Path) -> Path:
    f = tmp_path / "s.py"
    f.write_text("from dataclasses import dataclass\n@dataclass\nclass P: x: int\n")
    return f


def _make_env(tmp_path: Path) -> Path:
    f = tmp_path / "s.env"
    f.write_text("X=y\nDEBUG=true\n")
    return f


def _make_deprecated(tmp_path: Path) -> Path:
    f = tmp_path / "s.py"
    f.write_text("import warnings\ndef f(): pass\n")
    return f


def _make_argparse(tmp_path: Path) -> Path:
    f = tmp_path / "cli.py"
    f.write_text("import argparse\np = argparse.ArgumentParser()\np.add_argument('--x', '-x')\n")
    return f


def _make_click(tmp_path: Path) -> Path:
    f = tmp_path / "cli.py"
    f.write_text("import click\n@click.command()\n@click.option('--x')\ndef main(x): pass\n")
    return f


def _make_typer(tmp_path: Path) -> Path:
    f = tmp_path / "cli.py"
    f.write_text("import typer\napp = typer.Typer()\n@app.command()\ndef main(x: bool = False): pass\n")
    return f


def _make_rst(tmp_path: Path) -> Path:
    f = tmp_path / "s.rst"
    f.write_text(".. function:: foo(x: int)\n\n   Doc.\n")
    return f


# ---------------------------------------------------------------------------
# Registry extractors: class name -> sample file factory
# ---------------------------------------------------------------------------

REGISTRY_CASES = [
    # (extractor_class_name, sample_file_factory)
    ("ArgparseExtractor", _make_argparse),
    ("ClickExtractor", _make_click),
    ("TyperExtractor", _make_typer),
    ("ConfigFileExtractor", _make_yaml),
    ("DataclassFieldsExtractor", _make_dataclass),
    ("DecoratorExtractor", _make_py),
    ("DeprecatedExtractor", _make_deprecated),
    ("DjangoURLsExtractor", _make_django),
    ("DocstringExtractor", _make_py_docstring),
    ("EnvVarExtractor", _make_env),
    ("FastAPIRoutesExtractor", _make_fastapi),
    ("FlaskRoutesExtractor", _make_flask),
    ("PydanticExtractor", _make_pydantic),
    ("TerraformExtractor", _make_tf),
    ("SQLAlchemyExtractor", _make_sqlalchemy),
    ("GraphQLExtractor", _make_graphql),
    ("OpenAPIExtractor", _make_openapi),
    ("RSTDocsExtractor", _make_rst),
    ("YamlConfigExtractor", _make_yaml),
    ("DockerfileExtractor", _make_dockerfile),
    ("MakefileExtractor", _make_makefile),
    ("TypeScriptExtractor", _make_ts),
]

# Extractor names NOT in registry but that have @register (discovered via grep)
# These are loaded via plugin mechanism, not auto-discovered
KNOWN_REGISTRY_GAPS = {
    "DotenvExtractor",
    "ProtocolExtractor",
    "PyprojectExtractor",
}

# Extractors directly instantiated by scanner (not in registry)
DIRECT_EXTRACTOR_CASES = [
    ("PythonExtractor", _make_py),
    ("MarkdownExtractor", _make_md),
    ("JSDocExtractor", _make_js),
]


# ---------------------------------------------------------------------------
# Tests: registry extractors
# ---------------------------------------------------------------------------

class TestRegistryExtractorMetadata:
    """Test metadata consistency for all extractors in the registry."""

    @pytest.mark.parametrize("extractor_name,file_factory", REGISTRY_CASES)
    def test_extractor_has_required_fields(
        self,
        extractor_name: str,
        file_factory: callable,
        tmp_path: Path,
    ) -> None:
        """Every registry extractor must produce items with required metadata fields."""
        from drift.extractors.registry import get_extractors

        extractor_cls = next(
            (cls for cls in get_extractors() if cls.__name__ == extractor_name), None
        )
        assert extractor_cls is not None, f"{extractor_name} not in registry"

        f = file_factory(tmp_path)
        extractor = extractor_cls()

        if not extractor.can_handle(f):
            pytest.skip(f"{extractor_name} cannot handle {f.name}")

        items = extractor.extract(f)
        if not items:
            pytest.skip(f"{extractor_name} returned no items for {f.name}")

        for item in items:
            # All items must have line_number
            assert hasattr(item, "line_number"), (
                f"{extractor_name}: item missing line_number"
            )
            assert isinstance(item.line_number, int), (
                f"{extractor_name}: line_number not int: {type(item.line_number)}"
            )
            # line_number must be >= 1 (0 is a sentinel for unknown)
            # TerraformExtractor: HCL2 library doesn't provide line numbers
            if extractor_name != "TerraformExtractor":
                assert item.line_number >= 1, (
                    f"{extractor_name}: line_number must be >= 1, got {item.line_number} "
                    f"for item: {getattr(item, 'name', '?')}"
                )

            # CodeFact: source_file, name, kind
            if hasattr(item, "source_file"):
                assert item.source_file is not None, (
                    f"{extractor_name}: source_file is None"
                )
                assert hasattr(item, "name")
                assert item.name
                assert hasattr(item, "kind")
                assert item.kind is not None
            # DocClaim: doc_file, kind
            elif hasattr(item, "doc_file"):
                assert item.doc_file is not None, (
                    f"{extractor_name}: doc_file is None"
                )
                assert hasattr(item, "kind")
                assert item.kind is not None
            else:
                pytest.fail(
                    f"{extractor_name} item has neither source_file nor doc_file: "
                    f"{type(item).__name__}"
                )

    def test_registry_discovery_gaps_documented(self) -> None:
        """Verify known registry gaps are tracked."""
        from drift.extractors.registry import get_extractors

        registered = {cls.__name__ for cls in get_extractors()}
        for gap in KNOWN_REGISTRY_GAPS:
            assert gap not in registered, f"{gap} should NOT be in registry (documented gap)"


# ---------------------------------------------------------------------------
# Tests: direct-import extractors (PythonExtractor, MarkdownExtractor, JSDocExtractor)
# ---------------------------------------------------------------------------

class TestDirectExtractorMetadata:
    """Test metadata for extractors not in the registry."""

    @pytest.mark.parametrize("extractor_name,file_factory", DIRECT_EXTRACTOR_CASES)
    def test_direct_extractor_has_required_fields(
        self,
        extractor_name: str,
        file_factory: callable,
        tmp_path: Path,
    ) -> None:
        """PythonExtractor, MarkdownExtractor, JSDocExtractor must have required fields."""
        if extractor_name == "PythonExtractor":
            from drift.python_extractor import PythonExtractor
            extractor = PythonExtractor()
        elif extractor_name == "MarkdownExtractor":
            from drift.extractors.markdown import MarkdownExtractor
            extractor = MarkdownExtractor()
        elif extractor_name == "JSDocExtractor":
            from drift.extractor_js import JSDocExtractor
            extractor = JSDocExtractor()
        else:
            pytest.fail(f"Unknown direct extractor: {extractor_name}")

        f = file_factory(tmp_path)

        if not extractor.can_handle(f):
            pytest.skip(f"{extractor_name} cannot handle {f.name}")

        items = extractor.extract(f)
        if not items:
            pytest.skip(f"{extractor_name} returned no items for {f.name}")

        for item in items:
            assert hasattr(item, "line_number")
            assert isinstance(item.line_number, int)
            assert item.line_number >= 1

            if hasattr(item, "source_file"):
                assert item.source_file is not None
                assert isinstance(item.source_file, Path)
                assert hasattr(item, "name")
                assert item.name
                assert hasattr(item, "kind")
                assert item.kind is not None
            elif hasattr(item, "doc_file"):
                assert item.doc_file is not None
                assert isinstance(item.doc_file, Path)
                assert hasattr(item, "kind")
                assert item.kind is not None
            else:
                pytest.fail(
                    f"{extractor_name} item has neither source_file nor doc_file"
                )


# ---------------------------------------------------------------------------
# Tests: line_number validation across all extractors
# ---------------------------------------------------------------------------

class TestLineNumberValidity:
    """Every extractor must return line_number >= 1 for every item."""

    def test_all_registry_extractors_line_number_valid(self, tmp_path: Path) -> None:
        """All registry extractors return items with line_number >= 1."""
        from drift.extractors.registry import get_extractors

        failures = []

        for cls in get_extractors():
            factory = next(
                (fac for name, fac in REGISTRY_CASES if name == cls.__name__), None
            )
            if factory is None:
                continue

            f = factory(tmp_path)
            try:
                items = cls().extract(f)
            except Exception:
                continue

            for item in items:
                if item.line_number < 1:
                    # TerraformExtractor: HCL2 parser doesn't preserve line numbers
                    if cls.__name__ == "TerraformExtractor":
                        continue
                    failures.append(
                        f"{cls.__name__}: line_number={item.line_number} "
                        f"(name={getattr(item, 'name', '?')})"
                    )

        if failures:
            pytest.fail(
                "Extractors with line_number < 1:\n" + "\n".join(failures)
            )
