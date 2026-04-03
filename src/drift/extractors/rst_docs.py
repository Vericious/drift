"""RST/Sphinx documentation extractor for Drift.

Extracts DocClaim objects from reStructuredText (.rst) files.
Parses Sphinx directives and field lists to extract:
- Function/method/class signatures from py:function, py:method, py:class directives
- Parameter descriptions from :param: and :type: field lists
- Return descriptions from :returns: and :rtype: field lists
- Code examples from code-block directives
"""

import re
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import ClaimKind, DocClaim, Parameter

# Pattern for Sphinx Python directive start lines
# .. py:function::, .. py:method::, .. py:class::
_PY_DIRECTIVE_LINE_RE = re.compile(
    r"\.\. py:(function|method|class)::\s*(.+?)(?:\s*)$",
    re.IGNORECASE,
)

# Pattern for function/method/class signature
_SIGNATURE_RE = re.compile(
    r"^([a-zA-Z_][a-zA-Z0-9_.]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\(([^)]*)\)\s*(?:->\s*([^\s:]+))?",
    re.MULTILINE,
)

# Pattern for :param name: description
_PARAM_RE = re.compile(r":param\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:", re.IGNORECASE)

# Pattern for :type name: type description
_TYPE_RE = re.compile(r":type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*:", re.IGNORECASE)

# Pattern for :returns: or :return: or :rtype:
_RETURNS_RE = re.compile(r":returns?:\s*(.+?)(?:\n|$)", re.IGNORECASE)
_RTYPE_RE = re.compile(r":rtype:\s*(.+?)(?:\n|$)", re.IGNORECASE)

# Pattern for code-block directives
_CODE_BLOCK_RE = re.compile(
    r"\.\. code-block::\s*(\w*)\n((?:\s+.+\n)+)",
    re.IGNORECASE,
)

# Simple code examples: :: followed by indented literal text
_LITERAL_BLOCK_RE = re.compile(r"::\n((?:\s+.+\n)+)")

# Pattern for Sphinx cross-reference roles: :func:`module.func`, :class:`name`, :meth:`name`
# The role name is captured (func|class|meth|mod), and the target (e.g. module.func)
_CROSS_REF_RE = re.compile(
    r":(func|class|meth|mod):`([^`]+)`",
    re.IGNORECASE,
)

# Pattern for .. automodule:: directive
_AUTOMODULE_RE = re.compile(
    r"\.\. automodule::\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*$",
    re.IGNORECASE,
)


def _parse_parameters(params_str: str) -> list[Parameter]:
    """Parse a parameter list string into Parameter objects."""
    parameters: list[Parameter] = []
    if not params_str.strip():
        return parameters

    param_parts = _split_params(params_str)
    for part in param_parts:
        part = part.strip()
        if not part:
            continue

        if part.startswith("*") and "**" not in part:
            name = part.lstrip("*").strip()
            param_kind = "varargs"
        elif part.startswith("**"):
            name = part.lstrip("*").strip()
            param_kind = "varkw"
        else:
            name = part
            param_kind = "positional"

        inner_match = re.match(
            r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*([^=]+?))?\s*(?:=\s*(.+))?$",
            part,
        )
        if inner_match:
            name = inner_match.group(1)
            type_annotation = inner_match.group(2)
            default = inner_match.group(3)
            if type_annotation:
                type_annotation = type_annotation.strip()
            if default:
                default = default.strip()
            parameters.append(
                Parameter(
                    name=name,
                    type_annotation=type_annotation,
                    default=default,
                    kind=param_kind,
                )
            )
        else:
            parameters.append(Parameter(name=name, kind=param_kind))

    return parameters


def _split_params(params_str: str) -> list[str]:
    """Split parameter string by comma, respecting brackets."""
    result = []
    current = []
    bracket_depth = 0
    for char in params_str:
        if char in "([{":
            bracket_depth += 1
            current.append(char)
        elif char in ")]}":
            bracket_depth -= 1
            current.append(char)
        elif char == "," and bracket_depth == 0:
            result.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        result.append("".join(current))
    return result


