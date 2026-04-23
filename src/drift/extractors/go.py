"""Go extractor for Drift.

Extracts Go declarations from .go files:
- func declarations (top-level and methods with receiver)
- type declarations (struct, interface, etc.)
- const and var declarations

Produces CodeFact objects with metadata['lang']='go'.
"""

import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter

# Match function declarations: func foo() { ... } or func (r *Receiver) Foo() { ... }
# This matches BOTH top-level funcs and methods
_FUNC_RE = re.compile(
    r"func\s+(?:(?:\(([^)]+)\)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*)?\(([^)]*)\)\s*(?:(.*))?\{",
    re.MULTILINE,
)

# Match type declarations: type Foo interface { ... } or type Foo struct { ... }
_TYPE_RE = re.compile(
    r"type\s+([A-Za-z_][A-Za-z0-9_]*)\s+(interface|struct|map|chan|func)\s*\{",
    re.MULTILINE,
)

# Match const/var group: const ( ... ) or var ( ... )
_GROUP_RE = re.compile(
    r"(?:const|var)\s*\(([^)]+)\)",
    re.MULTILINE,
)

# Match single const/var: const foo = 1 or var bar int
_SINGLE_DECL_RE = re.compile(
    r"(?:const|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*([^;\n]+))?",
    re.MULTILINE,
)

# Match struct field: FieldName Type `tags`
_FIELD_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_\*\.]{1,50}(?:\[[^\]]+\])*)",
    re.MULTILINE,
)

# Match interface method: MethodName(args) returnType
_INTERFACE_METHOD_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*([^(]+)",
    re.MULTILINE,
)


def _get_body_end(source: str, start: int) -> int:
    """Find the end of a brace-delimited block starting at `start` (after the opening brace)."""
    depth = 1
    for i, c in enumerate(source[start:], start):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i
    return start


def _parse_parameters(params_str: str) -> list[tuple[str, str | None, bool]]:
    """Parse Go function parameter list into (name, type_annotation, is_optional) tuples."""
    parameters = []
    if not params_str.strip():
        return parameters

    parts = params_str.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Handle named parameters: name Type or name *Type
        # Handle anonymous: Type (when parameter has no name)
        tokens = part.split()
        if len(tokens) == 1:
            # Just a type (anonymous parameter)
            name = ""
            type_annotation = tokens[0]
        elif len(tokens) == 2:
            name, type_annotation = tokens
        elif len(tokens) > 2:
            # Could be "name *Type" or multiple tokens for type
            # Last token is type, preceding is name (or all but last for complex type)
            name = tokens[0]
            type_annotation = " ".join(tokens[1:])
        else:
            name = ""
            type_annotation = part

        is_optional = False
        parameters.append((name, type_annotation, is_optional))
    return parameters


def _extract_struct_fields(body: str) -> list[tuple[str, str | None, bool, bool]]:
    """Extract fields from a struct body."""
    properties = []
    for match in _FIELD_RE.finditer(body):
        field_name = match.group(1)
        field_type = match.group(2).strip()
        is_readonly = False  # Go doesn't have readonly fields
        is_optional = False
        properties.append((field_name, field_type, is_optional, is_readonly))
    return properties


def _extract_interface_methods(body: str) -> list[tuple[str, list[tuple], str | None]]:
    """Extract method signatures from an interface body."""
    methods = []
    for match in _INTERFACE_METHOD_RE.finditer(body):
        method_name = match.group(1)
        params_str = match.group(2)
        return_type = match.group(3).strip() if match.group(3) else None

        # Skip fields that look like struct fields (have a type field before this pattern)
        params = _parse_parameters(params_str)
        methods.append((method_name, params, return_type))
    return methods


