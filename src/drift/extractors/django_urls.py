"""Django URL pattern extractor for Drift.

Extracts API_ENDPOINT facts from Django urlpatterns using url() and path().
Handles: url(), path(), include(), and URL converters (int, str, slug, uuid, path).
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


def _convert_django_param(param_str: str) -> Parameter:
    """Convert a Django URL converter pattern to a Parameter.

    Handles: <int:name>, <str:name>, <slug:name>, <uuid:name>, <path:name>
    """
    # Pattern: <converter:optional_name> or just <converter>
    match = re.match(r"<(\w+)(?::(\w+))?>", param_str)
    if match:
        converter = match.group(1)
        name = match.group(2)
        type_map = {
            "int": "int",
            "str": "str",
            "slug": "slug",
            "uuid": "uuid",
            "path": "path",
        }
        type_str = type_map.get(converter, converter)
        return Parameter(
            name=name or converter,
            type_annotation=type_str,
            kind="path",
        )
    return Parameter(name=param_str, kind="path")


def _extract_params_from_path(path: str) -> list[Parameter]:
    """Extract path parameters from a Django path string."""
    # Find all <converter:name> or <name> patterns
    params: list[Parameter] = []
    # Match <converter:name>, <converter:>, or just <> (treated as str)
    pattern = r"<(?:\w+:)?(\w+)?>" 
    for match in re.finditer(pattern, path):
        name = match.group(1)
        if name:
            params.append(Parameter(name=name, kind="path"))
    return params


@register
class DjangoURLsExtractor(Extractor):
    """Extract API_ENDPOINT facts from Django URL patterns.

    Handles:
      url(r'^regex/$', view, name='name')
      path('str/<int:id>/', view, name='name')
      path('str/<slug:slug>/', include('module.urls'))

    Extracts: URL path, view name, view function/class, parameters.
    Fact name format: GET /path (method is inferred as GET by default).
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def _resolve_include(self, node: ast.expr, router_prefix: str = "") -> list[tuple[str, str | None]]:
        """Resolve an include() call to get nested URL patterns."""
        results = []
        if isinstance(node, ast.Call):
            func_name = _get_func_name(node.func)
            if func_name == "include":
                # include('app.urls') or include(module.urls)
                if node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        module_path = arg.value
                        # Try to find and parse the included URLconf
                        try:
                            import importlib.util
                            spec = importlib.util.find_spec(module_path)
                            if spec and spec.origin:
                                included_path = Path(spec.origin)
                                included_facts = self.extract(included_path)
                                for fact in included_facts:
                                    if fact.name.startswith("/"):
                                        resolved = router_prefix + fact.name
                                        results.append((resolved, fact.metadata.get("view_name")))
                        except (ImportError, OSError):
                            pass
        return results

    def _extract_from_patterns(self, patterns: list, prefix: str = "") -> list[CodeFact]:
        """Recursively extract facts from a list of URL patterns."""
        facts: list[CodeFact] = []

        for pattern in patterns:
            if not isinstance(pattern, (ast.Call, ast.Expr)):
                continue

            if isinstance(pattern, ast.Expr) and isinstance(pattern.value, ast.Call):
                # urlpatterns.append(path(...)) form
                pattern = pattern.value

            call = pattern if isinstance(pattern, ast.Call) else None
            if call is None:
                continue

            func_name = _get_func_name(call.func)

            if func_name == "path":
                # path('route/', view, name='name')
                route_path = _get_constant_string(call.args[0]) if call.args else None
                view_arg = call.args[1] if len(call.args) > 1 else None
                view_name = None
                view_function = None

                if isinstance(view_arg, ast.Name):
                    view_function = view_arg.id
                    view_name = view_function
                elif isinstance(view_arg, ast.Attribute):
                    view_function = _get_func_name(view_arg)
                    view_name = view_function
                elif isinstance(view_arg, ast.Call):
                    # views.as_view() or similar
                    view_function = _get_func_name(view_arg)
                    view_name = view_function

                # Extract name from kwargs
                name = None
                for kw in call.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = kw.value.value

                if route_path:
                    full_path = prefix + route_path
                    params = _extract_params_from_path(full_path)
                    fact_name = f"GET {full_path}"
                    metadata = {
                        "view_name": name,
                        "view_function": view_function,
                        "parameters": [{"name": p.name, "kind": p.kind} for p in params],
                    }
                    facts.append(
                        CodeFact(
                            name=fact_name,
                            kind=FactKind.API_ENDPOINT,
                            source_file=Path("<django_urls>"),
                            line_number=call.lineno if hasattr(call, 'lineno') else 0,
                            parameters=params,
                            metadata=metadata,
                        )
                    )

            elif func_name == "url":
                # url(r'^regex/$', view, name='name')
                # First arg could be a regex pattern
                route_arg = call.args[0] if call.args else None
                route_path = None

                if isinstance(route_arg, ast.Constant) and isinstance(route_arg.value, str):
                    route_path = route_arg.value
                elif isinstance(route_arg, ast.Call):
                    # re_path case - handled below
                    pass

                view_arg = call.args[1] if len(call.args) > 1 else None
                view_function = None
                if isinstance(view_arg, ast.Name):
                    view_function = view_arg.id
                elif isinstance(view_arg, ast.Attribute):
                    view_function = _get_func_name(view_arg)

                name = None
                for kw in call.keywords:
                    if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                        name = kw.value.value

                if route_path:
                    # Convert regex to path-like format for fact name
                    # Replace regex quantifiers with param placeholders
                    display_path = route_path
                    # Simple conversion: (\d+) -> {id}, (\w+) -> {slug}
                    display_path = re.sub(r'\\d\+', '{id}', display_path)
                    display_path = re.sub(r'\\w\+', '{slug}', display_path)
                    display_path = re.sub(r'\\D\+', '{id}', display_path)
                    
                    full_path = prefix + display_path
                    fact_name = f"GET {full_path}"
                    metadata = {
                        "view_name": name,
                        "view_function": view_function,
                        "route_regex": route_path,
                    }
                    facts.append(
                        CodeFact(
                            name=fact_name,
                            kind=FactKind.API_ENDPOINT,
                            source_file=Path("<django_urls>"),
                            line_number=call.lineno if hasattr(call, 'lineno') else 0,
                            metadata=metadata,
                        )
                    )

            elif func_name == "include":
                # include('app.urls') or include((patterns, app_name))
                include_arg = call.args[0] if call.args else None
                if isinstance(include_arg, ast.Constant) and isinstance(include_arg.value, str):
                    included_module = include_arg.value
                    try:
                        import importlib.util
                        spec = importlib.util.find_spec(included_module)
                        if spec and spec.origin:
                            included_path = Path(spec.origin)
                            included_facts = self._extract_from_file(included_path, prefix)
                            facts.extend(included_facts)
                    except (ImportError, OSError):
                        pass
                elif isinstance(include_arg, ast.Tuple):
                    # (patterns, app_name) tuple
                    patterns_arg = include_arg.elts[0] if include_arg.elts else None
                    if isinstance(patterns_arg, ast.List):
                        nested_patterns = []
                        for elt in patterns_arg.elts:
                            if isinstance(elt, ast.Call):
                                nested_patterns.append(elt)
                            elif isinstance(elt, ast.Expr) and isinstance(elt.value, ast.Call):
                                nested_patterns.append(elt.value)
                        nested_facts = self._extract_from_patterns(nested_patterns, prefix)
                        facts.extend(nested_facts)

        return facts

    def _extract_from_file(self, path: Path, prefix: str = "") -> list[CodeFact]:
        """Extract URL patterns from a Django URLs module."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # Find urlpatterns = [ ... ]
        urlpatterns = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "urlpatterns":
                        if isinstance(node.value, ast.List):
                            urlpatterns = node.value.elts
                        break

        if urlpatterns:
            facts.extend(self._extract_from_patterns(urlpatterns, prefix))

        return facts

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract API_ENDPOINT CodeFacts from Django URL patterns."""
        return self._extract_from_file(path)
