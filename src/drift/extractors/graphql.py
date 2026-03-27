"""GraphQL schema extractor for Drift.

Extracts facts from GraphQL Schema Definition Language (.graphql, .gql files).
Handles:
- Query, Mutation, Subscription type fields as API endpoints
- Input types and their fields
- Enum types
"""

import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


def _parse_arguments(arg_str: str) -> list[Parameter]:
    """Parse GraphQL field arguments from a string like 'id: ID!, limit: Int'."""
    params = []
    if not arg_str.strip():
        return params

    # Split on commas but respect nested structures (not expected in args but safe)
    parts = _split_args(arg_str)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # Format: name: Type! or name: Type = default
        m = re.match(r"(\w+)\s*:\s*(.+)", part)
        if m:
            name = m.group(1)
            type_info = m.group(2).strip()
            # Check for default value
            default = None
            if "=" in type_info:
                type_part, default = type_info.split("=", 1)
                type_info = type_part.strip()
                default = default.strip()
            # Check for nullability
            nullable = not type_info.endswith("!")
            type_clean = type_info.rstrip("!")
            params.append(Parameter(
                name=name,
                type_annotation=type_clean,
                default=default,
                kind="keyword",
            ))
    return params


def _split_args(arg_str: str) -> list[str]:
    """Split argument string on commas, respecting nested parens/brackets."""
    result = []
    depth = 0
    current = ""
    for ch in arg_str:
        if ch in "([{<":
            depth += 1
            current += ch
        elif ch in ")]}>":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            result.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        result.append(current)
    return result


@register
class GraphQLExtractor(Extractor):
    """Extract facts from GraphQL SDL files (.graphql, .gql)."""

    def can_handle(self, file_path: Path) -> bool:
        """Return True for .graphql and .gql files."""
        return file_path.suffix.lower() in (".graphql", ".gql")

    def extract(self, file_path: Path) -> list[Any]:
        """Extract facts from a GraphQL schema file."""
        content = file_path.read_text(encoding="utf-8")
        facts = []

        # Extract type definitions
        facts.extend(self._extract_operation_types(content, file_path))
        facts.extend(self._extract_input_types(content, file_path))
        facts.extend(self._extract_enum_types(content, file_path))

        return facts

    def _extract_operation_types(self, content: str, source_file: Path) -> list[Any]:
        """Extract Query, Mutation, Subscription field definitions as API endpoints."""
        facts = []

        for op_type in ("Query", "Mutation", "Subscription"):
            # Find the type block: type Query { ... }
            # Use a state machine to find the braces
            pattern = rf"\btype\s+{op_type}\s*\{{"
            match = re.search(pattern, content)
            if not match:
                continue

            start = match.end()
            brace_depth = 1
            end = start
            while end < len(content) and brace_depth > 0:
                if content[end] == "{":
                    brace_depth += 1
                elif content[end] == "}":
                    brace_depth -= 1
                end += 1

            block = content[start:end - 1]

            # Parse each field line: fieldName(args): ReturnType
            for line in block.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Skip field directives and descriptions
                if line.startswith("@") or line.startswith('"""'):
                    continue

                # fieldName(arg1: Type1, arg2: Type2): ReturnType
                # Handle multi-line fields by joining
                m = re.match(r"(\w+)\s*(?:\(([^)]*)\))?\s*:\s*(.+?)(?:\s*\{.*)?$", line)
                if m:
                    field_name = m.group(1)
                    args_str = m.group(2) or ""
                    return_type = m.group(3).strip()

                    # Strip trailing ! and [ ]
                    return_clean = return_type.rstrip("!")
                    is_list = "[" in return_type
                    is_required = return_type.endswith("!")

                    params = _parse_arguments(args_str)

                    fact = CodeFact(
                        name=field_name,
                        kind=FactKind.API_ENDPOINT,
                        source_file=source_file,
                        line_number=self._approx_line(content, match.start() + start),
                        parameters=params,
                        return_type=return_clean,
                        module=op_type,
                        metadata={
                            "operation_type": op_type.lower(),
                            "is_required": is_required,
                            "is_list": is_list,
                        },
                    )
                    facts.append(fact)

        return facts

    def _extract_input_types(self, content: str, source_file: Path) -> list[Any]:
        """Extract input type definitions with their fields."""
        facts = []

        # Find all input type blocks: input CreateUserInput { ... }
        for match in re.finditer(r"\binput\s+(\w+)\s*\{", content):
            type_name = match.group(1)
            start = match.end()
            brace_depth = 1
            end = start
            while end < len(content) and brace_depth > 0:
                if content[end] == "{":
                    brace_depth += 1
                elif content[end] == "}":
                    brace_depth -= 1
                end += 1

            block = content[start:end - 1]
            params = []

            for line in block.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("@") or line.startswith('"""'):
                    continue

                # fieldName: Type!
                m = re.match(r"(\w+)\s*:\s*(.+?)(?:\s*\{.*)?$", line)
                if m:
                    field_name = m.group(1)
                    type_info = m.group(2).strip()
                    nullable = not type_info.endswith("!")
                    type_clean = type_info.rstrip("!")
                    params.append(Parameter(
                        name=field_name,
                        type_annotation=type_clean,
                        kind="keyword",
                    ))

            fact = CodeFact(
                name=type_name,
                kind=FactKind.CLASS,
                source_file=source_file,
                line_number=self._approx_line(content, match.start()),
                parameters=params,
                metadata={"graphql_kind": "input"},
            )
            facts.append(fact)

        return facts

    def _extract_enum_types(self, content: str, source_file: Path) -> list[Any]:
        """Extract enum type definitions with their values."""
        facts = []

        # Find all enum type blocks: enum PostStatus { DRAFT PUBLISHED ... }
        for match in re.finditer(r"\benum\s+(\w+)\s*\{", content):
            type_name = match.group(1)
            start = match.end()
            brace_depth = 1
            end = start
            while end < len(content) and brace_depth > 0:
                if content[end] == "{":
                    brace_depth += 1
                elif content[end] == "}":
                    brace_depth -= 1
                end += 1

            block = content[start:end - 1]
            values = []
            for line in block.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Each line is an enum value name
                m = re.match(r"(\w+)", line)
                if m:
                    values.append(m.group(1))

            fact = CodeFact(
                name=type_name,
                kind=FactKind.CLASS,
                source_file=source_file,
                line_number=self._approx_line(content, match.start()),
                metadata={"graphql_kind": "enum", "values": values},
            )
            facts.append(fact)

        return facts

    def _approx_line(self, content: str, pos: int) -> int:
        """Approximate line number for a character position."""
        return content[:pos].count("\n") + 1
