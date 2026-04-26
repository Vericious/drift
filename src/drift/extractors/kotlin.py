"""Kotlin extractor for Drift — DRIFT-235.

Extracts Kotlin declarations from .kt and .kts files:
- fun declarations (top-level and extension functions)
- class declarations (class, data class, interface, abstract class, sealed class)
- object declarations (singleton objects)
- companion objects inside classes
- enum classes

Handles doc comments:
- KDoc comments (/** */) attach to the following item

Produces CodeFact objects with metadata['lang']='kotlin'.
"""

import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


@register
class KotlinExtractor(Extractor):
    """Extractor for Kotlin source files."""

    _FUN_RE = re.compile(
        r"(?:(?:protected|private|public|internal)\s+)?"
        r"(?:(?:companion\s+)?object\s+)?"
        r"(?:abstract\s+|open\s+|override\s+|inline\s+|infix\s+|operator\s+|suspend\s+|tailrec\s+)*"
        r"fun\s+(?:<\w[^>]*>\s+)?"
        r"(?:([A-Za-z_]\w*)\.)?"  # optional receiver (extension function)
        r"([A-Za-z_]\w*)"  # function name
        r"\s*\(([^)]*)\)"  # parameters
        r"(?:\s*:\s*([^({\n=]+))?",  # optional return type (stop before = or { or \n)
        re.MULTILINE,
    )

    _CLASS_RE = re.compile(
        r"(?:(?:protected|private|public|internal)\s+)?"
        r"(?:(?:abstract|open|data|sealed)\s+)*"
        r"(?<!enum\s)class\s+([A-Za-z_]\w*)"
        r"(?:\s*<[^>]+>)?"
        r"(?:"
        r"\s*\(([^)]*)\)\s*(?::|\{|\n)"  # class (params) followed by : or { or newline
        r"|"
        r"\s*:\s*[^({\n]+[{]"  # class with inheritance then body
        r"|"
        r"\s*\{)"  # class with body (opening brace on same line)
        r"",
        re.MULTILINE,
    )

    _INTERFACE_RE = re.compile(
        r"interface\s+([A-Za-z_]\w*)"
        r"(?:\s*<[^>]+>)?"
        r"(?:\s*:\s*[^({]+)?"
        r"\s*\{",
        re.MULTILINE,
    )

    _OBJECT_RE = re.compile(
        r"(?:(?:protected|private|public|internal)\s+)?"
        r"object\s+([A-Za-z_]\w*)"
        r"\s*(?::\s*[^({]+)?"
        r"\s*\{",
        re.MULTILINE,
    )

    _ENUM_RE = re.compile(
        r"(?:(?:protected|private|public|internal)\s+)?"
        r"(?:enum\s+class\s+|enum\s+)"
        r"([A-Za-z_]\w*)"
        r"(?:\s*<[^>]+>)?"
        r"(?:\s*:\s*[^({]+)?"
        r"\s*\{",
        re.MULTILINE,
    )

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in (".kt", ".kts")

    def extract(self, file_path: Path) -> list[CodeFact]:
        source = file_path.read_text()
        return self._extract_facts(source, file_path)

    def _extract_facts(self, source: str, file_path: Path) -> list[CodeFact]:
        facts: list[CodeFact] = []
        facts.extend(self._extract_functions(source, file_path))
        facts.extend(self._extract_classes(source, file_path))
        facts.extend(self._extract_interfaces(source, file_path))
        facts.extend(self._extract_objects(source, file_path))
        facts.extend(self._extract_enums(source, file_path))
        return facts

    # ------------------------------------------------------------------
    # Top-level extraction
    # ------------------------------------------------------------------

    def _extract_functions(self, source: str, file_path: Path) -> list[CodeFact]:
        facts: list[CodeFact] = []
        for match in self._FUN_RE.finditer(source):
            receiver = match.group(1)  # e.g. "User" for extension functions
            name = match.group(2)
            params_str = match.group(3) or ""
            return_type = match.group(4)

            line_number = source[: match.start()].count("\n") + 1

            # Skip if inside a class body (we handle methods there)
            prefix = source[: match.start()]
            brace_depth = prefix.count("{") - prefix.count("}")
            if brace_depth > 0:
                continue

            params = self._parse_params(params_str)

            metadata: dict[str, Any] = {"lang": "kotlin", "kotlin_kind": "function"}
            if receiver:
                metadata["receiver"] = receiver
                metadata["kotlin_kind"] = "extension_function"

            # Collect leading KDoc
            docstring = self._collect_leading_kdoc(source, match.start())
            if docstring:
                metadata["docstring"] = docstring

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.FUNCTION,
                    source_file=file_path,
                    line_number=line_number,
                    parameters=params,
                    return_type=return_type.strip() if return_type else None,
                    docstring=docstring,
                    metadata=metadata,
                )
            )
        return facts

    def _extract_classes(
        self, source: str, file_path: Path
    ) -> list[CodeFact]:
        facts: list[CodeFact] = []
        for match in self._CLASS_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1

            prefix = source[: match.start()]
            brace_depth = prefix.count("{") - prefix.count("}")
            if brace_depth > 0:
                continue

            modifiers = match.group(0)  # full match text
            is_data = "data" in modifiers
            is_sealed = "sealed" in modifiers
            is_abstract = "abstract" in modifiers
            is_open = "open" in modifiers

            # Parse constructor params if present (group 2)
            params_str = match.group(2) or ""
            params = self._parse_params(params_str) if params_str.strip() else []

            metadata: dict[str, Any] = {"lang": "kotlin", "kotlin_kind": "class"}
            if is_data:
                metadata["kotlin_kind"] = "data_class"
            elif is_sealed:
                metadata["kotlin_kind"] = "sealed_class"
            elif is_abstract:
                metadata["kotlin_kind"] = "abstract_class"
            elif is_open:
                metadata["kotlin_kind"] = "open_class"

            docstring = self._collect_leading_kdoc(source, match.start())
            if docstring:
                metadata["docstring"] = docstring

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,
                    source_file=file_path,
                    line_number=line_number,
                    parameters=params,
                    docstring=docstring,
                    metadata=metadata,
                )
            )
        return facts

    def _extract_interfaces(
        self, source: str, file_path: Path
    ) -> list[CodeFact]:
        facts: list[CodeFact] = []
        for match in self._INTERFACE_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1

            prefix = source[: match.start()]
            brace_depth = prefix.count("{") - prefix.count("}")
            if brace_depth > 0:
                continue

            metadata: dict[str, Any] = {"lang": "kotlin", "kotlin_kind": "interface"}

            docstring = self._collect_leading_kdoc(source, match.start())
            if docstring:
                metadata["docstring"] = docstring

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,
                    source_file=file_path,
                    line_number=line_number,
                    docstring=docstring,
                    metadata=metadata,
                )
            )
        return facts

    def _extract_objects(self, source: str, file_path: Path) -> list[CodeFact]:
        facts: list[CodeFact] = []
        for match in self._OBJECT_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1

            prefix = source[: match.start()]
            brace_depth = prefix.count("{") - prefix.count("}")
            if brace_depth > 0:
                continue

            metadata: dict[str, Any] = {"lang": "kotlin", "kotlin_kind": "object"}

            docstring = self._collect_leading_kdoc(source, match.start())
            if docstring:
                metadata["docstring"] = docstring

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,
                    source_file=file_path,
                    line_number=line_number,
                    docstring=docstring,
                    metadata=metadata,
                )
            )
        return facts

    def _extract_enums(self, source: str, file_path: Path) -> list[CodeFact]:
        facts: list[CodeFact] = []
        for match in self._ENUM_RE.finditer(source):
            name = match.group(1)
            line_number = source[: match.start()].count("\n") + 1

            prefix = source[: match.start()]
            brace_depth = prefix.count("{") - prefix.count("}")
            if brace_depth > 0:
                continue

            full_match = match.group(0)
            is_enum_class = "enum class" in full_match

            metadata: dict[str, Any] = {"lang": "kotlin", "kotlin_kind": "enum_class"}
            if not is_enum_class:
                metadata["kotlin_kind"] = "enum"

            docstring = self._collect_leading_kdoc(source, match.start())
            if docstring:
                metadata["docstring"] = docstring

            facts.append(
                CodeFact(
                    name=name,
                    kind=FactKind.CLASS,
                    source_file=file_path,
                    line_number=line_number,
                    docstring=docstring,
                    metadata=metadata,
                )
            )
        return facts

    # ------------------------------------------------------------------
    # Parameter parsing
    # ------------------------------------------------------------------

    def _parse_params(self, params_str: str) -> list[Parameter]:
        params: list[Parameter] = []
        if not params_str.strip():
            return params
        parts = self._split_params(params_str)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Format: (val|var)? name: Type(= default)?
            mv = re.match(
                r"(?:(?:val|var)\s+)?([A-Za-z_]\w*)\s*:\s*(.+)",
                part,
            )
            if mv:
                name = mv.group(1)
                type_rest = mv.group(2).strip()
                # Split off default value if present
                default = None
                if "=" in type_rest:
                    type_part, default = type_rest.split("=", 1)
                    type_part = type_part.strip()
                    default = default.strip()
                else:
                    type_part = type_rest
                params.append(
                    Parameter(name=name, type_annotation=type_part, default=default)
                )
        return params

    def _split_params(self, params_str: str) -> list[str]:
        result = []
        depth = 0
        current = ""
        for c in params_str:
            if c in "<(":
                depth += 1
                current += c
            elif c in ">)":
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

    # ------------------------------------------------------------------
    # KDoc collection
    # ------------------------------------------------------------------

    def _collect_leading_kdoc(self, source: str, decl_start: int) -> str | None:
        """Collect KDoc (/** */) immediately preceding the declaration at decl_start."""
        # Find the start of the line containing the declaration
        line_start = source.rfind("\n", 0, decl_start) + 1
        prefix = source[:decl_start]

        # Find the last non-whitespace character before line_start
        non_ws_end = len(prefix) - 1
        while non_ws_end >= 0 and prefix[non_ws_end] in " \t":
            non_ws_end -= 1

        if non_ws_end < 0 or prefix[non_ws_end] != "/":
            return None

        # Walk backward to find /**
        kdoc_start = non_ws_end
        while kdoc_start >= 2 and source[kdoc_start - 2 : kdoc_start + 1] != "/**":
            kdoc_start -= 1

        if kdoc_start < 2 or source[kdoc_start - 2 : kdoc_start + 1] != "/**":
            return None

        # Extract the KDoc block
        kdoc_end = source.find("*/", kdoc_start)
        if kdoc_end == -1:
            return None

        # Get all lines of the kdoc
        kdoc_body = source[kdoc_start + 3 : kdoc_end]
        lines = kdoc_body.split("\n")

        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Remove leading * for each line
            if stripped.startswith("*"):
                stripped = stripped[1:].strip()
            if stripped:
                cleaned_lines.append(stripped)

        return " ".join(cleaned_lines) if cleaned_lines else None
