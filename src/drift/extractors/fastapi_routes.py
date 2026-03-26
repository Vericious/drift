"""FastAPI route extractor for Drift.

Extracts API_ENDPOINT facts from FastAPI route decorators.
Handles @app.get/post/put/delete/patch, @router.get, @app.api_route, etc.
"""

import ast
import re
from pathlib import Path

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


def _get_constant_int(node: ast.expr) -> int | None:
    """Extract int value from an ast.Constant node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    return None


def _get_status_code(node: ast.expr) -> str | None:
    """Extract HTTP status code from a FastAPI status code value.

    Handles:
      - int: 201
      - ast.Attribute: status.HTTP_201_CREATED -> extracts "201"
      - str: "201"
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return str(node.value)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Attribute):
        # status.HTTP_201_CREATED -> extract 201 from attr name
        m = re.search(r"HTTP_(\d+)", node.attr)
        if m:
            return m.group(1)
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


def _get_default_value(node: ast.expr | None) -> str | None:
    """Get the default value as a string repr."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    elif isinstance(node, ast.Name):
        return node.id
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


HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "trace",
    "connect",
}


def _is_http_method(name: str) -> bool:
    return name.lower() in HTTP_METHODS


# router_var_name -> prefix string
RouterPrefixes = dict[str, str | None]


def _collect_router_prefixes(tree: ast.AST) -> RouterPrefixes:
    """First pass: collect APIRouter prefixes from constructor calls."""
    prefixes: RouterPrefixes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                var_name = target.id
                if isinstance(node.value, ast.Call):
                    callee = _get_func_name(node.value.func)
                    if callee == "APIRouter":
                        for kw in node.value.keywords:
                            if kw.arg == "prefix":
                                prefix = _get_constant_string(kw.value)
                                prefixes[var_name] = prefix
    return prefixes


def _combine_path(prefix: str | None, route_path: str | None) -> str | None:
    """Combine router prefix with a route path."""
    if route_path is None:
        return prefix
    if prefix:
        prefix = prefix.rstrip("/")
        route_path = route_path.lstrip("/")
        return f"{prefix}/{route_path}"
    return route_path


def _extract_decorator_info(
    decorator: ast.expr,
    router_prefixes: RouterPrefixes,
) -> tuple[list[str] | None, str | None, str | None, str | None, str | None, list[str] | None] | None:
    """Analyze a decorator and return (methods, path, router_name, status_code, response_model, tags).

    Returns None if this is not a FastAPI route decorator.
    """
    methods: list[str] | None = None
    path: str | None = None
    router_name: str | None = None
    status_code: str | None = None
    response_model: str | None = None
    tags: list[str] | None = None

    if isinstance(decorator, ast.Call):
        func_name = _get_func_name(decorator.func)

        # FastAPI HTTP method shortcuts: @app.get, @router.post, etc.
        if isinstance(decorator.func, ast.Attribute):
            attr_name = decorator.func.attr
            if _is_http_method(attr_name):
                method = attr_name.upper()
                methods = [method]
                path = (
                    _get_constant_string(decorator.args[0]) if decorator.args else None
                )
                obj_name = _get_func_name(decorator.func.value)
                # Apply router prefix if this is a router
                if obj_name and obj_name in router_prefixes:
                    router_prefix = router_prefixes.get(obj_name)
                    path = _combine_path(router_prefix, path)
                    router_name = obj_name
                elif obj_name:
                    router_name = obj_name
                for kw in decorator.keywords:
                    if kw.arg == "status_code":
                        status_code = _get_status_code(kw.value)
                    elif kw.arg == "response_model":
                        response_model = _get_annotation_name(kw.value)
                    elif kw.arg == "tags":
                        if isinstance(kw.value, ast.List):
                            tags = [
                                t
                                for t in [
                                    _get_constant_string(e) for e in kw.value.elts
                                ]
                                if t is not None
                            ]
                return (methods, path, router_name, status_code, response_model, tags)

        # @app.api_route("/path", methods=["GET", "POST"])
        if func_name and func_name.endswith(".api_route"):
            path = _get_constant_string(decorator.args[0]) if decorator.args else None
            if isinstance(decorator.func, ast.Attribute):
                obj_name = _get_func_name(decorator.func.value)
                if obj_name and obj_name in router_prefixes:
                    router_prefix = router_prefixes.get(obj_name)
                    path = _combine_path(router_prefix, path)
                    router_name = obj_name
            for kw in decorator.keywords:
                if kw.arg == "methods":
                    if isinstance(kw.value, ast.List):
                        methods = [
                            e.value.upper()
                            for e in kw.value.elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)
                        ]
                elif kw.arg == "status_code":
                    status_code = _get_status_code(kw.value)
                elif kw.arg == "response_model":
                    response_model = _get_annotation_name(kw.value)
                elif kw.arg == "tags":
                    if isinstance(kw.value, ast.List):
                        tags = [
                            t
                            for t in [_get_constant_string(e) for e in kw.value.elts]
                            if t is not None
                        ]
            return (methods, path, router_name, status_code, response_model, tags)

    elif isinstance(decorator, ast.Attribute):
        attr_name = decorator.attr
        if _is_http_method(attr_name):
            method = attr_name.upper()
            obj_name = _get_func_name(decorator.value)
            router_name = obj_name if obj_name else None
            return ([method], None, router_name, None, None, None)

    return None


def _extract_function_params(func_node: ast.FunctionDef) -> list[Parameter]:
    """Extract route function parameters with types and defaults."""
    params: list[Parameter] = []
    args = func_node.args
    num_defaults = len(args.defaults)
    num_params = len(args.args)

    for i, arg in enumerate(args.args):
        param_name = arg.arg
        type_str = _get_annotation_name(arg.annotation) if arg.annotation else None

        default_idx = i - (num_params - num_defaults)
        default_val = None
        if default_idx >= 0 and default_idx < len(args.defaults):
            default_val = _get_default_value(args.defaults[default_idx])

        kind = "path" if "path" in (type_str or "").lower() else "query"
        params.append(
            Parameter(
                name=param_name,
                type_annotation=type_str,
                default=default_val,
                kind=kind,
            )
        )

    return params


@register
class FastAPIRoutesExtractor(Extractor):
    """Extract API_ENDPOINT facts from FastAPI route decorators.

    Handles:
      @app.get('/path'), @app.post('/path'), etc.
      @router.get('/path'), etc.
      @app.api_route('/path', methods=['GET', 'POST'])

    Extracts path, HTTP methods, status_code, response_model, tags from decorator kwargs.
    Extracts function parameters (name, type, default) from the function signature.
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract API_ENDPOINT CodeFacts from FastAPI route decorators."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # First pass: collect APIRouter prefixes
        router_prefixes = _collect_router_prefixes(tree)

        # Second pass: find all route-decorated functions
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            for decorator in node.decorator_list:
                info = _extract_decorator_info(decorator, router_prefixes)
                if info is None:
                    continue

                methods, route_path, router_name, status_code, response_model, tags = (
                    info
                )
                if route_path is None:
                    continue
                if methods is None:
                    methods = ["GET"]

                func_params = _extract_function_params(node)

                for method in methods:
                    fact_name = f"{method.upper()} {route_path}"
                    metadata = {
                        "methods": list(methods),
                        "endpoint": route_path,
                        "router": router_name,
                        "status_code": status_code,
                        "response_model": response_model,
                        "tags": tags,
                        "function_name": node.name,
                    }
                    facts.append(
                        CodeFact(
                            name=fact_name,
                            kind=FactKind.API_ENDPOINT,
                            source_file=path,
                            line_number=node.lineno,
                            parameters=func_params,
                            metadata=metadata,
                        )
                    )

        return facts
