"""Deprecated decorator and docstring deprecation extractor for Drift.

Detects @deprecated decorator usage and docstring-level deprecation markers.
"""

import ast
import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind


# Patterns for docstring-level deprecation (reStructuredText)
DEPRECATED_DIRECTIVE_RE = re.compile(
    r"\.\.\s+deprecated::?\s*", re.IGNORECASE | re.MULTILINE
)
DEPRECATED_SINCE_RE = re.compile(
    r"\.\.\s+deprecated\s+since:\s*(.+?)$", re.IGNORECASE | re.MULTILINE
)


def _get_fact_name(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef, path: Path, parent: ast.ClassDef | None = None) -> str:
    """Build the fully-qualified fact name for a node.

    For methods, includes the parent class name: module.ClassName.method_name
    For standalone functions/classes: module.name
    """
    module = path.stem
    if parent is not None:
        return f"{module}.{parent.name}.{node.name}"
    return f"{module}.{node.name}"


def _parse_docstring_deprecation(docstring: str | None) -> dict[str, Any] | None:
    """Parse deprecation info from a docstring.

    Returns a dict with 'version' and 'reason' keys if deprecation found,
    or None if no deprecation directive is present.
    """
    if not docstring:
        return None

    # Check for deprecated directive (either ".. deprecated::" or ".. deprecated since:")
    has_deprecated = (
        DEPRECATED_DIRECTIVE_RE.search(docstring) is not None
        or DEPRECATED_SINCE_RE.search(docstring) is not None
    )
    if not has_deprecated:
        return None

    result: dict[str, Any] = {}

    # Try ".. deprecated since: X.Y" first
    since_match = DEPRECATED_SINCE_RE.search(docstring)
    if since_match:
        result["version"] = since_match.group(1).strip()

    # Try ".. deprecated:: X.Y" with version
    version_match = re.search(
        r"\.\.\s+deprecated::\s*(?:(\d+(?:\.\d+)*))?\s*(.*)",
        docstring,
        re.IGNORECASE
    )
    if version_match:
        version = version_match.group(1)
        reason_text = version_match.group(2).strip() if version_match.group(2) else ""
        if version and "version" not in result:
            result["version"] = version
        if reason_text:
            result["reason"] = reason_text

    # Try :version: field
    version_field = re.search(r":version:\s*(\S+)", docstring, re.IGNORECASE)
    if version_field and "version" not in result:
        result["version"] = version_field.group(1).strip()

    # Try reason/description in the body
    if "reason" not in result:
        reason_match = re.search(
            r"(?:reason|原因|description)[:\s]+(.+?)(?:\n\n|\n[^ \n]|$)",
            docstring,
            re.IGNORECASE | re.MULTILINE
        )
        if reason_match:
            result["reason"] = reason_match.group(1).strip().rstrip(".")

    return result if result else None


@register
class DeprecatedExtractor(Extractor):
    """Extract deprecation facts from Python source files.

    Detects:
    - @deprecated decorator from the `deprecated` package
    - @abc.deprecated decorator
    - Docstring-level .. deprecated:: and .. deprecated since: directives

    Output facts have kind=DEPRECATED and metadata containing:
    - version: version string if detected
    - reason: deprecation reason if detected
    - deprecation_type: "decorator" or "docstring"
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract deprecation facts from a Python file."""
        facts: list[CodeFact] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return facts

        # Walk class bodies to find methods with parent context
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Process the class itself
                class_fact = self._extract_for_node(node, path, parent_class=None)
                if class_fact:
                    facts.append(class_fact)
                # Process methods within the class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        fact = self._extract_for_node(item, path, parent_class=node)
                        if fact:
                            facts.append(fact)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Standalone function (not inside a class)
                fact = self._extract_for_node(node, path, parent_class=None)
                if fact:
                    facts.append(fact)

        return facts

    def _extract_for_node(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        path: Path,
        parent_class: ast.ClassDef | None,
    ) -> CodeFact | None:
        """Extract deprecation fact for a function, async function, or class."""
        # Check for @deprecated or @abc.deprecated decorator
        decorator_info = self._find_deprecated_decorator(node)
        if decorator_info:
            return self._make_fact(node, path, decorator_info, "decorator", parent_class)

        # Check for docstring deprecation
        docstring = ast.get_docstring(node)
        doc_info = _parse_docstring_deprecation(docstring)
        if doc_info:
            return self._make_fact(node, path, doc_info, "docstring", parent_class)

        return None

    def _find_deprecated_decorator(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> dict[str, Any] | None:
        """Find a @deprecated or @abc.deprecated decorator on a node.

        Returns a dict with 'version' and 'reason' if found, else None.
        """
        info: dict[str, Any] = {}
        found = False

        for decorator in node.decorator_list:
            name = self._get_decorator_name(decorator)
            if name in ("deprecated", "abc.deprecated"):
                found = True
                # Parse args if it's a call
                if isinstance(decorator, ast.Call):
                    # Handle positional args (the `deprecated` package uses positional 'msg')
                    for i, arg in enumerate(decorator.args):
                        val = self._extract_constant(arg)
                        if val:
                            # First positional arg is msg/reason
                            if "reason" not in info:
                                info["reason"] = str(val)
                            elif "version" not in info:
                                info["version"] = str(val)
                    for kw in decorator.keywords:
                        if kw.arg == "version":
                            info["version"] = self._extract_constant(kw.value)
                        elif kw.arg == "reason":
                            info["reason"] = self._extract_constant(kw.value)
                        elif kw.arg == "msg":
                            # The deprecated package uses 'msg' for the full message
                            msg = self._extract_constant(kw.value)
                            if msg:
                                msg_str = str(msg)
                                # Try to parse "version X.Y: description"
                                vm = re.search(
                                    r"version[:\s]+(\d+(?:\.\d+)*)", msg_str, re.IGNORECASE
                                )
                                if vm:
                                    info["version"] = vm.group(1)
                                info["reason"] = msg_str

        return info if found else None

    def _get_decorator_name(self, node: ast.expr) -> str | None:
        """Get the dotted path of a decorator."""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._get_decorator_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
        if isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return None

    def _extract_constant(self, node: ast.expr) -> Any:
        """Extract a constant value from an AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _make_fact(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
        path: Path,
        info: dict[str, Any],
        deprecation_type: str,
        parent_class: ast.ClassDef | None = None,
    ) -> CodeFact:
        """Build a DEPRECATED CodeFact."""
        fact_name = _get_fact_name(node, path, parent_class)

        metadata: dict[str, Any] = {
            "deprecation_type": deprecation_type,
        }
        if "version" in info:
            metadata["version"] = info["version"]
        if "reason" in info:
            metadata["reason"] = info["reason"]

        return CodeFact(
            name=fact_name,
            kind=FactKind.DEPRECATED,
            source_file=path,
            line_number=node.lineno or 0,
            parameters=[],
            metadata=metadata,
        )