def _extract_signature_info(
    sig_str: str,
) -> tuple[str | None, list[Parameter], str | None]:
    """Extract name, parameters, and return type from a signature string."""
    match = _SIGNATURE_RE.match(sig_str.strip())
    if match:
        name = match.group(1)
        params_str = match.group(2)
        return_type = match.group(3)
        parameters = _parse_parameters(params_str)
        return name, parameters, return_type.strip() if return_type else None
    return None, [], None


def _extract_field_list(
    body: str,
) -> tuple[dict[str, str], dict[str, str], str | None, str | None]:
    """Extract :param:, :type:, :returns:, :rtype: fields from directive body."""
    params_described: dict[str, str] = {}
    types_described: dict[str, str] = {}
    return_desc: str | None = None
    return_type: str | None = None

    for m in _PARAM_RE.finditer(body):
        param_name = m.group(1)
        start = m.end()
        # Find next field marker
        next_markers = [
            (m2.start(), m2.group(0))
            for m2 in re.finditer(
                r"\n:param|\n:type|\n:return|\n:rtype", body[start:], re.IGNORECASE
            )
        ]
        if next_markers:
            end = start + min(offset for offset, _ in next_markers)
        else:
            end = len(body)
        desc = body[start:end].strip()
        desc = re.sub(r"^\s*:", "", desc).strip()
        params_described[param_name] = desc

    for m in _TYPE_RE.finditer(body):
        type_name = m.group(1)
        start = m.end()
        next_markers = [
            (m2.start(), m2.group(0))
            for m2 in re.finditer(
                r"\n:param|\n:type|\n:return|\n:rtype", body[start:], re.IGNORECASE
            )
        ]
        if next_markers:
            end = start + min(offset for offset, _ in next_markers)
        else:
            end = len(body)
        type_desc = body[start:end].strip()
        type_desc = re.sub(r"^\s*:", "", type_desc).strip()
        types_described[type_name] = type_desc

    ret_match = _RETURNS_RE.search(body)
    if ret_match:
        return_desc = ret_match.group(1).strip()

    rtype_match = _RTYPE_RE.search(body)
    if rtype_match:
        return_type = rtype_match.group(1).strip()

    return params_described, types_described, return_desc, return_type


def _get_indent(line: str) -> int:
    """Return the leading whitespace count of a line."""
    return len(line) - len(line.lstrip())


