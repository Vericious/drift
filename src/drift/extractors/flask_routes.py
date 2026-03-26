"""Flask route extractor for Drift.

Extracts API_ENDPOINT facts from Flask route decorators.
Handles @app.route, @blueprint.route, @app.get/post (Flask 2.0+).
"""

import ast
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind


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


def _get_blueprint_prefix(call: ast.Call) -> str | None:
    """Extract url_prefix from a Blueprint(...) constructor call."""
    for kw in call.keywords:
        if kw.arg == "url_prefix":
            return _get_constant_string(kw.value)
    return None


def _get_blueprint_name(call: ast.Call) -> str | None:
    """Extract the blueprint name (first positional string arg) from a Blueprint(...) call."""
    if call.args:
        return _get_constant_string(call.args[0])
    return None


def _get_route_methods_and_path(
    call: ast.Call,
) -> tuple[list[str] | None, str | None]:
    """Extract HTTP methods and path from a route() or get/post/... call.

    Returns (methods, path) where methods is a list like ['GET', 'POST'] or
    ['GET'] for get/post shortcuts, and path is the URL path string.
    """
    methods = None
    path = None

    for kw in call.keywords:
        if kw.arg == "methods":
            if isinstance(kw.value, ast.List):
                methods = []
                for elt in kw.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        methods.append(elt.value.upper())
        elif kw.arg in ("rule", "url_prefix"):
            path = _get_constant_string(kw.value)

    # First positional arg is the path/rule
    if path is None and call.args:
        path = _get_constant_string(call.args[0])

    return methods, path


def _combine_path(prefix: str | None, route_path: str | None) -> str | None:
    """Combine blueprint prefix with a route path."""
    if route_path is None:
        return prefix
    if prefix:
        prefix = prefix.rstrip("/")
        route_path = route_path.lstrip("/")
        return f"{prefix}/{route_path}"
    return route_path


# bp_var_name -> (url_prefix, bp_internal_name)
BlueprintInfo = dict[str, tuple[str | None, str | None]]


@register
class FlaskRoutesExtractor(Extractor):
    """Extract API_ENDPOINT facts from Flask route decorators.

    Handles:
      @app.route('/path', methods=['GET', 'POST'])
      @app.get('/path'), @app.post('/path'), etc. (Flask 2.0+)
      @blueprint.route('/path', methods=['GET'])
      @bp.get('/path'), @bp.post('/path'), etc.

    The name of the fact is "METHOD /path", e.g. "GET /users" or "POST /api/items".
    """

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

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract API_ENDPOINT CodeFacts from Flask route decorators."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # First pass: collect Blueprint info (url_prefix + internal name)
        blueprint_info: BlueprintInfo = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        bp_var_name = target.id
                    else:
                        continue
                    if isinstance(node.value, ast.Call):
                        callee = _get_func_name(node.value.func)
                        if callee == "Blueprint":
                            blueprint_info[bp_var_name] = (
                                _get_blueprint_prefix(node.value),
                                _get_blueprint_name(node.value),
                            )

        # Second pass: find all route-decorated functions
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue

            for decorator in node.decorator_list:
                result = self._analyze_decorator(decorator, blueprint_info)
                if result is None:
                    continue

                methods, route_path, blueprint_internal_name = result
                if route_path is None:
                    continue
                if methods is None:
                    methods = ["GET"]

                for method in methods:
                    fact_name = f"{method.upper()} {route_path}"
                    metadata = {
                        "methods": list(methods),
                        "endpoint": route_path,
                        "blueprint": blueprint_internal_name,
                        "function_name": node.name,
                    }
                    facts.append(
                        CodeFact(
                            name=fact_name,
                            kind=FactKind.API_ENDPOINT,
                            source_file=path,
                            line_number=node.lineno,
                            metadata=metadata,
                        )
                    )

        return facts

    def _analyze_decorator(
        self,
        decorator: ast.expr,
        blueprint_info: BlueprintInfo,
    ) -> tuple[list[str] | None, str | None, str | None] | None:
        """Analyze a decorator and return (methods, path, blueprint_internal_name).

        Returns None if this is not a Flask route decorator.
        """
        # Pattern 1: @bp.route('/path', methods=[...]) or @app.route('/path')
        if isinstance(decorator, ast.Call):
            func_name = _get_func_name(decorator.func)
            if func_name and (func_name.endswith(".route") or func_name in ("route",)):
                methods, route_path = _get_route_methods_and_path(decorator)
                blueprint_internal_name: str | None = None
                bp_prefix: str | None = None

                if isinstance(decorator.func, ast.Attribute):
                    obj_name = _get_func_name(decorator.func.value)
                    if obj_name and obj_name not in ("app",):
                        bp_prefix, blueprint_internal_name = blueprint_info.get(
                            obj_name, (None, None)
                        )
                        route_path = _combine_path(bp_prefix, route_path)
                elif isinstance(decorator.func, ast.Name):
                    if decorator.func.id not in ("route", "app"):
                        obj_name = decorator.func.id
                        bp_prefix, blueprint_internal_name = blueprint_info.get(
                            obj_name, (None, None)
                        )
                        route_path = _combine_path(bp_prefix, route_path)

                return (methods, route_path, blueprint_internal_name)

            # Pattern 2: @bp.get('/path'), @app.post('/path'), etc. (Flask 2.0+)
            if isinstance(decorator.func, ast.Attribute):
                attr_name = decorator.func.attr
                if attr_name.lower() in self.HTTP_METHODS:
                    method = attr_name.upper()
                    route_path = None
                    if decorator.args:
                        route_path = _get_constant_string(decorator.args[0])
                    if route_path is None:
                        for kw in decorator.keywords:
                            if kw.arg in ("rule", "url_prefix", "path"):
                                route_path = _get_constant_string(kw.value)

                    obj_name = _get_func_name(decorator.func.value)
                    blueprint_internal_name = None
                    if obj_name:
                        bp_prefix, blueprint_internal_name = blueprint_info.get(
                            obj_name, (None, None)
                        )
                        route_path = _combine_path(bp_prefix, route_path)

                    return ([method], route_path, blueprint_internal_name)

        # Pattern 3: bare @bp.get (not called)
        if isinstance(decorator, ast.Attribute):
            attr_name = decorator.attr
            if attr_name.lower() in self.HTTP_METHODS:
                method = attr_name.upper()
                obj_name = _get_func_name(decorator.value)
                blueprint_internal_name = None
                if obj_name:
                    _, blueprint_internal_name = blueprint_info.get(
                        obj_name, (None, None)
                    )
                return ([method], None, blueprint_internal_name)

        return None
