"""Environment variable extractor for Drift.

Extracts CONFIG_KEY facts from os.environ usage in Python source code.
Detects: os.environ["VAR"], os.environ.get("VAR"), os.getenv("VAR").
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


def _is_os_environ(node: ast.expr) -> bool:
    """Return True if node evaluates to os.environ."""
    name = _get_func_name(node)
    return name == "os.environ"


def _get_string_constant(node: ast.expr) -> str | None:
    """Extract string value from an ast.Constant node."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _get_default_value(node: ast.expr | None) -> str | None:
    """Repr a default value as a string."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return repr(node.value)
    elif isinstance(node, ast.Name):
        return node.id
    return None


@register
class EnvVarExtractor(Extractor):
    """Extract CONFIG_KEY facts from environment variable usage.

    Detects:
      os.environ["VAR"]       -> required=True
      os.environ.get("VAR")  -> required=False
      os.getenv("VAR")        -> required=False
      os.getenv("VAR", default) -> required=False, default captured
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CONFIG_KEY CodeFacts for environment variables."""
        facts: list[CodeFact] = []
        seen: set[tuple[str, str]] = set()  # (var_name, source_form) dedup

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        for node in ast.walk(tree):
            # Pattern 1: os.environ["VAR"] (Subscript)
            if isinstance(node, ast.Subscript):
                if _is_os_environ(node.value):
                    var_name = _get_string_constant(node.slice)
                    if var_name is None:
                        continue
                    key = (var_name, "subscript")
                    if key in seen:
                        continue
                    seen.add(key)
                    facts.append(
                        CodeFact(
                            name=var_name,
                            kind=FactKind.CONFIG_KEY,
                            source_file=path,
                            line_number=node.lineno or 0,
                            metadata={
                                "env_var": var_name,
                                "required": True,
                                "source": "os.environ[...]",
                            },
                        )
                    )
                continue

            # Pattern 2 & 3: os.environ.get("VAR") or os.getenv("VAR") (Call)
            if isinstance(node, ast.Call):
                func_name = _get_func_name(node.func)
                if func_name in ("os.environ.get", "os.getenv"):
                    var_name = _get_string_constant(node.args[0]) if node.args else None
                    if var_name is None:
                        continue
                    # Optional default from second arg
                    default_val = None
                    if len(node.args) >= 2:
                        default_val = _get_default_value(node.args[1])
                    elif node.keywords:
                        # os.environ.get("VAR", default=...)
                        for kw in node.keywords:
                            if kw.arg == "default":
                                default_val = _get_default_value(kw.value)
                                break

                    key = (var_name, func_name)
                    if key in seen:
                        continue
                    seen.add(key)
                    facts.append(
                        CodeFact(
                            name=var_name,
                            kind=FactKind.CONFIG_KEY,
                            source_file=path,
                            line_number=node.lineno or 0,
                            metadata={
                                "env_var": var_name,
                                "required": False,
                                "default": default_val,
                                "source": func_name,
                            },
                        )
                    )
                continue

        return facts
