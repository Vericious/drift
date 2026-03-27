"""SQLAlchemy ORM model extractor for Drift.

Extracts TABLE_SCHEMA facts from SQLAlchemy ORM model definitions.
Detects declarative_base() and class definitions inheriting from Base.
"""

import ast
import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


def _get_func_name(node: ast.expr) -> str | None:
    """Get the dotted name from an Attribute or Name node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _get_func_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _get_constant_string(node: ast.expr) -> str | None:
    """Extract string value from an ast.Constant node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_annotation_name(node: ast.expr) -> str | None:
    """Get a type annotation as a string."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        name = _get_func_name(node)
        return name
    elif isinstance(node, ast.Subscript):
        base = _get_annotation_name(node.value)
        if base:
            if isinstance(node.slice, ast.Tuple):
                args = [_get_annotation_name(elt) for elt in node.slice.elts]
                str_args = [a for a in args if a is not None]
                return f"{base}[{', '.join(str_args)}]" if str_args else base
            else:
                inner = _get_annotation_name(node.slice)
                return f"{base}[{inner}]" if inner else base
    elif isinstance(node, ast.Constant):
        return repr(node.value)
    return None


def _extract_column_args(column_call: ast.Call) -> dict[str, Any]:
    """Extract Column() arguments into a dict."""
    result = {
        "col_type": None,
        "nullable": True,
        "primary_key": False,
        "default": None,
        "index": False,
        "foreign_key": None,
    }

    # First positional arg is usually the type
    if column_call.args:
        first_arg = column_call.args[0]
        result["col_type"] = _get_annotation_name(first_arg)

    # Check positional args for ForeignKey (usually second positional arg)
    for i, arg in enumerate(column_call.args):
        if i == 0:
            continue  # Skip type
        if isinstance(arg, ast.Call):
            func_name = _get_func_name(arg.func)
            if func_name and func_name.endswith("ForeignKey"):
                # ForeignKey("users.id") - first positional arg is the FK string
                if arg.args and isinstance(arg.args[0], ast.Constant):
                    result["foreign_key"] = arg.args[0].value

    # Keyword arguments
    for kw in column_call.keywords:
        key = kw.arg
        value = kw.value

        if key == "primary_key":
            if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                result["primary_key"] = value.value
        elif key == "nullable":
            if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                result["nullable"] = value.value
        elif key == "default":
            if isinstance(value, ast.Constant):
                result["default"] = repr(value.value)
            elif isinstance(value, ast.Name):
                result["default"] = value.id
            elif isinstance(value, ast.Call):
                result["default"] = _get_func_name(value.func) or "..."
        elif key == "index":
            if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                result["index"] = value.value
        elif key == "foreign_key":
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                result["foreign_key"] = value.value
            elif isinstance(value, ast.Attribute):
                result["foreign_key"] = _get_func_name(value)

    return result


def _extract_relationship_args(rel_call: ast.Call) -> dict[str, Any]:
    """Extract Relationship() arguments into a dict."""
    result = {
        "target": None,
        "back_populates": None,
        "foreign_keys": None,
        "uselist": True,
    }

    # Usually first positional arg is the target
    if rel_call.args:
        first_arg = rel_call.args[0]
        if isinstance(first_arg, ast.Name):
            result["target"] = first_arg.id
        elif isinstance(first_arg, ast.Attribute):
            result["target"] = _get_func_name(first_arg)
        elif isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            result["target"] = first_arg.value

    for kw in rel_call.keywords:
        key = kw.arg
        value = kw.value

        if key == "back_populates":
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                result["back_populates"] = value.value
        elif key == "foreign_keys":
            if isinstance(value, ast.Call):
                result["foreign_keys"] = _get_func_name(value.func)
            elif isinstance(value, ast.Name):
                result["foreign_keys"] = value.id
        elif key == "uselist":
            if isinstance(value, ast.Constant) and isinstance(value.value, bool):
                result["uselist"] = value.value

    return result


@register
class SQLAlchemyExtractor(Extractor):
    """Extract TABLE_SCHEMA facts from SQLAlchemy ORM models.

    Detects:
      declarative_base() calls
      class ModelName(Base): declarations
      Column() definitions with types, nullable, primary_key, default
      relationship() definitions

    Each column becomes a TABLE_SCHEMA fact with name = "table_name.column_name".
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def _find_declarative_base(self, tree: ast.AST) -> str | None:
        """Find the variable name assigned to declarative_base()."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = _get_func_name(node.func)
                if func_name and func_name.endswith("declarative_base"):
                    # Look for assignment: Base = declarative_base()
                    # This is typically handled by tracking the assignment target
                    pass
        return "Base"  # Default assumption

    def _is_base_subclass(self, class_node: ast.ClassDef, base_names: set[str]) -> bool:
        """Return True if class inherits from any of base_names."""
        for base in class_node.bases:
            if isinstance(base, ast.Name):
                if base.id in base_names:
                    return True
            elif isinstance(base, ast.Attribute):
                name = _get_func_name(base)
                if name and any(b in name for b in base_names):
                    return True
        return False

    def _extract_model_columns(self, class_node: ast.ClassDef, table_name: str) -> list[CodeFact]:
        """Extract all Column() definitions from a model class."""
        facts: list[CodeFact] = []

        for node in class_node.body:
            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue

                col_name = target.id

                # Check if value is a Column() call
                if isinstance(node.value, ast.Call):
                    func_name = _get_func_name(node.value.func)
                    if func_name and func_name.endswith("Column"):
                        col_info = _extract_column_args(node.value)
                        fact_name = f"{table_name}.{col_name}"
                        metadata = {
                            "column_type": col_info["col_type"],
                            "nullable": col_info["nullable"],
                            "primary_key": col_info["primary_key"],
                            "default": col_info["default"],
                            "index": col_info["index"],
                            "foreign_key": col_info["foreign_key"],
                            "table": table_name,
                        }
                        facts.append(
                            CodeFact(
                                name=fact_name,
                                kind=FactKind.TABLE_SCHEMA,
                                source_file=Path("<sqlalchemy>"),
                                line_number=node.lineno,
                                metadata=metadata,
                            )
                        )

        return facts

    def _extract_model_relationships(self, class_node: ast.ClassDef, table_name: str) -> list[CodeFact]:
        """Extract relationship() definitions from a model class."""
        facts: list[CodeFact] = []

        for node in class_node.body:
            if not isinstance(node, ast.Assign):
                continue

            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue

                rel_name = target.id

                if isinstance(node.value, ast.Call):
                    func_name = _get_func_name(node.value.func)
                    if func_name and func_name.endswith("relationship"):
                        rel_info = _extract_relationship_args(node.value)
                        fact_name = f"{table_name}.{rel_name}"
                        metadata = {
                            "relationship_target": rel_info["target"],
                            "back_populates": rel_info["back_populates"],
                            "foreign_keys": rel_info["foreign_keys"],
                            "uselist": rel_info["uselist"],
                            "table": table_name,
                            "is_relationship": True,
                        }
                        facts.append(
                            CodeFact(
                                name=fact_name,
                                kind=FactKind.TABLE_SCHEMA,
                                source_file=Path("<sqlalchemy>"),
                                line_number=node.lineno,
                                metadata=metadata,
                            )
                        )

        return facts

    def _get_table_name(self, class_node: ast.ClassDef) -> str | None:
        """Extract __tablename__ from a model class if defined."""
        for node in class_node.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__tablename__":
                        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                            return node.value.value
        return None

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract TABLE_SCHEMA CodeFacts from SQLAlchemy models."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # Find declarative_base assignment to get the Base name
        base_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if isinstance(node.value, ast.Call):
                            func_name = _get_func_name(node.value.func)
                            if func_name and "declarative_base" in func_name:
                                base_names.add(target.id)

        # Default to "Base" if not found
        if not base_names:
            base_names.add("Base")

        # Find all classes inheriting from Base
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            if self._is_base_subclass(node, base_names):
                table_name = self._get_table_name(node)
                if table_name is None:
                    # Use class name as fallback, lowercased
                    table_name = node.name.lower()

                facts.extend(self._extract_model_columns(node, table_name))
                facts.extend(self._extract_model_relationships(node, table_name))

        return facts
