"""Decorator extractor for Drift.

Detects decorator usage patterns in Python source code.
"""

import ast
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind


# Well-known decorator patterns that indicate behavior-changing decorators
KNOWN_DECORATORS: dict[str, dict[str, str]] = {
    "app.route": {"category": "routing", "framework": "Flask"},
    "route": {"category": "routing", "framework": "Flask"},
    "login_required": {"category": "auth", "framework": "common"},
    "requires_auth": {"category": "auth", "framework": "common"},
    "authenticated": {"category": "auth", "framework": "common"},
    "cache": {"category": "caching", "framework": "common"},
    "cached": {"category": "caching", "framework": "common"},
    "lru_cache": {"category": "caching", "framework": "common"},
    "deprecated": {"category": "deprecation", "framework": "common"},
    "deprecated_msg": {"category": "deprecation", "framework": "common"},
    "retry": {"category": "resilience", "framework": "common"},
    "rate_limit": {"category": "rate_limiting", "framework": "common"},
    "admin_required": {"category": "auth", "framework": "common"},
    "permissions_required": {"category": "auth", "framework": "common"},
}


def _get_decorator_name(node: ast.expr) -> tuple[str | None, str | None]:
    """Get the dotted name and full dotted path from a decorator node.

    Returns (short_name, full_path) tuple.
    """
    if isinstance(node, ast.Name):
        return node.id, node.id
    if isinstance(node, ast.Attribute):
        parent_name, parent_path = _get_decorator_name(node.value)
        if parent_name and parent_path:
            full = f"{parent_path}.{node.attr}"
            return node.attr, full
    if isinstance(node, ast.Call):
        # Decorator with arguments: @cache(ttl=60)
        return _get_decorator_name(node.func)
    return None, None


@register
class DecoratorExtractor(Extractor):
    """Extract decorator usage patterns from Python source files.

    Detects behavior-changing decorators like @login_required, @cache,
    @app.route, @deprecated, and custom decorators with arguments.
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract decorator CodeFacts from a Python file."""
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
            if not isinstance(node, ast.FunctionDef) and not isinstance(
                node, ast.AsyncFunctionDef
            ):
                continue

            for decorator in node.decorator_list:
                fact = self._extract_decorator(decorator, node, path)
                if fact:
                    facts.append(fact)

        return facts

    def _extract_decorator(
        self, decorator: ast.expr, func: ast.FunctionDef | ast.AsyncFunctionDef, path: Path
    ) -> CodeFact | None:
        """Extract a decorator fact from a decorator node."""
        short_name, full_path = _get_decorator_name(decorator)

        if not short_name or not full_path:
            return None

        # Check if it's a known behavior-changing decorator
        info = KNOWN_DECORATORS.get(full_path) or KNOWN_DECORATORS.get(short_name)

        # Extract decorator arguments if it's a call
        decorator_args: dict[str, Any] = {}
        if isinstance(decorator, ast.Call):
            for kw in decorator.keywords:
                if kw.arg and kw.value:
                    val = self._extract_constant(kw.value)
                    if val is not None:
                        decorator_args[kw.arg] = val

        metadata: dict[str, Any] = {
            "decorator_name": short_name,
            "decorator_path": full_path,
            "decorated_function": func.name,
            "is_async": isinstance(func, ast.AsyncFunctionDef),
            "arguments": decorator_args if decorator_args else None,
        }

        if info:
            metadata["category"] = info["category"]
            metadata["framework"] = info["framework"]
        else:
            # Custom decorator
            metadata["category"] = "custom"
            metadata["framework"] = None

        return CodeFact(
            name=full_path,
            kind=FactKind.DECORATOR,
            source_file=path,
            line_number=decorator.lineno or 0,
            parameters=[],
            metadata=metadata,
        )

    def _extract_constant(self, node: ast.expr) -> Any:
        """Extract a constant value from an AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Tuple):
            return tuple(self._extract_constant(elt) for elt in node.elts)
        if isinstance(node, ast.List):
            return [self._extract_constant(elt) for elt in node.elts]
        return None
