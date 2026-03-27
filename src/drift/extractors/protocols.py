"""Protocol and ABC extractor for Drift.

Extracts interface contracts from Python Protocol and Abstract Base Class definitions.
"""

import ast
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


def _get_annotation_name(node: ast.expr | None) -> str | None:
    """Get a type annotation as a string."""
    if node is None:
        return None
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
        if node.value is None:
            return None
        return repr(node.value)
    return None


def _get_parameters(func: ast.FunctionDef | ast.AsyncFunctionDef) -> list[Parameter]:
    """Extract parameters from a function definition."""
    params = []
    for arg in func.args.posonlyargs:
        params.append(Parameter(name=arg.arg, kind="positional"))
    for arg in func.args.args:
        params.append(Parameter(name=arg.arg, kind="positional"))
    if func.args.vararg:
        params.append(Parameter(name=func.args.vararg.arg, kind="varargs"))
    for arg in func.args.kwonlyargs:
        params.append(Parameter(name=arg.arg, kind="keyword"))
    if func.args.kwarg:
        params.append(Parameter(name=func.args.kwarg.arg, kind="varkw"))

    # Set default values
    defaults = func.args.defaults or []
    num_defaults = len(defaults)
    num_params = len(params)
    for i, default in enumerate(defaults):
        param_idx = num_params - num_defaults + i
        if param_idx >= 0:
            params[param_idx].default = ast.unparse(default)

    return params


def _is_abstract_method(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a method has @abstractmethod decorator."""
    for decorator in func.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id == "abstractmethod":
            return True
        if isinstance(decorator, ast.Attribute) and decorator.attr == "abstractmethod":
            return True
    return False


def _is_protocol_stub(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a Protocol method is a stub (body is just ... or ... + docstring)."""
    # Filter out docstrings (ast.Expr with str Constant at start of body)
    body = func.body
    # Skip leading docstring
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]

    if len(body) == 1 and isinstance(body[0], ast.Expr):
        if isinstance(body[0].value, ast.Constant) and body[0].value.value is ...:
            return True
    return False


@register
class ProtocolExtractor(Extractor):
    """Extract Protocol and ABC interface contracts from Python files."""

    def can_handle(self, file_path: Path) -> bool:
        """Return True for .py files."""
        return file_path.suffix.lower() == ".py"

    def extract(self, file_path: Path) -> list[Any]:
        """Extract Protocol and ABC facts from a Python file."""
        content = file_path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError:
            return []

        facts = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_facts = self._extract_class(node, file_path)
                facts.extend(class_facts)

        return facts

    def _extract_class(self, node: ast.ClassDef, source_file: Path) -> list[Any]:
        """Extract facts from a Protocol or ABC class."""
        facts = []

        # Determine if this class is a Protocol or ABC
        is_protocol = False
        is_abc = False
        is_runtime_checkable = False

        for base in node.bases:
            if isinstance(base, ast.Name):
                if base.id == "Protocol":
                    is_protocol = True
                elif base.id == "ABC":
                    is_abc = True
            elif isinstance(base, ast.Attribute):
                if base.attr == "Protocol":
                    is_protocol = True
                elif base.attr == "ABC":
                    is_abc = True

        # Check for @runtime_checkable on Protocol
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "runtime_checkable":
                is_runtime_checkable = True
            elif isinstance(decorator, ast.Attribute) and decorator.attr == "runtime_checkable":
                is_runtime_checkable = True

        if not (is_protocol or is_abc):
            return facts

        # Extract methods
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if is_protocol:
                    # For Protocol: extract method stubs (body is ...)
                    if _is_protocol_stub(item):
                        fact = self._make_fact(item, node.name, source_file, item.lineno, "protocol_method")
                        fact.metadata["is_runtime_checkable"] = is_runtime_checkable
                        facts.append(fact)
                elif is_abc:
                    # For ABC: extract @abstractmethod methods
                    if _is_abstract_method(item):
                        fact = self._make_fact(item, node.name, source_file, item.lineno, "abstract_method")
                        facts.append(fact)

        return facts

    def _make_fact(
        self,
        func: ast.FunctionDef | ast.AsyncFunctionDef,
        class_name: str,
        source_file: Path,
        line_number: int,
        method_category: str,
    ) -> CodeFact:
        """Build a CodeFact for a Protocol or ABC method."""
        params = _get_parameters(func)
        return_type = None
        if func.returns:
            return_type = _get_annotation_name(func.returns)

        fact = CodeFact(
            name=f"{class_name}.{func.name}",
            kind=FactKind.FUNCTION,
            source_file=source_file,
            line_number=line_number,
            parameters=params,
            return_type=return_type,
            module=class_name,
            metadata={"method_category": method_category},
        )
        return fact
