"""Dataclass field extractor for Drift.

Extracts CONFIG_KEY facts from @dataclass decorated classes.
Handles: field names, type annotations, defaults, default_factory.
Skips: ClassVar, InitVar.
"""

import ast
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind


def _get_annotation_name(node: ast.expr) -> str | None:
    """Get a type annotation as a string."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Attribute):
        parts = []
        cur: ast.expr = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    elif isinstance(node, ast.Subscript):
        base = _get_annotation_name(node.value)
        if base:
            if isinstance(node.slice, ast.Tuple):
                args = [_get_annotation_name(e) for e in node.slice.elts]
                str_args = [a for a in args if a is not None]
                return f"{base}[{', '.join(str_args)}]" if str_args else base
            else:
                inner = _get_annotation_name(node.slice)
                return f"{base}[{inner}]" if inner else base
    elif isinstance(node, ast.Constant):
        return repr(node.value)
    return None


def _get_default_value(node: ast.expr | None) -> str | None:
    """Get the default value as a string repr."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    elif isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.List):
        elts = [_get_default_value(e) for e in node.elts]
        return f"[{', '.join(e for e in elts if e)}]"
    elif isinstance(node, ast.Dict):
        pairs = []
        for k, v in zip(node.keys, node.values, strict=True):
            k_str = _get_default_value(k)
            v_str = _get_default_value(v)
            if k_str and v_str:
                pairs.append(f"{k_str}: {v_str}")
        return f"{{{', '.join(pairs)}}}"
    elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        operand = _get_default_value(node.operand)
        if operand:
            return ("+" if isinstance(node.op, ast.UAdd) else "-") + operand
    elif isinstance(node, ast.BinOp):
        left = _get_default_value(node.left)
        right = _get_default_value(node.right)
        if left and right:
            return f"({left} {type(node.op).__name__} {right})"
    return None


@register
class DataclassFieldsExtractor(Extractor):
    """Extract CONFIG_KEY facts from @dataclass field definitions.

    Extracts field names, type annotations, defaults, and default_factory.
    Skips ClassVar and InitVar annotated fields.
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CONFIG_KEY CodeFacts from @dataclass field definitions."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            # Check if class has @dataclass decorator
            has_dataclass = any(
                self._is_dataclass_decorator(d) for d in node.decorator_list
            )
            if not has_dataclass:
                continue

            class_name = node.name

            for item in node.body:
                if not isinstance(item, ast.AnnAssign):
                    continue

                # Skip ClassVar and InitVar
                if self._is_classvar_or_initvar(item.annotation):
                    continue

                field_name = (
                    item.target.id if isinstance(item.target, ast.Name) else None
                )
                if field_name is None:
                    continue

                type_str = _get_annotation_name(item.annotation)
                default_val = None
                if item.value:
                    # Handle field(default=X) or field(default_factory=Y) calls
                    if (
                        isinstance(item.value, ast.Call)
                        and isinstance(item.value.func, ast.Name)
                        and item.value.func.id == "field"
                    ):
                        for kw in item.value.keywords:
                            if kw.arg in ("default", "default_factory"):
                                default_val = _get_default_value(kw.value)
                                break
                    else:
                        default_val = _get_default_value(item.value)
                metadata = {
                    "class_name": class_name,
                    "field_name": field_name,
                    "field_type": type_str,
                    "default": default_val,
                }

                fact_name = f"{class_name}.{field_name}"
                facts.append(
                    CodeFact(
                        name=fact_name,
                        kind=FactKind.CONFIG_KEY,
                        source_file=path,
                        line_number=item.lineno or 0,
                        metadata=metadata,
                    )
                )

        return facts

    def _is_dataclass_decorator(self, decorator: ast.expr) -> bool:
        """Return True if the decorator is @dataclass."""
        if isinstance(decorator, ast.Name):
            return decorator.id == "dataclass"
        if isinstance(decorator, ast.Attribute):
            return decorator.attr == "dataclass"
        if isinstance(decorator, ast.Call):
            func_name = self._get_func_name(decorator.func)
            return func_name == "dataclass"
        return False

    def _get_func_name(self, node: ast.expr) -> str | None:
        """Get the dotted name from an Attribute or Name node."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_func_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
        return None

    def _is_classvar_or_initvar(self, annotation: ast.expr) -> bool:
        """Return True if annotation is ClassVar[...] or InitVar[...]."""
        if isinstance(annotation, ast.Subscript):
            base = _get_annotation_name(annotation.value)
            return base in ("ClassVar", "InitVar")
        name = _get_annotation_name(annotation)
        return name in ("ClassVar", "InitVar")
