"""Markdown documentation extractor for Drift.

Extracts DocClaim objects from Markdown files by finding:
- Function signatures in code blocks
- Inline code references
- CLI usage patterns
"""
import re
from pathlib import Path

from drift.models import ClaimKind, DocClaim, Parameter


# Pattern for function signatures in code blocks:
# def function_name(param: Type = default, ...) -> ReturnType:
# Note: colon is optional to handle malformed signatures
_FUNC_SIGNATURE_RE = re.compile(
    r'^def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*(?:->\s*([^:\n]+))?\s*:?',
    re.MULTILINE
)

# Pattern to parse individual parameters
_PARAM_RE = re.compile(
    r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*([^=]+?))?\s*(?:=\s*(.+))?$'
)

# Pattern for inline code references: `function_name(...)`
_INLINE_CODE_RE = re.compile(r'`([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^`]*`')

# Pattern for CLI usage: $ command or just command at start of line
_CLI_RE = re.compile(r'^\$\s+(\S+)(?:\s+(.+))?$|^(?:^|\n)([a-zA-Z_][a-zA-Z0-9_-]*)\s+(?:scan|run|exec|check)')

# Simple backtick inline: `code`
_SIMPLE_BACKTICK_RE = re.compile(r'`([^`]+)`')


class MarkdownExtractor:
    """Extracts DocClaim objects from Markdown files."""

    def extract(self, path: Path) -> list[DocClaim]:
        """Extract all DocClaim objects from a markdown file."""
        claims = []

        try:
            content = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError) as e:
            # Gracefully handle file read errors
            return claims

        lines = content.split('\n')

        # Extract code blocks
        claims.extend(self._extract_code_blocks(content, lines, path))

        # Extract inline code references
        claims.extend(self._extract_inline_refs(content, lines, path))

        # Extract CLI usage patterns
        claims.extend(self._extract_cli_usage(content, lines, path))

        return claims

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Markdown file."""
        return path.suffix.lower() == '.md'

    def _extract_code_blocks(self, content: str, lines: list[str], path: Path) -> list[DocClaim]:
        """Extract function signatures from code blocks."""
        claims = []
        in_code_block = False
        code_block_content = []
        code_block_start_line = 0

        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of code block - parse it
                    block_text = '\n'.join(code_block_content)
                    parsed = self._parse_code_block_signature(block_text, code_block_start_line + 1, path)
                    claims.extend(parsed)
                    code_block_content = []
                    in_code_block = False
                else:
                    # Start of code block
                    in_code_block = True
                    code_block_start_line = i
            elif in_code_block:
                code_block_content.append(line)

        return claims

    def _parse_code_block_signature(self, block_text: str, start_line: int, path: Path) -> list[DocClaim]:
        """Parse a code block for function signatures."""
        claims = []

        for match in _FUNC_SIGNATURE_RE.finditer(block_text):
            func_name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3)
            offset = block_text[:match.start()].count('\n')

            parameters = self._parse_parameters(params_str)

            claim = DocClaim(
                raw_text=match.group(0),
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=path,
                line_number=start_line + offset,
                name=func_name,
                parameters=parameters,
                return_type=return_type.strip() if return_type else None,
            )
            claims.append(claim)

        return claims

    def _parse_parameters(self, params_str: str) -> list[Parameter]:
        """Parse a parameter list string into Parameter objects."""
        parameters = []

        if not params_str.strip():
            return parameters

        # Split by comma, but handle nested brackets carefully
        param_parts = self._split_params(params_str)

        for part in param_parts:
            part = part.strip()
            if not part:
                continue

            # Handle *args and **kwargs
            if part.startswith('*') and '**' not in part:
                name = part.lstrip('*').strip()
                param_kind = 'varargs'
            elif part.startswith('**'):
                name = part.lstrip('*').strip()
                param_kind = 'varkw'
            else:
                name = part
                param_kind = 'positional'

            # Try to parse name:type = default or name = default
            param_match = _PARAM_RE.match(part)

            if param_match:
                name = param_match.group(1)
                type_annotation = param_match.group(2)
                default = param_match.group(3)

                if type_annotation:
                    type_annotation = type_annotation.strip()
                if default:
                    default = default.strip()

                parameters.append(Parameter(
                    name=name,
                    type_annotation=type_annotation,
                    default=default,
                    kind=param_kind,
                ))
            else:
                # Fallback: just use the part as name
                parameters.append(Parameter(name=name, kind=param_kind))

        return parameters

    def _split_params(self, params_str: str) -> list[str]:
        """Split parameter string by comma, respecting brackets."""
        result = []
        current = []
        bracket_depth = 0

        for char in params_str:
            if char in '([{':
                bracket_depth += 1
                current.append(char)
            elif char in ')]}':
                bracket_depth -= 1
                current.append(char)
            elif char == ',' and bracket_depth == 0:
                result.append(''.join(current))
                current = []
            else:
                current.append(char)

        if current:
            result.append(''.join(current))

        return result

    def _extract_inline_refs(self, content: str, lines: list[str], path: Path) -> list[DocClaim]:
        """Extract inline code references like `function_name(args)`."""
        claims = []
        seen = set()  # Avoid duplicate claims on same line

        for i, line in enumerate(lines):
            # Look for inline code patterns
            matches = _SIMPLE_BACKTICK_RE.findall(line)

            for match in matches:
                # Skip if it looks like a code block marker or is too short
                if match.strip().startswith('```') or len(match) < 2:
                    continue

                # Check if this is a function call pattern
                call_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*)\)$', match)

                if call_match:
                    func_name = call_match.group(1)
                    key = (i, match)
                    if key in seen:
                        continue
                    seen.add(key)

                    # Try to parse parameters
                    params_str = call_match.group(2)
                    parameters = self._parse_parameters(params_str) if params_str.strip() else []

                    claim = DocClaim(
                        raw_text=match,
                        kind=ClaimKind.CODE_EXAMPLE,
                        doc_file=path,
                        line_number=i + 1,
                        name=func_name,
                        parameters=parameters,
                    )
                    claims.append(claim)
                elif re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', match):
                    # Simple identifier in backticks - record as code example
                    key = (i, match)
                    if key in seen:
                        continue
                    seen.add(key)

                    claim = DocClaim(
                        raw_text=match,
                        kind=ClaimKind.CODE_EXAMPLE,
                        doc_file=path,
                        line_number=i + 1,
                        name=match,
                        parameters=[],
                    )
                    claims.append(claim)

        return claims

    def _extract_cli_usage(self, content: str, lines: list[str], path: Path) -> list[DocClaim]:
        """Extract CLI usage patterns like $ drift scan [PATH]."""
        claims = []

        for i, line in enumerate(lines):
            line = line.strip()

            # Pattern: $ command args
            dollar_match = re.match(r'^\$\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*(.*)?$', line)
            if dollar_match:
                cmd_name = dollar_match.group(1)
                args_str = dollar_match.group(2) or ""

                claim = DocClaim(
                    raw_text=line,
                    kind=ClaimKind.CLI_USAGE,
                    doc_file=path,
                    line_number=i + 1,
                    name=cmd_name,
                    metadata={'args': args_str},
                )
                claims.append(claim)
                continue

            # Pattern: command scan/run/etc (without $)
            bare_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_-]*)\s+(scan|run|exec|check|version|help)\s*(.*)$', line, re.MULTILINE)
            if bare_match:
                cmd_name = bare_match.group(1)
                action = bare_match.group(2)
                args_str = bare_match.group(3) or ""

                # Avoid double-counting if we already found this with $
                existing = any(
                    c.kind == ClaimKind.CLI_USAGE and c.name == cmd_name and c.line_number == i + 1
                    for c in claims
                )
                if not existing:
                    claim = DocClaim(
                        raw_text=line,
                        kind=ClaimKind.CLI_USAGE,
                        doc_file=path,
                        line_number=i + 1,
                        name=cmd_name,
                        metadata={'args': args_str, 'action': action},
                    )
                    claims.append(claim)

        return claims
