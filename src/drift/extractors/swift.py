"""Swift extractor for Drift.

Extracts Swift declarations from .swift files:
- struct, class, enum, protocol declarations
- func declarations
- property declarations

Produces CodeFact objects with metadata['lang']='swift'.
"""

import re
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter

# Match struct declarations: struct Foo { ... }
_STRUCT_RE = re.compile(
    r"(?:public |internal |open |fileprivate |private )?struct\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]+>)?\s*\{",
    re.MULTILINE,
)

# Match class declarations: class Foo { ... }
_CLASS_RE = re.compile(
    r"(?:public |internal |open |fileprivate |private )?class\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]+>)?\s*(?::\s*[^{]+)?\s*\{",
    re.MULTILINE,
)

# Match enum declarations: enum Foo { ... }
_ENUM_RE = re.compile(
    r"(?:public |internal |open |fileprivate |private )?enum\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]+>)?\s*(?::\s*[^{]+)?\s*\{",
    re.MULTILINE,
)

# Match protocol declarations: protocol Foo { ... }
_PROTOCOL_RE = re.compile(
    r"(?:public |internal |open |fileprivate |private )?protocol\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*[^{]+)?\s*\{",
    re.MULTILINE,
)

# Match extension declarations: extension Foo { ... }
_EXTENSION_RE = re.compile(
    r"(?:public |internal |open |fileprivate |private )?extension\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*[^{]+)?\s*\{",
    re.MULTILINE,
)

# Match func declarations: func foo() { ... } or func foo() -> Type { ... }
# Handles instance, static, and class methods
_FUNC_RE = re.compile(
    r"(?:public |internal |open |fileprivate |private )?(?:static |class |convenience )?func\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:<[^>]+>)?\s*\(([^)]*)\)\s*(?:->\s*([^{(\n]+))?",
    re.MULTILINE,
)

# Match property declarations: var foo: Type or let foo: Type
_PROPERTY_RE = re.compile(
    r"(?:public |internal |open |fileprivate |private )?(?:static |class )?(?:var |let)\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*([^=;\n]+))?",
    re.MULTILINE,
)


def _parse_parameters(params_str: str) -> list[tuple[str, str | None, bool]]:
    """Parse Swift parameter list into (name, type_annotation, is_optional) tuples.

    Swift params look like:  label name: Type
    Or: name: Type
    Or: _ name: Type
    """
    parameters = []
    if not params_str.strip():
        return parameters

    # Split on commas, but be careful inside generic brackets
    parts = _split_params(params_str)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Pattern: external_label name: Type or just name: Type or _: Type
        m = re.match(r"(?:([A-Za-z_][A-Za-z0-9_]*)\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)", part)
        if m:
            # external_label or _ for the first group, name for the second
            name = m.group(2)
            type_annotation = m.group(3).strip()
            is_optional = type_annotation.endswith("?")
        else:
            name = part.split(":")[0].strip()
            type_annotation = None
            is_optional = False
        parameters.append((name, type_annotation, is_optional))
    return parameters


def _split_params(params_str: str) -> list[str]:
    """Split parameter string on commas, respecting angle brackets."""
    result = []
    depth = 0
    current = ""
    for c in params_str:
        if c == "<":
            depth += 1
            current += c
        elif c == ">":
            depth -= 1
            current += c
        elif c == "," and depth == 0:
            result.append(current)
            current = ""
        else:
            current += c
    if current.strip():
        result.append(current)
    return result


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


def _extract_properties(body: str) -> list[tuple[str, str | None, bool, bool]]:
    """Extract property declarations from a type body.

    Returns list of (name, type_annotation, is_optional, is_readonly).
    """
    properties = []
    for match in _PROPERTY_RE.finditer(body):
        name = match.group(1)
        type_annotation = match.group(2)
        if type_annotation:
            type_annotation = type_annotation.strip()
            if type_annotation.endswith("?"):
                is_optional = True
                type_annotation = type_annotation[:-1].strip()
            else:
                is_optional = False
        else:
            is_optional = False
        is_readonly = "let " in match.group(0)
        properties.append((name, type_annotation, is_optional, is_readonly))
    return properties


def _extract_functions(body: str) -> list[tuple[str, list[tuple], str | None]]:
    """Extract function declarations from a type body.

    Returns list of (name, parameters, return_type).
    """
    functions = []
    seen_funcs: set[str] = set()
    for match in _FUNC_RE.finditer(body):
        name = match.group(1)
        params_str = match.group(2) or ""
        return_type = match.group(3)
        if return_type:
            return_type = return_type.strip()

        if name in seen_funcs:
            continue
        seen_funcs.add(name)

        params = _parse_parameters(params_str)
        functions.append((name, params, return_type))
    return functions


