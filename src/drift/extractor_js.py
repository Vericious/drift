"""JS/TS JSDoc extractor for Drift.

Extracts @param, @returns, @type, @throws, @see, and @name JSDoc annotations
from .js and .ts files, producing DocClaim objects.
"""

import re
from pathlib import Path

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import ClaimKind, DocClaim, Parameter


# Match JSDoc comment blocks: /** ... */
_JSDOC_BLOCK_RE = re.compile(r"/\*\*((?:[^*]|\*(?!/))*)\*/", re.DOTALL)

# Match @name annotation within a JSDoc block
_NAME_RE = re.compile(r"@name\s+([^\s@]+)")

# Match @param annotation:
# @param {type} name - description
# @param name - description  (JSDoc 3 legacy without type)
_PARAM_RE = re.compile(
    r"@param\s+(?:\{([^}]+)\}\s+)?(?:\[[^\]]+\]\s+)?([^\s@-][^\s-]*)(?:\s+-\s+(.*))?"
)

# Match @returns / @return annotation:
# @returns {type} description
# @return {type} description
_RETURNS_RE = re.compile(
    r"@returns?\s+(?:\{([^}]+)\}\s+)?(.*)"
)

# Match @type annotation:
# @type {type} description
_TYPE_RE = re.compile(r"@type\s+\{([^}]+)\}(?:\s+(.*))?")

# Match @throws annotation:
# @throws {type} description
_THROWS_RE = re.compile(r"@throws\s+\{([^}]+)\}(?:\s+(.*))?")

# Match @see annotation:
# @see [text](url)
# @see url
# @see text
_SEE_RE = re.compile(r"@see\s+(.*)")

# Match function declarations in JS/TS:
# function name(...) { ... }
# const name = (...) => ...
# const name = function(...) ...
# async function name(...)
_FUNCTION_DECL_RE = re.compile(
    r"(?:async\s+)?function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)",
    re.MULTILINE,
)

# Arrow function: const name = (...) => ...
_ARROW_CONST_RE = re.compile(
    r"const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>",
    re.MULTILINE,
)

# Function expression: const name = function(...) ...
_FUNC_EXPR_RE = re.compile(
    r"const\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s+(?:async\s+)?function\s*\(([^)]*)\)",
    re.MULTILINE,
)

# Class method: name(...) { ... } (inside class body)
_CLASS_METHOD_RE = re.compile(
    r"(?:async\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)\s*(?::\s*[^{]+)?\s*\{",
    re.MULTILINE,
)

# TS interface/function signature: name(params): type
_TS_SIGNATURE_RE = re.compile(
    r"(?:export\s+)?function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*<[^>]+>\s*\(([^)]*)\)\s*:\s*[^;]+;",
    re.MULTILINE,
)

# TS type alias: type Name = ...
_TS_TYPE_RE = re.compile(
    r"type\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:React\.)?[^;]+;",
    re.MULTILINE,
)

# TS interface method signature
_TS_INTERFACE_METHOD_RE = re.compile(
    r"([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\(([^)]*)\)\s*:\s*[^;{]+(?:\{[^}]*\})?;",
    re.MULTILINE,
)


def _clean_text(text: str | None) -> str | None:
    """Strip leading/trailing whitespace from text, return None if empty."""
    if text is None:
        return None
    text = text.strip()
    return text if text else None


def _parse_param_name(param_str: str) -> list[Parameter]:
    """Parse a parameter string into Parameter objects."""
    params: list[Parameter] = []
    if not param_str.strip():
        return params

    # Handle destructuring: { a, b } or { a: type }
    if param_str.strip().startswith("{"):
        # Simple destructuring pattern
        inner = param_str.strip()[1:-1]
        for part in inner.split(","):
            part = part.strip()
            if not part:
                continue
            # Handle a: Type pattern
            name = part.split(":")[0].strip()
            ptype = None
            if ":" in part:
                ptype = part.split(":", 1)[1].strip()
            params.append(Parameter(name=name, type_annotation=ptype, kind="positional"))
        return params

    # Handle rest: ...name
    if param_str.strip().startswith("..."):
        name = param_str.strip()[3:].strip()
        params.append(Parameter(name="..." + name, kind="varargs"))
        return params

    # Simple comma-separated params
    for i, part in enumerate(param_str.split(",")):
        part = part.strip()
        if not part:
            continue

        # Handle name: Type = default patterns (TypeScript)
        name = part
        ptype = None
        default = None

        if ": " in part or ":" in part:
            # Split on first colon for type annotation
            colon_idx = part.index(":")
            name = part[:colon_idx].strip()
            rest = part[colon_idx + 1:].strip()
            # Check for default value after =
            if "=" in rest:
                type_part, default = rest.split("=", 1)
                ptype = type_part.strip()
                default = default.strip()
            else:
                ptype = rest

        # Handle name = default patterns (JavaScript)
        if "=" in name and ptype is None:
            name, default = name.split("=", 1)
            name = name.strip()
            default = default.strip()

        params.append(Parameter(
            name=name,
            type_annotation=ptype if ptype else None,
            default=default if default else None,
            kind="positional",
        ))

    return params