@register
class RSTDocsExtractor(Extractor):
    """Extract DocClaim objects from reStructuredText (.rst) Sphinx documentation.

    Handles:
    - .. py:function::, .. py:method::, .. py:class:: directives
    - :param name: and :type name: field lists
    - :returns: and :rtype: field lists
    - code-block and literal-block :: examples
    """

    def can_handle(self, path: Path) -> bool:
        """Return True if this is an RST file."""
        return path.suffix.lower() == ".rst"

    def extract(self, path: Path) -> list[DocClaim]:
        """Extract DocClaim objects from an RST file."""
        claims: list[DocClaim] = []
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return claims

        lines = content.split("\n")

        # Extract Sphinx Python directives
        claims.extend(self._extract_directives(content, lines, path))

        # Extract code blocks
        claims.extend(self._extract_code_blocks(content, lines, path))

        # Extract cross-references (:func:, :class:, :meth:, :mod:)
        claims.extend(self._extract_cross_references(content, path))

        # Extract automodule directives
        claims.extend(self._extract_automodule(content, lines, path))

        return claims

    def _extract_directives(
        self, content: str, lines: list[str], path: Path
    ) -> list[DocClaim]:
        """Extract claims from Sphinx Python directives using line-based parsing."""
        claims = []

        # Find all directive start line indices
        directive_starts: list[
            tuple[int, str, str]
        ] = []  # (line_idx, directive_type, sig_str)
        for i, line in enumerate(lines):
            m = _PY_DIRECTIVE_LINE_RE.match(line)
            if m:
                directive_starts.append((i, m.group(1), m.group(2)))

        for _idx, (start_line_idx, directive_type, sig_str) in enumerate(
            directive_starts
        ):
            # Determine indentation level of this directive
            base_indent = _get_indent(lines[start_line_idx])

            # Find the end of this directive (next directive at same or lower indent)
            end_line_idx = len(lines)
            for i in range(start_line_idx + 1, len(lines)):
                line = lines[i]
                # Empty lines / blank lines don't break the directive block
                if not line.strip():
                    continue
                line_indent = _get_indent(line)
                # A line at same or lower indent ends the block
                if line_indent <= base_indent:
                    end_line_idx = i
                    break

            # Build directive body from indented lines
            body_lines = []
            for i in range(start_line_idx + 1, end_line_idx):
                line = lines[i]
                if not line.strip():
                    body_lines.append("")
                    continue
                line_indent = _get_indent(line)
                if line_indent > base_indent:
                    # Strip leading indent to get content
                    body_lines.append(line[line_indent:])
                else:
                    break

            directive_body = "\n".join(body_lines)

            # Determine overall line number (1-indexed)
            line_number = start_line_idx + 1

            # Extract signature info
            name, parameters, return_type = _extract_signature_info(sig_str)
            if not name:
                sig_m = re.match(r"([a-zA-Z_][a-zA-Z0-9_.]*)", sig_str.strip())
                if sig_m:
                    name = sig_m.group(1)

            if not name:
                continue

            # Create FUNCTION_SIGNATURE claim
            func_claim = DocClaim(
                raw_text=lines[start_line_idx].strip(),
                kind=ClaimKind.FUNCTION_SIGNATURE,
                doc_file=path,
                line_number=line_number,
                name=name,
                parameters=parameters,
                return_type=return_type,
                metadata={"directive_type": directive_type},
            )
            claims.append(func_claim)

            # Extract field lists
            params_described, types_described, return_desc, _ = _extract_field_list(
                directive_body
            )

            for param_name, description in params_described.items():
                param_type = types_described.get(param_name)
                # Find line number for this param
                param_match = re.search(
                    rf":param\s+{re.escape(param_name)}\s*:",
                    directive_body,
                    re.IGNORECASE,
                )
                param_line = line_number
                if param_match:
                    body_offset = directive_body[: param_match.start()].count("\n")
                    param_line = line_number + body_offset

                param_claim = DocClaim(
                    raw_text=f":param {param_name}: {description}",
                    kind=ClaimKind.PARAMETER_DESCRIPTION,
                    doc_file=path,
                    line_number=param_line,
                    name=param_name,
                    parameters=[
                        Parameter(
                            name=param_name,
                            type_annotation=param_type,
                        )
                    ]
                    if param_type
                    else [Parameter(name=param_name)],
                    metadata={"description": description, "directive": name},
                )
                claims.append(param_claim)

            if return_desc:
                ret_match = _RETURNS_RE.search(directive_body)
                ret_line = line_number
                if ret_match:
                    body_offset = directive_body[: ret_match.start()].count("\n")
                    ret_line = line_number + body_offset

                ret_claim = DocClaim(
                    raw_text=f":returns: {return_desc}",
                    kind=ClaimKind.RETURN_DESCRIPTION,
                    doc_file=path,
                    line_number=ret_line,
                    name=name,
                    metadata={"description": return_desc, "directive": name},
                )
                claims.append(ret_claim)

        return claims

    def _extract_code_blocks(
        self, content: str, lines: list[str], path: Path
    ) -> list[DocClaim]:
        """Extract code examples from code-block and literal-block directives."""
        claims = []

        # code-block:: python / bash / etc
        for match in _CODE_BLOCK_RE.finditer(content):
            lang = match.group(1)
            code_body = match.group(2)

            line_offset = content[: match.start()].count("\n")
            line_number = line_offset + 1

            for line in code_body.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                call_match = re.match(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line)
                if not call_match:
                    call_match = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line)
                if call_match:
                    func_name = call_match.group(1)
                    claim = DocClaim(
                        raw_text=line,
                        kind=ClaimKind.CODE_EXAMPLE,
                        doc_file=path,
                        line_number=line_number,
                        name=func_name,
                        metadata={"language": lang, "source": "code-block"},
                    )
                    claims.append(claim)
                    break

        # literal-block :: (double colon syntax)
        for match in _LITERAL_BLOCK_RE.finditer(content):
            code_body = match.group(1)
            line_offset = content[: match.start()].count("\n")
            line_number = line_offset + 1

            for line in code_body.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                call_match = re.match(r"def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line)
                if not call_match:
                    call_match = re.match(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line)
                if call_match:
                    func_name = call_match.group(1)
                    claim = DocClaim(
                        raw_text=line,
                        kind=ClaimKind.CODE_EXAMPLE,
                        doc_file=path,
                        line_number=line_number,
                        name=func_name,
                        metadata={"source": "literal-block"},
                    )
                    claims.append(claim)
                    break

        return claims

    def _extract_cross_references(
        self, content: str, path: Path
    ) -> list[DocClaim]:
        """Extract claims from Sphinx cross-reference roles (:func:, :class:, :meth:, :mod:)."""
        claims = []

        for match in _CROSS_REF_RE.finditer(content):
            role = match.group(1).lower()
            target = match.group(2)

            line_offset = content[: match.start()].count("\n")
            line_number = line_offset + 1

            if role == "func":
                kind = ClaimKind.FUNCTION_REF
                # Extract function name from target like "module.func" or just "func"
                name = target.split(".")[-1] if "." in target else target
            elif role == "class":
                kind = ClaimKind.FUNCTION_REF
                name = target.split(".")[-1] if "." in target else target
            elif role == "meth":
                kind = ClaimKind.FUNCTION_REF
                name = target.split(".")[-1] if "." in target else target
            elif role == "mod":
                kind = ClaimKind.FUNCTION_REF
                name = target
            else:
                continue

            claim = DocClaim(
                raw_text=match.group(0),
                kind=kind,
                doc_file=path,
                line_number=line_number,
                name=name,
                metadata={
                    "role": role,
                    "target": target,
                    "source": "cross_ref",
                },
            )
            claims.append(claim)

        return claims

    def _extract_automodule(
        self, content: str, lines: list[str], path: Path
    ) -> list[DocClaim]:
        """Extract implicit claims from .. automodule:: directives.

        An automodule directive documents all public symbols in a module.
        We emit a FUNCTION_REF claim for each public name found in the
        directive's body (if any), and a claim for the module itself.
        """
        claims = []

        for i, line in enumerate(lines):
            m = _AUTOMODULE_RE.match(line)
            if not m:
                continue

            module_name = m.group(1)
            line_number = i + 1

            # Determine base indentation
            base_indent = _get_indent(line)

            # Collect symbols listed under this automodule directive
            symbols: list[str] = []
            for j in range(i + 1, len(lines)):
                next_line = lines[j]
                if not next_line.strip():
                    continue
                next_indent = _get_indent(next_line)
                if next_indent <= base_indent:
                    break
                # Look for :term: or :obj: or bare indented names
                stripped = next_line.strip()
                sym_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*$", stripped)
                if sym_match:
                    symbols.append(sym_match.group(1))

            # Emit a claim for the module itself
            claim = DocClaim(
                raw_text=line.strip(),
                kind=ClaimKind.FUNCTION_REF,
                doc_file=path,
                line_number=line_number,
                name=module_name,
                metadata={
                    "role": "mod",
                    "source": "automodule",
                    "symbols": symbols,
                },
            )
            claims.append(claim)

            # Emit a claim per exported symbol
            for sym in symbols:
                sym_claim = DocClaim(
                    raw_text=f".. automodule:: {module_name} (symbol: {sym})",
                    kind=ClaimKind.FUNCTION_REF,
                    doc_file=path,
                    line_number=line_number,
                    name=sym,
                    metadata={
                        "role": "func",
                        "target": f"{module_name}.{sym}",
                        "source": "automodule",
                    },
                )
                claims.append(sym_claim)

        return claims