@register
class SwiftExtractor(Extractor):
    """Extract Swift struct, class, enum, protocol, func, and property declarations."""

    def can_handle(self, path: Path) -> bool:
        """Return True if this extractor handles Swift files."""
        return path.suffix.lower() == ".swift"

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract all Swift declarations from a file."""
        source = path.read_text()
        facts: list[CodeFact] = []

        facts.extend(self._extract_structs(source, path))
        facts.extend(self._extract_classes(source, path))
        facts.extend(self._extract_enums(source, path))
        facts.extend(self._extract_protocols(source, path))
        facts.extend(self._extract_extensions(source, path))
        facts.extend(self._extract_standalone_functions(source, path))

        return facts

    def _extract_structs(self, source: str, path: Path) -> list[CodeFact]:
        """Extract struct declarations."""
        facts: list[CodeFact] = []
        for match in _STRUCT_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1
            start = match.end()
            end = _get_body_end(source, start)
            body = source[start:end]

            properties = _extract_properties(body)
            functions = _extract_functions(body)

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,  # Swift structs map closest to CLASS
                    source_file=path,
                    line_number=line_number,
                    parameters=[
                        Parameter(name=n, type_annotation=t, kind="property", is_optional=is_opt, is_readonly=is_ro)
                        for n, t, is_opt, is_ro in properties
                    ],
                    metadata={
                        "lang": "swift",
                        "swift_kind": "struct",
                        "properties": [n for n, _, _, _ in properties],
                        "methods": [n for n, _, _ in functions],
                    },
                )
            )
        return facts

    def _extract_classes(self, source: str, path: Path) -> list[CodeFact]:
        """Extract class declarations."""
        facts: list[CodeFact] = []
        for match in _CLASS_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1
            start = match.end()
            end = _get_body_end(source, start)
            body = source[start:end]

            properties = _extract_properties(body)
            functions = _extract_functions(body)

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,
                    source_file=path,
                    line_number=line_number,
                    parameters=[
                        Parameter(name=n, type_annotation=t, kind="property", is_optional=is_opt, is_readonly=is_ro)
                        for n, t, is_opt, is_ro in properties
                    ],
                    metadata={
                        "lang": "swift",
                        "swift_kind": "class",
                        "properties": [n for n, _, _, _ in properties],
                        "methods": [n for n, _, _ in functions],
                    },
                )
            )
        return facts

    def _extract_enums(self, source: str, path: Path) -> list[CodeFact]:
        """Extract enum declarations."""
        facts: list[CodeFact] = []
        for match in _ENUM_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1
            start = match.end()
            end = _get_body_end(source, start)
            body = source[start:end]

            # Extract enum cases (members)
            members = []
            parameters = []
            member_pattern = re.compile(
                r"case\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:\(([^)]+)\))?"
            )
            for m in member_pattern.finditer(body):
                member_name = m.group(1)
                raw_value = m.group(2)
                members.append(member_name)
                parameters.append((member_name, raw_value or None, None))

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,  # Swift enum maps to CLASS
                    source_file=path,
                    line_number=line_number,
                    parameters=[
                        Parameter(name=n, type_annotation=v, default=d, kind="positional")
                        for n, v, d in parameters
                    ],
                    metadata={
                        "lang": "swift",
                        "swift_kind": "enum",
                        "members": members,
                    },
                )
            )
        return facts

    def _extract_protocols(self, source: str, path: Path) -> list[CodeFact]:
        """Extract protocol declarations."""
        facts: list[CodeFact] = []
        for match in _PROTOCOL_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1
            start = match.end()
            end = _get_body_end(source, start)
            body = source[start:end]

            properties = _extract_properties(body)
            functions = _extract_functions(body)

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,
                    source_file=path,
                    line_number=line_number,
                    parameters=[
                        Parameter(name=n, type_annotation=t, kind="property", is_optional=is_opt, is_readonly=is_ro)
                        for n, t, is_opt, is_ro in properties
                    ],
                    metadata={
                        "lang": "swift",
                        "swift_kind": "protocol",
                        "properties": [n for n, _, _, _ in properties],
                        "methods": [n for n, _, _ in functions],
                    },
                )
            )
        return facts

    def _extract_extensions(self, source: str, path: Path) -> list[CodeFact]:
        """Extract extension declarations."""
        facts: list[CodeFact] = []
        for match in _EXTENSION_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1
            start = match.end()
            end = _get_body_end(source, start)
            body = source[start:end]

            # Extract any added properties and functions
            properties = _extract_properties(body)
            functions = _extract_functions(body)

            # Collect inherited protocols if any
            inherits = []
            inherits_match = re.search(r":\s*([^{]+)\s*\{", match.group(0))
            if inherits_match:
                for prot in inherits_match.group(1).split(","):
                    prot = prot.strip()
                    if prot:
                        inherits.append(prot)

            fact = CodeFact(
                name=name,
                kind=FactKind.CLASS,
                source_file=path,
                line_number=line_number,
                parameters=[
                    Parameter(name=n, type_annotation=t, kind="property", is_optional=is_opt, is_readonly=is_ro)
                    for n, t, is_opt, is_ro in properties
                ],
                metadata={
                    "lang": "swift",
                    "swift_kind": "extension",
                    "extended_type": name,
                    "properties": [n for n, _, _, _ in properties],
                    "methods": [n for n, _, _ in functions],
                },
            )
            if inherits:
                fact.metadata["conforms_to"] = inherits
            facts.append(fact)
        return facts

    def _extract_standalone_functions(self, source: str, path: Path) -> list[CodeFact]:
        """Extract top-level func declarations."""
        facts: list[CodeFact] = []
        # Only match funcs that appear at the top level (not inside a type body)
        # We use a simpler approach: find all funcs, then filter out those inside braces
        for match in _FUNC_RE.finditer(source):
            name = match.group(1)
            params_str = match.group(2) or ""
            return_type = match.group(3)
            if return_type:
                return_type = return_type.strip()

            line_number = source[: match.start()].count("\n") + 1

            # Check if this func is inside a type body by counting brace depths
            # A top-level func should have brace_depth == 0 (outside any braces)
            # Protocols and their bodies have depth >= 1, type bodies have depth >= 2
            prefix = source[: match.start()]
            brace_depth = prefix.count("{") - prefix.count("}")
            if brace_depth != 0:
                # Inside a type body, protocol body, or closure
                continue

            params = _parse_parameters(params_str)
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
                    metadata={"lang": "swift"},
                )
            )
        return facts