def _find_jsdoc_block_before(content: str, match_start: int) -> str | None:
    """Find the JSDoc comment block immediately preceding a match.

    Returns the JSDoc text (without /** and */ delimiters) or None.
    """
    # Look backwards from match_start for /**
    search_start = max(0, match_start - 500)
    snippet = content[search_start:match_start]

    # Find the last /** in the snippet
    jsdoc_start = snippet.rfind("/**")
    if jsdoc_start == -1:
        return None

    jsdoc_text = snippet[jsdoc_start + 3:]

    # Check this block ends properly
    if "*/" not in jsdoc_text:
        return None

    block_end = jsdoc_text.index("*/")
    return jsdoc_text[:block_end]


def _extract_jsdoc_claims(
    jsdoc_text: str,
    func_name: str,
    param_str: str,
    line_offset: int,
    source_file: Path,
    content: str,
    match_start: int,
) -> list[DocClaim]:
    """Extract DocClaim objects from a JSDoc block and function context."""
    claims: list[DocClaim] = []

    # Try @name first (explicit name override)
    name_match = _NAME_RE.search(jsdoc_text)
    effective_name = name_match.group(1) if name_match else func_name

    # Extract @params
    for pm in _PARAM_RE.finditer(jsdoc_text):
        ptype = _clean_text(pm.group(1))
        raw_pname = pm.group(2)
        # Strip [] from optional parameter names: [name] -> name
        if raw_pname and raw_pname.startswith("["):
            pname = _clean_text(raw_pname[1:].rstrip("]")) if len(raw_pname) > 2 else None
        else:
            pname = _clean_text(raw_pname)
        pdesc = _clean_text(pm.group(3))

        if pname:
            params = _parse_param_name(param_str) if param_str else []
            # Check if we can match param by name
            matching_params = [p for p in params if p.name == pname]
            if not matching_params:
                matching_params = [Parameter(name=pname, type_annotation=ptype)]

            claim = DocClaim(
                raw_text=f"@param {ptype + ' ' if ptype else ''}{pname}"
                         + (f" - {pdesc}" if pdesc else ""),
                kind=ClaimKind.PARAMETER_DESCRIPTION,
                doc_file=source_file,
                line_number=line_offset,
                name=effective_name,
                parameters=matching_params,
                return_type=None,
                metadata={
                    "description": pdesc,
                    "type": ptype,
                    "source": "jsdoc",
                },
            )
            claims.append(claim)

    # Extract @returns / @return
    for rm in _RETURNS_RE.finditer(jsdoc_text):
        rtype = _clean_text(rm.group(1))
        rdesc = _clean_text(rm.group(2))

        claim = DocClaim(
            raw_text=f"@returns"
                     + (f" {{{rtype}}}" if rtype else "")
                     + (f" {rdesc}" if rdesc else ""),
            kind=ClaimKind.RETURN_DESCRIPTION,
            doc_file=source_file,
            line_number=line_offset,
            name=effective_name,
            parameters=[],
            return_type=rtype,
            metadata={
                "description": rdesc,
                "type": rtype,
                "source": "jsdoc",
            },
        )
        claims.append(claim)

    # Extract @type (standalone type annotation, not @param/@returns)
    for tm in _TYPE_RE.finditer(jsdoc_text):
        ttype = _clean_text(tm.group(1))
        tdesc = _clean_text(tm.group(2))

        claim = DocClaim(
            raw_text=f"@type {{{ttype}}}" + (f" {tdesc}" if tdesc else ""),
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=source_file,
            line_number=line_offset,
            name=effective_name,
            parameters=_parse_param_name(param_str) if param_str else [],
            return_type=ttype,
            metadata={
                "description": tdesc,
                "type": ttype,
                "source": "jsdoc",
                "category": "type",
            },
        )
        claims.append(claim)

    # Extract @throws
    for thm in _THROWS_RE.finditer(jsdoc_text):
        thtype = _clean_text(thm.group(1))
        thdesc = _clean_text(thm.group(2))

        claim = DocClaim(
            raw_text=f"@throws {{{thtype}}}" + (f" {thdesc}" if thdesc else ""),
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=source_file,
            line_number=line_offset,
            name=effective_name,
            parameters=_parse_param_name(param_str) if param_str else [],
            metadata={
                "description": thdesc,
                "type": thtype,
                "source": "jsdoc",
                "category": "throws",
            },
        )
        claims.append(claim)

    # Extract @see
    for sm in _SEE_RE.finditer(jsdoc_text):
        see_text = _clean_text(sm.group(1))

        claim = DocClaim(
            raw_text=f"@see {see_text}" if see_text else "@see",
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=source_file,
            line_number=line_offset,
            name=effective_name,
            parameters=_parse_param_name(param_str) if param_str else [],
            metadata={
                "description": see_text,
                "source": "jsdoc",
                "category": "see",
            },
        )
        claims.append(claim)

    # If JSDoc exists but no recognized tags, capture it as a general docstring claim
    if not claims and jsdoc_text.strip():
        claim = DocClaim(
            raw_text=jsdoc_text.strip(),
            kind=ClaimKind.FUNCTION_SIGNATURE,
            doc_file=source_file,
            line_number=line_offset,
            name=effective_name,
            parameters=_parse_param_name(param_str) if param_str else [],
            metadata={
                "description": jsdoc_text.strip(),
                "source": "jsdoc",
                "category": "docstring",
            },
        )
        claims.append(claim)

    return claims


