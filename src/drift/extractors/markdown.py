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

# Pattern for CLI flags in documentation:
# --flag or -f (with optional =value)
_CLI_FLAG_PATTERN = re.compile(r'(--[a-zA-Z0-9_-]+|-[a-zA-Z])(?:[=:\s][^`\s]*)?')

# Simple backtick inline: `code`
_SIMPLE_BACKTICK_RE = re.compile(r'`([^`]+)`')

# Pattern for a markdown table row separator: |---|---|
_TABLE_SEP_RE = re.compile(r'^\|[\s|-]+\|[\s|-]+\|$')

# Pattern to find a CLI flag in a table cell: --flag or -f (with optional value)
_TABLE_FLAG_RE = re.compile(r'^(-{1,2}[a-zA-Z0-9_-]+)(?:\s*=\s*(\S+))?$')


class MarkdownExtractor:
    """Extracts DocClaim objects from Markdown files."""

    def extract(self, path: Path) -> list[DocClaim]:
        """Extract all DocClaim objects from a markdown file."""
        claims: list[DocClaim] = []

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

        # Extract CLI flag references from bash/shell code blocks
        claims.extend(self._extract_cli_flag_refs(content, lines, path))

        # Extract CLI flag references from markdown tables
        claims.extend(self._extract_cli_flags_from_tables(content, lines, path))

        # Extract config/env var references from inline text and tables
        claims.extend(self._extract_config_refs(content, lines, path))

        return claims

    def can_handle(self, path: Path) -> bool:
        """Return True if this is a Markdown file."""
        return path.suffix.lower() == '.md'

    def _extract_code_blocks(self, content: str, lines: list[str], path: Path) -> list[DocClaim]:
        """Extract function signatures from code blocks."""
        claims: list[DocClaim] = []
        in_code_block = False
        code_block_content: list[str] = []
        code_block_start_line = 0
        pending_suppression: dict[str, object] | None = None

        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                if in_code_block:
                    # End of code block - parse it
                    block_text = '\n'.join(code_block_content)
                    parsed = self._parse_code_block_signature(
                        block_text, code_block_start_line + 1, path, pending_suppression
                    )
                    claims.extend(parsed)
                    code_block_content = []
                    in_code_block = False
                    pending_suppression = None
                else:
                    # Start of code block - check for suppression comments in preceding lines
                    pending_suppression = self._check_suppression_before(lines, i)
                    # Start of code block
                    in_code_block = True
                    code_block_start_line = i
            elif in_code_block:
                code_block_content.append(line)

        return claims

    def _check_suppression_before(self, lines: list[str], code_block_start: int) -> dict[str, object] | None:
        """Check lines before a code block for drift:ignore suppression comments.

        Returns a dict with suppression info or None if no suppression.
        Supports:
          <!-- drift:ignore -->      → suppress all in next block
          <!-- drift:ignore name -->  → suppress only 'name' in next block
        """
        suppression: dict[str, object] | None = None
        # Look at the 5 lines before the code block
        for j in range(code_block_start - 1, max(0, code_block_start - 6), -1):
            line = lines[j].strip()
            if '<!--' in line and '-->' in line and 'drift:ignore' in line:
                # Extract target if any
                import re
                m = re.search(r'drift:ignore\s*(.*?)-->', line)
                if m:
                    target = m.group(1).strip()
                    if target:
                        suppression = {"suppress_for": target}
                    else:
                        suppression = {"suppress_all": True}
                else:
                    suppression = {"suppress_all": True}
                break
        return suppression

    def _parse_code_block_signature(
        self,
        block_text: str,
        start_line: int,
        path: Path,
        suppression: dict[str, object] | None = None,
    ) -> list[DocClaim]:
        """Parse a code block for function signatures."""
        claims: list[DocClaim] = []

        for match in _FUNC_SIGNATURE_RE.finditer(block_text):
            func_name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3)
            offset = block_text[:match.start()].count('\n')

            parameters = self._parse_parameters(params_str)

            metadata: dict[str, object] = {}
            is_suppressed = False
            if suppression:
                if suppression.get("suppress_all"):
                    is_suppressed = True
                elif suppression.get("suppress_for") == func_name:
                    is_suppressed = True
                metadata["suppressed"] = is_suppressed
                if is_suppressed:
                    metadata["suppress_reason"] = "drift:ignore"

            claim = DocClaim(
                raw_text=match.group(0),
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=path,
                line_number=start_line + offset,
                name=func_name,
                parameters=parameters,
                return_type=return_type.strip() if return_type else None,
                metadata=metadata,
            )
            claims.append(claim)

        return claims

    def _parse_parameters(self, params_str: str) -> list[Parameter]:
        """Parse a parameter list string into Parameter objects."""
        parameters: list[Parameter] = []

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

    def _extract_cli_flag_refs(self, content: str, lines: list[str], path: Path) -> list[DocClaim]:
        """Extract CLI flag references from bash/shell code blocks and inline text."""
        claims: list[DocClaim] = []
        in_shell_block = False
        seen: set[tuple[int, str]] = set()

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track shell/bash code blocks
            if stripped.startswith('```'):
                lang = stripped.lstrip('`').strip().lower()
                if lang in ('bash', 'shell', 'sh', 'zsh', ''):
                    in_shell_block = not in_shell_block
                continue

            if in_shell_block:
                # Extract flags from shell code block lines
                self._extract_flags_from_line(line, i + 1, path, claims, seen)
                continue

            # Also extract from plain lines that look like usage/documentation
            # Only flag lines that look like command invocations
            if stripped.startswith('$') or stripped.startswith('>'):
                self._extract_flags_from_line(line, i + 1, path, claims, seen)

        return claims

    def _extract_flags_from_line(
        self, line: str, line_number: int, path: Path,
        claims: list[DocClaim], seen: set[tuple[int, str]]
    ) -> None:
        """Extract CLI flag references from a single line."""
        for match in _CLI_FLAG_PATTERN.finditer(line):
            flag = match.group(1)
            key = (line_number, flag)
            if key in seen:
                continue
            seen.add(key)

            # Extract associated value if present (e.g. --flag=value)
            rest = match.group(0)[len(flag):].strip()
            default = None
            if rest.startswith('=') or rest.startswith(':'):
                default = rest.lstrip('=:').strip().strip('"\'')

            claim = DocClaim(
                raw_text=flag,
                kind=ClaimKind.CLI_FLAG_REF,
                doc_file=path,
                line_number=line_number,
                name=flag,
                metadata={} if default is None else {'default': default},
            )
            claims.append(claim)

    def _extract_cli_flags_from_tables(
        self, content: str, lines: list[str], path: Path
    ) -> list[DocClaim]:
        """Extract CLI flag references from markdown tables.

        Looks for tables whose rows contain --flag or -f style entries in any column.
        Handles:
        - Single flags: --verbose
        - Comma-separated flags: -v, --verbose
        - Flags with inline defaults: --port=8080
        - Defaults in separate columns (looked up by header proximity)
        """
        claims = []
        seen: set[tuple[int, str]] = set()

        # First pass: build a map of header column indices that look like "default" or "Default"
        header_line = -1
        default_col_indices: set[int] = set()

        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()

            if not stripped.startswith('|'):
                i += 1
                continue

            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if not cells:
                i += 1
                continue

            # Detect separator row — skip it
            if _TABLE_SEP_RE.match(stripped):
                i += 1
                continue

            # First row with non-separator content: treat as header
            if header_line == -1:
                header_line = i
                for idx, cell in enumerate(cells):
                    cell_lower = cell.lower()
                    if 'default' in cell_lower or 'dflt' in cell_lower:
                        default_col_indices.add(idx)
                i += 1
                continue

            # Data row — scan for flags in all cells
            for idx, cell in enumerate(cells):
                # Skip cells that are plain default values (not flag cells)
                # unless they are in the default column AND adjacent to a flag cell
                if not cell.startswith('-') and not cell.startswith('`'):
                    continue

                # Handle comma-separated flags: "-v, --verbose" or "-v, --verbose=8080"
                parts = [p.strip() for p in cell.split(',')]
                for part in parts:
                    flag_match = _TABLE_FLAG_RE.match(part)
                    if flag_match:
                        flag_name = flag_match.group(1)
                        default = flag_match.group(2)

                        # If no inline default, try to find it in a default-value column
                        # on the same row (adjacent or nearby cell)
                        if default is None and default_col_indices:
                            for dc_idx in default_col_indices:
                                if dc_idx < len(cells) and dc_idx != idx:
                                    potential_default = cells[dc_idx]
                                    # Skip if it looks like another flag
                                    if potential_default and not potential_default.startswith('-'):
                                        default = potential_default
                                        break

                        key = (i + 1, flag_name)
                        if key in seen:
                            continue
                        seen.add(key)

                        metadata = {}
                        if default:
                            metadata['default'] = default

                        claim = DocClaim(
                            raw_text=flag_name,
                            kind=ClaimKind.CLI_FLAG_REF,
                            doc_file=path,
                            line_number=i + 1,
                            name=flag_name,
                            metadata=metadata,
                        )
                        claims.append(claim)

            i += 1

        return claims

    def _extract_config_refs(self, content: str, lines: list[str], path: Path) -> list[DocClaim]:
        """Extract config/env var references from inline text and markdown tables.

        Handles:
          - Inline: $VAR_NAME, ${VAR_NAME}, `VAR_NAME` (backtick)
          - Tables: rows with UPPER_SNAKE_CASE names in Variable/Env/Name columns
        """
        claims: list[DocClaim] = []
        seen: set[tuple[int, str]] = set()

        # ── Inline patterns ────────────────────────────────────────────────────
        # $DATABASE_URL or ${DATABASE_URL} or $API_KEY
        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip inside code blocks (lines already in a block are skipped by content scanning)
            # $VAR patterns
            for m in re.finditer(r'\$({[A-Z_][A-Z0-9_]*}|[A-Z_][A-Z0-9_]*)', line):
                var_name = m.group(1).strip('{}')
                key = (i + 1, var_name)
                if key in seen:
                    continue
                seen.add(key)
                claims.append(DocClaim(
                    raw_text=m.group(0),
                    kind=ClaimKind.CONFIG_REF,
                    doc_file=path,
                    line_number=i + 1,
                    name=var_name,
                    metadata={},
                ))

            # Backtick refs: `DATABASE_URL`
            for m in re.finditer(r'`([A-Z_][A-Z0-9_]*)`', line):
                var_name = m.group(1)
                key = (i + 1, var_name)
                if key in seen:
                    continue
                seen.add(key)
                claims.append(DocClaim(
                    raw_text=m.group(0),
                    kind=ClaimKind.CONFIG_REF,
                    doc_file=path,
                    line_number=i + 1,
                    name=var_name,
                    metadata={},
                ))

        # ── Table patterns ────────────────────────────────────────────────────
        in_table = False
        header_cols: list[str] = []
        table_line_start = -1

        for i, line in enumerate(lines):
            line = line.strip()
            if not line.startswith('|'):
                in_table = False
                header_cols = []
                continue

            cells = [c.strip() for c in line.split('|')[1:-1]]
            if not cells:
                continue

            # Header row
            if not in_table:
                header_lower = [c.lower() for c in cells]
                # Check if this looks like a config/env table
                name_col = None
                default_col = None
                for idx, col in enumerate(header_lower):
                    if name_col is None and any(k in col for k in ('variable', 'env', 'name', 'key')):
                        name_col = idx
                    if default_col is None and any(k in col for k in ('default', 'dflt', 'value')):
                        default_col = idx
                if name_col is not None:
                    in_table = True
                    header_cols = cells
                    table_line_start = i
                continue

            # Separator row (|---|---|)
            if re.match(r'^\|[-:|\s]+\|$', line):
                continue

            # Data row
            if name_col is not None and name_col < len(cells):
                cell = cells[name_col].strip()
                # Skip flag-like cells (--flag or -f)
                if cell.startswith('-'):
                    continue
                # Match UPPER_SNAKE_CASE identifiers (env var names) or
                # dot-notation keys (e.g., database.port, server.host)
                is_upper_snake = re.match(r'^[A-Z_][A-Z0-9_]*$', cell) and len(cell) > 1
                is_dot_notation = re.match(r'^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)+$', cell, re.IGNORECASE)
                if is_upper_snake or is_dot_notation:
                    default_val = None
                    if default_col is not None and default_col < len(cells):
                        default_val = cells[default_col].strip()
                    key = (i + 1, cell)
                    if key in seen:
                        continue
                    seen.add(key)
                    metadata = {}
                    if default_val:
                        metadata['default'] = default_val
                    claims.append(DocClaim(
                        raw_text=cell,
                        kind=ClaimKind.CONFIG_REF,
                        doc_file=path,
                        line_number=i + 1,
                        name=cell,
                        metadata=metadata,
                    ))

        return claims
