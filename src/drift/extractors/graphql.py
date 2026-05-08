"""GraphQL schema extractor for Drift.

Extracts facts from GraphQL Schema Definition Language (.graphql, .gql files).
Handles:
- Query, Mutation, Subscription type fields as API endpoints
- Input types and their fields
- Enum types
- Union types (with their member types)
- Interface types (with their possible types and fields)
- Scalar types
"""

import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


def _parse_arguments(arg_str: str) -> list[Parameter]:
    """Parse GraphQL field/argument definitions into Parameter objects."""
    if not arg_str or not arg_str.strip():
        return []

    params: list[Parameter] = []
    args = _split_args(arg_str)
    for arg in args:
        arg = arg.strip()
        if not arg:
            continue

        # Handle patterns like: id: ID!, name: String, user: User!
        # Group 1: arg name, Group 2: type annotation
        m = re.match(r"(\w+)\s*:\s*(.+)", arg)
        if m:
            param = Parameter(
                name=m.group(1),
                type_annotation=m.group(2).strip(),
            )
            params.append(param)

    return params


def _split_args(arg_str: str) -> list[str]:
    """Split argument string by comma, respecting nested parens/brackets."""
    result: list[str] = []
    depth = 0
    current = ""
    for ch in arg_str:
        if ch in "([{":
            depth += 1
            current += ch
        elif ch in ")]}":
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
    """Extract facts from GraphQL SDL files.

    Handles .graphql and .gql files.

    Example schema:
        type Query {
            user(id: ID!): User
            users(limit: Int): [User!]!
        }

        type User {
            id: ID!
            name: String!
            email: String
        }

        enum Status {
            ACTIVE
            INACTIVE
            PENDING
        }

        union SearchResult = User | Post | Comment

        interface Node {
            id: ID!
        }

        scalar DateTime

    Facts extracted:
      - graphql.Query.field.user (ARGUMENTS: id: ID!, user: User!)
      - graphql.User.field.id (ARGUMENTS: id: ID!)
      - graphql.Status enum value ACTIVE
      - graphql.SearchResult (union, member_types: [User, Post, Comment])
      - graphql.Node (interface, possible_types: [...])
      - graphql.DateTime (scalar)
    """

    _FIELD_PATTERN = re.compile(
        r"\b(?:type|interface)\s+(\w+)(?:\s+implements\s+[^{]+)?\s*\{([^}]+)\}",
        re.DOTALL,
    )
    _OPERATION_TYPE_PATTERN = re.compile(
        r"\b(?:type|interface)\s+(Query|Mutation|Subscription|Subscription)\s*\{([^}]+)\}",
        re.DOTALL,
    )
    _ENUM_PATTERN = re.compile(r"\benum\s+(\w+)\s*\{([^}]+)\}", re.DOTALL)
    _UNION_PATTERN = re.compile(r"\bunion\s+(\w+)\s*=\s*([^{]+)\{", re.DOTALL)
    _INTERFACE_PATTERN = re.compile(
        r"\binterface\s+(\w+)(?:\s+implements\s+[^{]+)?\s*\{([^}]+)\}",
        re.DOTALL,
    )
    _SCALAR_PATTERN = re.compile(r"\bscalar\s+(\w+)", re.DOTALL)
    _FIELD_DEF_PATTERN = re.compile(r"(\w+)(?:\s*\([^)]*\))?\s*:\s*([^(]+?)(?:\s*$)")

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a GraphQL schema file."""
        return path.suffix.lower() in (".graphql", ".gql")

    def _approx_line(self, content: str, match: re.Match[Any], offset: int = 0) -> int:
        """Approximate line number for a regex match."""
        return content[: match.start() + offset].count("\n") + 1

    def _extract_operation_types(
        self, content: str, source_file: Path
    ) -> list[CodeFact]:
        """Extract Query, Mutation, and Subscription root types."""
        facts: list[CodeFact] = []

        # Match root operation types
        for match in re.finditer(
            r"\b(type|interface)\s+(Query|Mutation|Subscription)\s*\{([^}]+)\}",
            content,
            re.DOTALL,
        ):
            type_name = match.group(2)
            block = match.group(3)

            # Determine if it's a root operation or regular type
            kind = "operation" if type_name in ("Query", "Mutation", "Subscription") else "object"

            # Extract field definitions line by line
            lines = block.split("\n")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Match field definitions: fieldName(arg: Type): ReturnType
                field_match = re.match(r"(\w+)(?:\s*\(([^)]*)\))?\s*:\s*([^(]+)$", line)
                if field_match:
                    field_name = field_match.group(1)
                    args_str = field_match.group(2) or ""
                    return_type = field_match.group(3).strip()

                    params = _parse_arguments(args_str)

                    fact_name = f"graphql.{type_name}.field.{field_name}"
                    facts.append(
                        CodeFact(
                            name=fact_name,
                            kind=FactKind.CLASS,
                            source_file=source_file,
                            line_number=self._approx_line(content, match),
                            metadata={
                                "graphql_kind": kind,
                                "type": type_name,
                                "field": field_name,
                                "return_type": return_type,
                                "arguments": [p.__dict__ for p in params],
                            },
                        )
                    )

        return facts

    def _extract_input_types(self, content: str, source_file: Path) -> list[CodeFact]:
        """Extract input object types."""
        facts: list[CodeFact] = []

        for match in re.finditer(
            r"\binput\s+(\w+)\s*\{([^}]+)\}", content, re.DOTALL
        ):
            type_name = match.group(1)
            block = match.group(2)

            params = _parse_arguments(block)

            fact_name = f"graphql.{type_name}"
            facts.append(
                CodeFact(
                    name=fact_name,
                    kind=FactKind.CLASS,
                    source_file=source_file,
                    line_number=self._approx_line(content, match),
                    metadata={
                        "graphql_kind": "input",
                        "type": type_name,
                        "fields": [p.__dict__ for p in params],
                    },
                )
            )

        return facts

    def _extract_enum_types(self, content: str, source_file: Path) -> list[CodeFact]:
        """Extract enum type definitions with their values."""
        facts: list[CodeFact] = []

        enum_block_re = re.compile(r"\benum\s+(\w+)\s*\{([^}]+)\}", re.DOTALL)
        for match in enum_block_re.finditer(content):
            type_name = match.group(1)
            block = match.group(2)

            # Parse enum values (simple - just word boundaries)
            # Need to track brace depth in case of directives or comments
            values: list[str] = []
            start = match.start(2)
            end = start
            depth = 0

            # Find the end by tracking braces
            while end < len(content) and (end < start + len(block) or depth > 0):
                if block[end - start] == "{":
                    depth += 1
                elif block[end - start] == "}":
                    depth -= 1
                end += 1

            inner = block.strip()
            if inner.startswith("{") and inner.endswith("}"):
                inner = inner[1:-1]

            for line in inner.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                val_match = re.match(r"(\w+)", line)
                if val_match:
                    values.append(val_match.group(1))

            facts.append(
                CodeFact(
                    name=f"graphql.{type_name}",
                    kind=FactKind.CLASS,
                    source_file=source_file,
                    line_number=self._approx_line(content, match),
                    metadata={
                        "graphql_kind": "enum",
                        "values": values,
                    },
                )
            )

        return facts

    def _extract_union_types(self, content: str, source_file: Path) -> list[CodeFact]:
        """Extract union type definitions with their member types."""
        facts: list[CodeFact] = []

        # Union pattern: union UnionName = Type1 | Type2 | Type3
        # The = can be on same line or the member types on following lines in braces
        union_re = re.compile(r"\bunion\s+(\w+)\s*=\s*([^{]+)", re.DOTALL)
        for match in union_re.finditer(content):
            type_name = match.group(1)
            member_str = match.group(2).strip()

            # Parse member types: Type1 | Type2 | Type3
            # Can be inline (union Foo = A | B) or spread across lines
            member_types: list[str] = []
            for part in member_str.split("|"):
                part = part.strip()
                if part:
                    # Extract type name (might have ! suffix)
                    type_match = re.match(r"(\w+)", part)
                    if type_match:
                        member_types.append(type_match.group(1))

            facts.append(
                CodeFact(
                    name=f"graphql.{type_name}",
                    kind=FactKind.CLASS,
                    source_file=source_file,
                    line_number=self._approx_line(content, match),
                    metadata={
                        "graphql_kind": "union",
                        "member_types": member_types,
                    },
                )
            )

        return facts

    def _extract_interface_types(self, content: str, source_file: Path) -> list[CodeFact]:
        """Extract interface type definitions with their fields."""
        facts: list[CodeFact] = []

        # Interface pattern: interface InterfaceName { field: Type }
        interface_re = re.compile(
            r"\binterface\s+(\w+)(?:\s+implements\s+([^{]+))?\s*\{([^}]+)\}",
            re.DOTALL,
        )
        for match in interface_re.finditer(content):
            type_name = match.group(1)
            implements_str = match.group(2) or ""
            block = match.group(3)

            # Parse implemented interfaces
            implements: list[str] = []
            if implements_str:
                for part in implements_str.split(","):
                    part = part.strip()
                    if part:
                        implements.append(part)

            # Parse fields
            fields_params = _parse_arguments(block)

            facts.append(
                CodeFact(
                    name=f"graphql.{type_name}",
                    kind=FactKind.CLASS,
                    source_file=source_file,
                    line_number=self._approx_line(content, match),
                    metadata={
                        "graphql_kind": "interface",
                        "fields": [p.__dict__ for p in fields_params],
                        "implements": implements,
                    },
                )
            )

        return facts

    def _extract_scalar_types(self, content: str, source_file: Path) -> list[CodeFact]:
        """Extract custom scalar type definitions."""
        facts: list[CodeFact] = []

        scalar_re = re.compile(r"\bscalar\s+(\w+)", re.DOTALL)
        for match in scalar_re.finditer(content):
            type_name = match.group(1)

            facts.append(
                CodeFact(
                    name=f"graphql.{type_name}",
                    kind=FactKind.CLASS,
                    source_file=source_file,
                    line_number=self._approx_line(content, match),
                    metadata={
                        "graphql_kind": "scalar",
                    },
                )
            )

        return facts

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract GraphQL schema facts from a .graphql file."""
        facts: list[CodeFact] = []

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return facts

        facts.extend(self._extract_operation_types(content, path))
        facts.extend(self._extract_input_types(content, path))
        facts.extend(self._extract_enum_types(content, path))
        facts.extend(self._extract_union_types(content, path))
        facts.extend(self._extract_interface_types(content, path))
        facts.extend(self._extract_scalar_types(content, path))

        return facts