def _count_newlines_before(content: str, pos: int) -> int:
    """Count newlines before position pos in content."""
    return content[:pos].count("\n")


@register
class JSDocExtractor(Extractor):
    """Extract DocClaim objects from JS/TS files via JSDoc comments.

    Handles:
    - @param {type} name - description
    - @returns {type} description
    - @type {type} description
    - @throws {type} description
    - @see reference
    - @name explicitName
    - bare JSDoc blocks (captured as docstring)
    """

    def can_handle(self, path: Path) -> bool:
        """Return True for .js and .ts files."""
        return path.suffix.lower() in (".js", ".ts", ".jsx", ".tsx")

    def extract(self, path: Path) -> list[DocClaim]:
        """Extract all DocClaim objects from a JS/TS file."""
        claims: list[DocClaim] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return claims

        lines = content.split("\n")

        # Find all JSDoc block positions
        jsdoc_blocks: list[tuple[int, str]] = []  # (start_pos, text)
        for m in _JSDOC_BLOCK_RE.finditer(content):
            jsdoc_text = m.group(1)
            jsdoc_blocks.append((m.start(), jsdoc_text))

        # Try to match function declarations and associate with preceding JSDoc
        patterns_and_kinds: list[tuple[re.Pattern[str], str]] = [
            (_FUNCTION_DECL_RE, "function"),
            (_ARROW_CONST_RE, "arrow"),
            (_FUNC_EXPR_RE, "func_expr"),
            (_CLASS_METHOD_RE, "class_method"),
        ]

        found_matches: list[tuple[int, str, str, str]] = []  # (pos, name, params, kind)

        for pattern, _ in patterns_and_kinds:
            for m in pattern.finditer(content):
                found_matches.append((m.start(), m.group(1), m.group(2), _))

        # Also find TS-specific signatures
        for m in _TS_SIGNATURE_RE.finditer(content):
            found_matches.append((m.start(), m.group(1), m.group(2), "ts_function"))

        for m in _TS_INTERFACE_METHOD_RE.finditer(content):
            found_matches.append((m.start(), m.group(1), m.group(2), "ts_interface"))

        # Sort by position
        found_matches.sort(key=lambda x: x[0])

        for pos, name, params, kind in found_matches:
            # Find the JSDoc block that precedes this function
            preceding_jsdoc: str | None = None
            jsdoc_line_offset = 0

            # Find the JSDoc block that ends just before this function
            for jsdoc_pos, jsdoc_text in jsdoc_blocks:
                block_end = jsdoc_pos + len(jsdoc_text) + 4  # +3 for /** */ +1
                # The block should end within ~10 chars before the function
                gap = pos - block_end
                if 0 <= gap <= 15 and block_end <= pos:
                    preceding_jsdoc = jsdoc_text
                    jsdoc_line_offset = _count_newlines_before(content, jsdoc_pos) + 1
                    break

            if preceding_jsdoc is not None:
                new_claims = _extract_jsdoc_claims(
                    preceding_jsdoc,
                    name,
                    params,
                    jsdoc_line_offset,
                    path,
                    content,
                    pos,
                )
                claims.extend(new_claims)
            elif kind in ("function", "ts_function", "arrow", "func_expr"):
                # Function without JSDoc - still register with empty claim if it's exported
                # Check if it's exported
                export_kw = "export "
                export_pos = max(0, pos - 20)
                snippet = content[export_pos:pos]
                is_exported = export_kw in snippet or "export {" in snippet or "export default" in snippet

                if is_exported:
                    jsdoc_line_offset = _count_newlines_before(content, pos) + 1
                    claim = DocClaim(
                        raw_text="",
                        kind=ClaimKind.FUNCTION_SIGNATURE,
                        doc_file=path,
                        line_number=jsdoc_line_offset,
                        name=name,
                        parameters=_parse_param_name(params),
                        metadata={
                            "source": "jsdoc",
                            "category": "no_jsdoc",
                            "kind": kind,
                        },
                    )
                    claims.append(claim)

        return claims
