"""TypeScript interface, type, and enum extractor for Drift.

Extracts TypeScript type declarations from .ts and .tsx files:
- interface Foo { ... } — interface declarations
- type Foo = { ... } — type alias declarations
- enum Foo { ... } — enum declarations

Produces CodeFact objects with metadata['ts_kind'] indicating the type.
"""

import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind


# Match interface declarations: interface Foo { ... }
_INTERFACE_RE = re.compile(
    r"(?:export\s+)?interface\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:extends\s+([A-Za-z_$][A-Za-z0-9_$]*))?\s*\{",
    re.MULTILINE,
)

# Match type alias declarations: type Foo = { ... } or type Foo = ...
_TYPE_ALIAS_RE = re.compile(
    r"(?:export\s+)?type\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:\{[^}]*\}|[^;]+);",
    re.MULTILINE,
)

# Match enum declarations: enum Foo { ... } or const enum Foo { ... }
_ENUM_RE = re.compile(
    r"(?:const\s+)?enum\s+([A-Za-z_$][A-Za-z_$]*)\s*\{",
    re.MULTILINE,
)

# Match interface/type body properties: name?: type, name: type, readonly name: type
_PROPERTY_RE = re.compile(
    r"(?:readonly\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)\??\s*:\s*([^,;\n]+)",
)

# Match function signature in interface/type: name(params): returnType
_SIGNATURE_RE = re.compile(
    r"(?:async\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)\s*:\s*([^;{]+)",
)


def _parse_parameters(params_str: str) -> list[tuple[str, str, str | None]]:
    """Parse a parameter string into (name, type_annotation, default) tuples."""
    parameters = []
    if not params_str.strip():
        return parameters
    for param in params_str.split(","):
        param = param.strip()
        if not param:
            continue
        # name?: type or name: type or name = default
        m = re.match(r"(?:([a-zA-Z_$][a-zA-Z0-9_$]*?)\??)\s*:\s*(.+)", param)
        if m:
            name = m.group(1)
            type_annotation = m.group(2).strip()
            default = None
        else:
            name = param
            type_annotation = "any"
            default = None
        parameters.append((name, type_annotation, default))
    return parameters


@register
class TypeScriptExtractor(Extractor):
    """Extract TypeScript interface, type, and enum declarations."""

    def can_handle(self, path: Path) -> bool:
        """Return True if this extractor handles TypeScript files."""
        return path.suffix.lower() in (".ts", ".tsx")

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract all TypeScript type declarations from a file."""
        source = path.read_text()
        facts: list[CodeFact] = []

        # Extract interfaces
        for match in _INTERFACE_RE.finditer(source):
            name = match.group(1)
            extends = match.group(2)
            line_number = source[: match.start()].count("\n") + 1

            # Try to extract properties from the interface body
            start = match.end()
            brace_depth = 1
            end = start
            for i, c in enumerate(source[start:], start):
                if c == "{":
                    brace_depth += 1
                elif c == "}":
                    brace_depth -= 1
                    if brace_depth == 0:
                        end = i
                        break
            body = source[start:end]

            properties = []
            parameters = []
            for prop_match in _PROPERTY_RE.finditer(body):
                prop_name = prop_match.group(1)
                prop_type = prop_match.group(2).strip()
                properties.append(prop_name)
                parameters.append((prop_name, prop_type, None))

            metadata: dict[str, Any] = {
                "ts_kind": "TS_INTERFACE",
                "properties": properties,
            }
            if extends:
                metadata["extends"] = extends

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.FUNCTION,  # Closest existing kind
                    source_file=path,
                    line_number=line_number,
                    parameters=[
                        {"name": n, "type_annotation": t, "default": d, "kind": "positional"}
                        for n, t, d in parameters
                    ],
                    metadata=metadata,
                )
            )

        # Extract type aliases
        for match in _TYPE_ALIAS_RE.finditer(source):
            name = match.group(1)
            type_expr = match.group(0)
            line_number = source[: match.start()].count("\n") + 1

            # Check if it's an object type ({ ... })
            is_object = "{" in type_expr
            properties = []
            parameters = []

            if is_object:
                # Extract properties from object type
                obj_start = type_expr.index("{")
                obj_end = type_expr.rindex("}")
                obj_body = type_expr[obj_start + 1 : obj_end]
                for prop_match in _PROPERTY_RE.finditer(obj_body):
                    prop_name = prop_match.group(1)
                    prop_type = prop_match.group(2).strip()
                    properties.append(prop_name)
                    parameters.append((prop_name, prop_type, None))

            metadata = {
                "ts_kind": "TS_TYPE",
                "type_expression": type_expr[:50],
                "properties": properties,
            }

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.FUNCTION,  # Closest existing kind
                    source_file=path,
                    line_number=line_number,
                    parameters=[
                        {"name": n, "type_annotation": t, "default": d, "kind": "positional"}
                        for n, t, d in parameters
                    ],
                    metadata=metadata,
                )
            )

        # Extract enums
        for match in _ENUM_RE.finditer(source):
            name = match.group(1)
            is_const = "const" in source[max(0, match.start() - 12) : match.start()].lower()
            line_number = source[: match.start()].count("\n") + 1

            # Try to extract enum members
            start = match.end()
            brace_depth = 1
            end = start
            for i, c in enumerate(source[start:], start):
                if c == "{":
                    brace_depth += 1
                elif c == "}":
                    brace_depth -= 1
                    if brace_depth == 0:
                        end = i
                        break
            body = source[start:end]

            members = []
            parameters = []
            for i, line in enumerate(body.split("\n")):
                line = line.strip().rstrip(",").strip()
                if not line or line == "}":
                    continue
                if "=" in line:
                    name_part, value_part = line.split("=", 1)
                    name_part = name_part.strip()
                    value_part = value_part.strip()
                else:
                    name_part = line
                    value_part = str(i)
                members.append(name_part)
                parameters.append((name_part, value_part, None))

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.FUNCTION,  # Closest existing kind
                    source_file=path,
                    line_number=line_number,
                    parameters=[
                        {"name": n, "type_annotation": t, "default": d, "kind": "positional"}
                        for n, t, d in parameters
                    ],
                    metadata={
                        "ts_kind": "TS_ENUM",
                        "members": members,
                        "is_const": is_const,
                    },
                )
            )

        return facts
