"""Docstring extractor for Drift.

Detects drift between function signatures and their docstrings.
Parses Google, NumPy, and Sphinx style docstrings.
"""

import ast
import re
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import ClaimKind, DocClaim, Parameter


def extract_docstring_params(func: object) -> list[str]:
    """Extract parameter names from a function's docstring.

    Supports Google, NumPy, and Sphinx style docstrings.

    Args:
        func: A Python function object (or lambda)

    Returns:
        List of parameter names documented in the docstring.
    """
    docstring = getattr(func, "__doc__", None)
    if not docstring:
        return []

    params = _parse_docstring(docstring)
    return params


# ---------------------------------------------------------------------------
# Docstring parsing internals
# ---------------------------------------------------------------------------


def _parse_docstring(docstring: str) -> list[str]:
    """Parse a docstring and return documented parameter names.

    Handles Google, NumPy, and Sphinx styles.
    """
    if not docstring:
        return []
    docstring = docstring.strip()
    if not docstring:
        return []

    # Try each style in order
    params = _parse_google_style(docstring)
    if params is not None:
        return params

    params = _parse_numpy_style(docstring)
    if params is not None:
        return params

    params = _parse_sphinx_style(docstring)
    if params is not None:
        return params

    return []


def _parse_google_style(docstring: str) -> list[str] | None:
    """Parse Google-style Args section.

    Example:
        Args:
            foo (int): description
            bar (str, optional): description
    """
    # Find Args section
    args_match = re.search(
        r"(?:Args|Arguments|Parameters):\s*\n", docstring, re.IGNORECASE | re.MULTILINE
    )
    if not args_match:
        return None

    start = args_match.end()
    # Find next section header or end
    section_end = len(docstring)
    next_section = re.search(
        r"\n\s+(?:Returns?|Examples?|Notes?|Raises|Yields):",
        docstring[start:],
        re.IGNORECASE,
    )
    if next_section:
        section_end = start + next_section.start()

    section = docstring[start:section_end]

    params: list[str] = []
    # Match lines like "    name (type): description" or "    name: description"
    for line in section.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        # Dedent to handle indentation
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if (
            indent < 2
        ):  # Not a parameter line (needs at least some indent in Args section)
            continue

        # Google style: name (type): description OR name: description
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?\s*:", stripped)
        if match:
            params.append(match.group(1))

    return params if params else None


def _parse_numpy_style(docstring: str) -> list[str] | None:
    """Parse NumPy-style Parameters section.

    Example:
        Parameters
        ----------
        foo : int
            description
        bar : str
            description
    """
    # Find Parameters section
    params_match = re.search(
        r"Parameters\s*\n\s*(-+)\n", docstring, re.IGNORECASE | re.MULTILINE
    )
    if not params_match:
        return None

    start = params_match.end()
    # Find next section header
    section_end = len(docstring)
    next_section = re.search(
        r"\n\s+[A-Z][a-z]+.*\n\s*-+", docstring[start:], re.MULTILINE
    )
    if next_section:
        section_end = start + next_section.start()

    section = docstring[start:section_end]

    params: list[str] = []
    # NumPy style: name : type (on its own line)
    for line in section.splitlines():
        line = line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        # Look for "name : type" pattern (param name followed by colon)
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:", stripped)
        if match:
            params.append(match.group(1))

    return params if params else None


def _parse_sphinx_style(docstring: str) -> list[str] | None:
    """Parse Sphinx-style :param: declarations.

    Example:
        :param foo: description
        :type foo: int
        :param bar: description
    """
    # Find any :param: declarations
    if ":param" not in docstring and ":parameter" not in docstring:
        return None

    params: list[str] = []
    seen: set[str] = set()

    # Match :param name: or :param type name: patterns
    for match in re.finditer(r":param\s+(\w+):", docstring):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            params.append(name)

    return params if params else None


# ---------------------------------------------------------------------------
# DocstringExtractor
# ---------------------------------------------------------------------------


@register
class DocstringExtractor(Extractor):
    """Extract DocClaim objects from docstrings in Python source files.

    Compares documented parameters against actual function signatures
    and reports mismatches as DriftItems.
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Python file."""
        return path.suffix.lower() == ".py"

    def extract(self, path: Path) -> list[DocClaim]:
        """Extract DocClaims from docstrings in a Python file.

        Returns DocClaim objects for functions with docstrings that
        document parameters. These will be matched against CodeFacts
        to produce DriftItems.
        """
        claims: list[DocClaim] = []

        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):
            return claims

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return claims

        # Build parent map for nodes
        parent_map: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent

        # Walk the AST to find functions and their docstrings
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node)
                if not docstring:
                    continue

                # Get the qualified name
                qualified_name = node.name
                parent = parent_map.get(node)  # type: ignore[assignment]
                if isinstance(parent, ast.ClassDef):
                    qualified_name = f"{parent.name}.{node.name}"

                # Extract documented params
                doc_params = _parse_docstring(docstring)
                if not doc_params:
                    continue

                # Build DocClaim
                parameters = [Parameter(name=p, kind="positional") for p in doc_params]

                claim = DocClaim(
                    raw_text=docstring.strip().split("\n")[0],  # First line as raw_text
                    kind=ClaimKind.FUNCTION_SIGNATURE,
                    doc_file=path,
                    line_number=node.lineno,
                    name=qualified_name,
                    parameters=parameters,
                )
                claims.append(claim)

        return claims
