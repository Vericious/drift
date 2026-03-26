"""Pydantic settings/model extractor for Drift.

Detects Pydantic BaseSettings and BaseModel field definitions via AST analysis.
"""
import ast
from pathlib import Path
from typing import Any, Optional

from drift.extractors.base import Extractor
from drift.models import CodeFact, FactKind, Parameter


def _get_func_name(node: ast.expr) -> Optional[str]:
    """Get the dotted name from an Attribute or Name node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _get_func_name(node.value)
        if parent:
            return f"{parent}.{node.attr}"
    return None


def _get_constant_value(node: ast.expr) -> Any:
    """Extract value from an ast.Constant node."""
    if isinstance(node, ast.Constant):
        return node.value
    return None


def _is_pydantic_base(node: ast.expr, pydantic_names: tuple[str, ...]) -> bool:
    """Return True if node inherits from a Pydantic class."""
    if isinstance(node, ast.Name):
        return node.id in pydantic_names
    if isinstance(node, ast.Attribute):
        name = _get_func_name(node)
        return name in pydantic_names
    return False


def _extract_field_info(annotation: ast.expr, value: ast.expr | None) -> dict:
    """Extract field metadata from an annotation and optional default value.

    Handles:
      name: Type = Field(default, env='VAR', alias='x', description='...')
      name: Type = default_value
      name: Type
    """
    result = {
        "field_type": None,
        "default": None,
        "env_var": None,
        "alias": None,
        "description": None,
    }

    # Extract type from annotation
    result["field_type"] = _get_type_from_annotation(annotation)

    if value is None:
        return result

    # Field(...) call
    if isinstance(value, ast.Call):
        func_name = _get_func_name(value.func)
        if func_name and (func_name.endswith(".Field") or func_name == "Field"):
            # It's a Field() call
            for kw in value.keywords:
                key = kw.arg
                val = kw.value

                if key == "default":
                    result["default"] = repr(_get_constant_value(val)) if isinstance(val, ast.Constant) else val.id if isinstance(val, ast.Name) else None

                elif key == "env":
                    result["env_var"] = _get_constant_value(val) if isinstance(val, ast.Constant) else None

                elif key == "alias":
                    result["alias"] = _get_constant_value(val) if isinstance(val, ast.Constant) else None

                elif key == "description":
                    result["description"] = _get_constant_value(val) if isinstance(val, ast.Constant) else None

            # First positional arg might be the default (Field(False, ...))
            if result["default"] is None and value.args:
                first_arg = value.args[0]
                if isinstance(first_arg, ast.Constant):
                    result["default"] = repr(_get_constant_value(first_arg))
                elif isinstance(first_arg, ast.Name):
                    result["default"] = first_arg.id

        elif func_name and (func_name.endswith(".validator") or func_name.endswith(".root_validator") or func_name in ("validator", "root_validator")):
            # Skip validators
            return None

    # Plain default value (not Field call)
    if result["default"] is None and result["env_var"] is None:
        if isinstance(value, ast.Constant):
            result["default"] = repr(value.value)
        elif isinstance(value, ast.Name):
            result["default"] = value.id

    return result


def _get_type_from_annotation(annotation: ast.expr) -> Optional[str]:
    """Extract type name from an annotation."""
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Attribute):
        return _get_func_name(annotation)
    elif isinstance(annotation, ast.Subscript):
        # List[T], Optional[T], Dict[K, V], etc.
        base = _get_type_from_annotation(annotation.value)
        if base:
            if isinstance(annotation.slice, ast.Tuple):
                args = []
                for elt in annotation.slice.elts:
                    t = _get_type_from_annotation(elt)
                    if t:
                        args.append(t)
                return f"{base}[{', '.join(args)}]" if args else base
            else:
                inner = _get_type_from_annotation(annotation.slice)
                return f"{base}[{inner}]" if inner else base
        return _get_func_name(annotation)
    elif isinstance(annotation, ast.Constant):
        return repr(annotation.value)
    return None


class PydanticExtractor(Extractor):
    """Extract CONFIG_KEY facts from Pydantic BaseSettings and BaseModel classes.

    Finds field definitions and produces CodeFact objects with kind="config_key".
    """

    # Names that indicate Pydantic base classes
    PYDANTIC_BASES = ("BaseSettings", "BaseModel", "Settings", "Base")

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list:
        """Extract CONFIG_KEY CodeFacts from Pydantic models."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # First pass: find Pydantic class names and their field assignments
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Check if class inherits from Pydantic base
            if not any(
                _is_pydantic_base(base, self.PYDANTIC_BASES)
                for base in node.bases
            ):
                continue

            # Extract field assignments from the class body
            for item in node.body:
                if not isinstance(item, ast.AnnAssign):
                    continue

                # Must have annotation
                if item.annotation is None:
                    continue

                # Skip if it's not a simple name (e.g., computed fields)
                if not isinstance(item.target, ast.Name):
                    continue

                field_name = item.target.id
                field_info = _extract_field_info(item.annotation, item.value)

                if field_info:
                    fact = self._build_codefact(
                        class_name=node.name,
                        field_name=field_name,
                        field_info=field_info,
                        source_file=path,
                        line_number=item.lineno or item.target.lineno,
                    )
                    facts.append(fact)

        return facts

    def _build_codefact(
        self,
        class_name: str,
        field_name: str,
        field_info: dict,
        source_file: Path,
        line_number: int,
    ) -> CodeFact:
        """Build a CodeFact from extracted field metadata."""
        fact_name = f"{class_name}.{field_name}"
        field_type = field_info.get("field_type")

        params = []
        if field_type:
            params.append(Parameter(
                name=field_name,
                type_annotation=field_type,
                default=field_info.get("default"),
                kind="keyword",
            ))

        return CodeFact(
            name=fact_name,
            kind=FactKind.CONFIG_KEY,
            source_file=source_file,
            line_number=line_number,
            parameters=params,
            metadata={
                "env_var": field_info.get("env_var"),
                "alias": field_info.get("alias"),
                "description": field_info.get("description"),
                "field_type": field_type,
                "class_name": class_name,
                "field_name": field_name,
            },
        )