@register
class GoExtractor(Extractor):
    """Extract Go function, type (struct/interface), const, and var declarations."""

    def can_handle(self, path: Path) -> bool:
        """Return True if this extractor handles Go files."""
        return path.suffix.lower() == ".go"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract all Go declarations from a file."""
        source = path.read_text()
        facts: list[CodeFact] = []

        facts.extend(self._extract_functions(source, path))
        facts.extend(self._extract_types(source, path))
        facts.extend(self._extract_declarations(source, path))

        return facts

    def _extract_functions(self, source: str, path: Path) -> list[CodeFact]:
        """Extract func declarations (top-level and methods)."""
        facts: list[CodeFact] = []

        for match in _FUNC_RE.finditer(source):
            receiver = match.group(1)  # e.g. "*User" or "u User"
            name = match.group(2)
            params_str = match.group(3) or ""
            rest = match.group(4) or ""

            line_number = source[: match.start()].count("\n") + 1

            # Determine if this is a method (has receiver) or top-level func
            is_method = receiver is not None

            # Try to get return type from rest
            return_type = None
            if "->" in rest:
                # This is for completeness; Go uses -> nowhere in source
                pass
            # Look for return type after the closing paren
            func_start = match.end()
            # Find the opening brace of this function
            brace_pos = source.find("{", func_start)
            if brace_pos != -1:
                # The return type (if any) would be between ) and {
                between = source[func_start:brace_pos].strip()
                if between:
                    return_type = between

            # Also check if there's a literal `-> ` in the pattern
            # (we'll handle this more robustly below)

            params = _parse_parameters(params_str)

            metadata: dict[str, Any] = {"lang": "go"}
            if is_method:
                metadata["receiver"] = receiver
                metadata["kind"] = "method"
            else:
                metadata["kind"] = "function"

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.FUNCTION,
                    source_file=path,
                    line_number=line_number,
                    return_type=return_type,
                    parameters=[
                        Parameter(name=n, type_annotation=t, kind="positional", is_optional=is_opt)
                        for n, t, is_opt in params
                    ],
                    metadata=metadata,
                )
            )
        return facts

    def _extract_types(self, source: str, path: Path) -> list[CodeFact]:
        """Extract type declarations (struct, interface, etc.)."""
        facts: list[CodeFact] = []

        for match in _TYPE_RE.finditer(source):
            type_name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1

            # Find the type body
            start = match.end()
            end = _get_body_end(source, start)
            body = source[start:end]

            # Determine if it's a struct or interface
            type_keyword = match.group(2)
            is_struct = type_keyword == "struct"
            is_interface = type_keyword == "interface"

            if is_struct:
                properties = _extract_struct_fields(body)
                facts.append(
                    CodeFact(
                        name=type_name,
                        kind=FactKind.CLASS,
                        source_file=path,
                        line_number=line_number,
                        parameters=[
                            Parameter(name=n, type_annotation=t, kind="field", is_optional=is_opt, is_readonly=is_ro)
                            for n, t, is_opt, is_ro in properties
                        ],
                        metadata={
                            "lang": "go",
                            "go_kind": "struct",
                            "properties": [n for n, _, _, _ in properties],
                        },
                    )
                )
            elif is_interface:
                methods = _extract_interface_methods(body)
                facts.append(
                    CodeFact(
                        name=type_name,
                        kind=FactKind.CLASS,
                        source_file=path,
                        line_number=line_number,
                        parameters=[
                            Parameter(
                                name=method_name,
                                type_annotation="(" + ", ".join(p[1] or "" for p in params) + ")",
                                kind="method",
                            )
                            for method_name, params, _ in methods
                        ],
                        metadata={
                            "lang": "go",
                            "go_kind": "interface",
                            "methods": [m[0] for m in methods],
                        },
                    )
                )
            else:
                # Other type (map, chan, func) - just record the name
                facts.append(
                    CodeFact(
                        name=type_name,
                        kind=FactKind.CLASS,
                        source_file=path,
                        line_number=line_number,
                        metadata={
                            "lang": "go",
                            "go_kind": "other",
                        },
                    )
                )
        return facts

    def _extract_declarations(self, source: str, path: Path) -> list[CodeFact]:
        """Extract const and var declarations (top-level only)."""
        facts: list[CodeFact] = []

        # Skip declarations inside functions
        for match in _SINGLE_DECL_RE.finditer(source):
            name = match.group(1)
            value = match.group(2)
            line_number = source[: match.start()].count("\n") + 1

            # Check if inside a function (brace depth > 0 means inside a func body)
            prefix = source[: match.start()]
            brace_depth = prefix.count("{") - prefix.count("}")
            if brace_depth > 0:
                continue  # Skip declarations inside functions

            # Look for const or var keyword before this declaration
            # Search backward from match start to find the keyword
            # Use rfind with end=match.end() to include the match position
            search_end = min(match.end() + 10, len(source))  # small buffer after match
            const_pos = source.rfind("const", 0, search_end)
            var_pos = source.rfind("var", 0, search_end)
            go_kind = "var" if var_pos > const_pos else "const"

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.FUNCTION,  # No specific kind for const/var
                    source_file=path,
                    line_number=line_number,
                    metadata={
                        "lang": "go",
                        "go_kind": go_kind,
                        "value": value.strip() if value else None,
                    },
                )
            )

        return facts
