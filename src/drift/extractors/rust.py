"""Rust extractor for Drift — DRIFT-238.

Extracts Rust declarations from .rs files:
- fn declarations (top-level and methods)
- struct, enum, trait, impl blocks

Handles doc comments:
- Outer doc comments (/// and /** */) attach to the following item
- Inner doc comments (//! and /*!! */) attach to the enclosing item

Produces CodeFact objects with metadata['lang']='rust'.
"""

import re
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


@register
class RustExtractor(Extractor):
    """Extractor for Rust source files."""

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() == ".rs"

    def extract(self, file_path: Path) -> list[CodeFact]:
        source = file_path.read_text()
        return self._extract_facts(source, file_path)

    # ------------------------------------------------------------------
    # Public extraction API
    # ------------------------------------------------------------------

    def _extract_facts(self, source: str, file_path: Path) -> list[CodeFact]:
        facts: list[CodeFact] = []
        lines = source.split("\n")
        n = len(lines)

        i = 0
        doc_text = ""
        doc_end = -1
        while i < n:
            stripped = lines[i].strip()

            # Skip blank lines
            if not stripped:
                i += 1
                continue

            # Skip inner doc comments (//! and /*!! */) and regular comments
            if stripped.startswith("//!") or stripped.startswith("/*!!"):
                i += 1
                continue
            if stripped.startswith("//") and not stripped.startswith("///"):
                i += 1
                continue

            # Skip preprocessor / inner-attribute lines
            if stripped.startswith("#["):
                i += 1
                continue

            # Collect leading outer doc comments (/// or /** */)
            # Only re-collect if doc_end < i (we've moved past the last doc position).
            # If doc_end >= i, we've either just collected (doc_end == i) or
            # are inside a block body (doc_end > i) — keep existing doc_text.
            if doc_end < i:
                _doc_text, _doc_end = self._collect_leading_outer_docs(lines, i)
                # Only update doc_text if we actually found new docs; don't wipe
                # out stale doc_text when re-collecting at a non-doc position.
                if _doc_text:
                    doc_text = _doc_text
                    doc_end = _doc_end

            # decl_idx: point to the declaration line.
            # If we found doc comments (doc_end > i): decl_idx = doc_end + 1
            #   to skip all consecutive doc lines and land on the declaration.
            # If doc_end == i (we're at a non-doc line after finding docs):
            #   use doc_end to stay at the last doc position for the next match.
            # If doc_end < i or doc_end == -1 (no docs found yet): decl_idx = i.
            if doc_end > i:
                decl_idx = doc_end + 1
            elif doc_end == i:
                decl_idx = doc_end  # use the last doc position for this item
            else:
                decl_idx = i

            # Now `stripped` is the declaration
            stripped = lines[decl_idx].strip()

            if not stripped:
                i += 1
                continue

            matched = False

            # Struct
            m = self._match_struct(stripped)
            if m:
                name = m.group(1)
                body_start = self._find_block_end(lines, decl_idx)
                inner = self._collect_inner_docs_in_block(lines, decl_idx, body_start)
                fact = self._make_struct_fact(
                    name, file_path, decl_idx + 1,
                    doc_text if doc_text else None,
                    inner.get("doc"),
                    {},
                )
                facts.append(fact)
                # Also extract items inside the struct body
                nested = self._extract_items_in_block(lines, decl_idx + 1, body_start - 1, file_path)
                facts.extend(nested)
                i = body_start + 1
                # Reset so doc_text doesn't leak into next iteration
                doc_text = ""
                doc_end = -1
                continue

            # Enum
            m = self._match_enum(stripped)
            if m:
                name = m.group(1)
                body_start = self._find_block_end(lines, decl_idx)
                inner = self._collect_inner_docs_in_block(lines, decl_idx, body_start)
                fact = self._make_enum_fact(
                    name, file_path, decl_idx + 1,
                    doc_text if doc_text else None,
                    inner.get("doc"),
                    {},
                )
                facts.append(fact)
                i = body_start + 1
                doc_text = ""
                doc_end = -1
                continue

            # Trait
            m = self._match_trait(stripped)
            if m:
                name = m.group(1)
                body_start = self._find_block_end(lines, decl_idx)
                inner = self._collect_inner_docs_in_block(lines, decl_idx, body_start)
                fact = self._make_trait_fact(
                    name, file_path, decl_idx + 1,
                    doc_text if doc_text else None,
                    inner.get("doc"),
                    {},
                )
                facts.append(fact)
                # Also extract items inside the trait body
                nested = self._extract_items_in_block(lines, decl_idx + 1, body_start - 1, file_path)
                facts.extend(nested)
                i = body_start + 1
                doc_text = ""
                doc_end = -1
                continue

            # Impl
            m = self._match_impl(stripped)
            if m:
                impl_name = m.group(1)  # e.g. "Serializable"
                type_name = m.group(2) if m.group(2) else impl_name  # e.g. "User"
                body_start = self._find_block_end(lines, decl_idx)
                inner = self._collect_inner_docs_in_block(lines, decl_idx, body_start)
                fact = self._make_impl_fact(
                    type_name, file_path, decl_idx + 1,
                    doc_text if doc_text else None,
                    inner.get("doc"),
                    {"impl_trait": impl_name} if impl_name != type_name else {},
                )
                facts.append(fact)
                # Also extract methods inside the impl body
                nested = self._extract_items_in_block(lines, decl_idx + 1, body_start - 1, file_path)
                facts.extend(nested)
                i = body_start + 1
                doc_text = ""
                doc_end = -1
                continue

            # Function / method
            m = self._match_fn(stripped)
            if m:
                name = m.group("name")
                params_str = m.group("params") or ""
                return_type = m.group("return_type")
                params = self._parse_rust_params(params_str)
                ret = return_type.strip() if return_type else None
                fn_body = self._find_block_end(lines, decl_idx)
                inner = self._collect_inner_docs_in_block(lines, decl_idx, fn_body)
                fact = self._make_fn_fact(
                    name, file_path, decl_idx + 1,
                    doc_text if doc_text else None,
                    params, ret,
                    inner_docs=inner.get("doc"),
                    metadata={},
                )
                facts.append(fact)
                i = fn_body + 1
                doc_text = ""
                doc_end = -1
                continue

            # No match: preserve doc_end so the next item's docs (at the next position)
            # can still be found. We only advance past the non-doc line.
            i += 1

        return facts

    def _extract_items_in_block(
        self, lines: list[str], start: int, end: int, file_path: Path
    ) -> list[CodeFact]:
        """Extract function/method facts from within a block (struct body, impl body, etc.).

        Only looks for fn declarations. Does NOT collect outer docs (since those
        would be for struct/enum/impl members, not the fn itself in this context).
        """
        facts: list[CodeFact] = []
        n = len(lines)
        if start > end:
            return facts

        i = start
        while i <= end and i < n:
            stripped = lines[i].strip()

            # Skip blank lines, inner docs, regular comments, attributes, outer docs
            if not stripped:
                i += 1
                continue
            if stripped.startswith("//!") or stripped.startswith("/*!!"):
                i += 1
                continue
            if stripped.startswith("//") and not stripped.startswith("///"):
                i += 1
                continue
            if stripped.startswith("#["):
                i += 1
                continue

            # Skip outer doc comments — they are not fn declarations
            if stripped.startswith("///") or (stripped.startswith("/**") and not stripped.startswith("/**/")):
                i += 1
                continue

            # Only look for fn declarations within this block
            m = self._match_fn(stripped)
            if m:
                name = m.group("name")
                params_str = m.group("params") or ""
                return_type = m.group("return_type")
                params = self._parse_rust_params(params_str)
                ret = return_type.strip() if return_type else None
                fn_body = self._find_block_end(lines, i)
                fact = self._make_fn_fact(
                    name, file_path, i + 1,
                    None,  # no outer docs in block context
                    params, ret,
                    metadata={},
                )
                facts.append(fact)
                i = fn_body + 1
                continue

            # For other block items (nested struct, enum, etc.), find block end and skip
            m_struct = self._match_struct(stripped)
            m_enum = self._match_enum(stripped)
            m_trait = self._match_trait(stripped)
            m_impl = self._match_impl(stripped)
            if m_struct or m_enum or m_trait or m_impl:
                block_end = self._find_block_end(lines, i)
                i = block_end + 1
                continue

            i += 1

        return facts

    # ------------------------------------------------------------------
    # Matching helpers
    # ------------------------------------------------------------------

    def _match_struct(self, line: str):
        return re.match(
            r"(?:pub\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)",
            line,
        )

    def _match_enum(self, line: str):
        return re.match(
            r"(?:pub\s+)?enum\s+([A-Za-z_][A-Za-z0-9_]*)",
            line,
        )

    def _match_trait(self, line: str):
        return re.match(
            r"(?:pub\s+)?trait\s+([A-Za-z_][A-Za-z0-9_]*)",
            line,
        )

    def _match_impl(self, line: str):
        # impl [Trait for] Type  or  impl Type
        return re.match(
            r"impl\s+(?:<[^>]+>\s+)?(?:([A-Za-z_][A-Za-z0-9_]*)\s+for\s+)?([A-Za-z_][A-Za-z0-9_]*)",
            line,
        )

    def _match_fn(self, line: str):
        return re.match(
            r"(?:pub\s+)?(?:async\s+)?fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
            r"(?:\s*<[^>]+>)?\s*\((?P<params>[^)]*)\)"
            r"(?:\s*->\s*(?P<return_type>[^{]+))?",
            line,
        )

    # ------------------------------------------------------------------
    # Doc comment helpers
    # ------------------------------------------------------------------

    def _collect_leading_outer_docs(self, lines: list[str], start: int) -> tuple[str, int]:
        """Collect consecutive /// lines and /** */ block docs starting at `start`.

        Returns (joined_doc_text, index_of_last_doc_line).
        If no doc comments found, returns ("", start).
        """
        doc_lines = []
        i = start
        n = len(lines)
        while i < n:
            stripped = lines[i].strip()
            if stripped.startswith("///"):
                doc_lines.append(stripped[3:].strip())
                i += 1
            elif stripped.startswith("/**") and not stripped.startswith("/**/"):
                # Block doc comment — collect until we hit */
                block_lines = []
                j = i
                open_block = False
                while j < n:
                    block_stripped = lines[j].strip()
                    if not open_block:
                        if block_stripped.startswith("/**"):
                            open_block = True
                            block_lines.append(block_stripped[3:].rstrip("*/").strip())
                        j += 1
                        continue
                    # Inside block
                    if block_stripped.endswith("*/"):
                        block_lines.append(block_stripped[:-2].strip())
                        j += 1
                        break
                    block_lines.append(block_stripped)
                    j += 1
                doc_lines.append(" ".join(block_lines))
                i = j
            else:
                break
        if doc_lines:
            return " ".join(doc_lines), i - 1
        return "", start

    def _collect_inner_docs_in_block(
        self, lines: list[str], decl_idx: int, block_end: int
    ) -> dict[str, Any]:
        """Collect //! and /*!! */ inner docs inside a block.

        The block starts at the opening { of the declaration at decl_idx
        and ends at block_end (inclusive).
        Returns {"doc": docstring} if inner docs found, else {}.
        """
        # Find opening brace
        brace_idx = -1
        for idx in range(decl_idx, min(decl_idx + 5, len(lines))):
            if "{" in lines[idx]:
                brace_idx = idx
                break
        if brace_idx < 0 or brace_idx >= block_end:
            return {}

        doc_parts = []
        for idx in range(brace_idx + 1, block_end):
            stripped = lines[idx].strip()
            if stripped.startswith("//!"):
                doc_parts.append(stripped[3:].strip())
            elif stripped.startswith("/*!!"):
                content = stripped[4:].strip()
                if content.endswith("*/"):
                    content = content[:-2].strip()
                doc_parts.append(content)

        if doc_parts:
            return {"doc": " ".join(doc_parts)}
        return {}

    # ------------------------------------------------------------------
    # Block navigation
    # ------------------------------------------------------------------

    def _find_block_end(self, lines: list[str], start: int) -> int:
        """Find the line index of the closing } for a block starting at `start`."""
        depth = 0
        for idx in range(start, len(lines)):
            depth += lines[idx].count("{") - lines[idx].count("}")
            if depth == 0 and idx > start:
                return idx
        return len(lines) - 1

    # ------------------------------------------------------------------
    # Parameter parsing
    # ------------------------------------------------------------------

    def _parse_rust_params(self, params_str: str) -> list[Parameter]:
        params = []
        if not params_str.strip():
            return params
        parts = self._split_params(params_str)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Skip receiver
            if re.match(r"&?(?:mut\s+)?self\b", part):
                continue
            m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)", part)
            if m:
                name = m.group(1)
                type_ann = m.group(2).rstrip(",").strip()
                params.append(Parameter(name=name, type_annotation=type_ann))
            else:
                m2 = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", part)
                if m2:
                    params.append(Parameter(name=m2.group(1)))
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
    # Fact constructors
    # ------------------------------------------------------------------

    def _make_fn_fact(
        self,
        name: str,
        file_path: Path,
        line: int,
        docstring: str | None,
        parameters: list[Parameter],
        return_type: str | None,
        inner_docs: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CodeFact:
        meta = dict(metadata or {})
        meta["lang"] = "rust"
        final_doc = docstring
        if inner_docs:
            meta["inner_docstring"] = inner_docs
            if final_doc:
                final_doc = final_doc + "\n" + inner_docs
            else:
                final_doc = inner_docs
        return CodeFact(
            name=name,
            kind=FactKind.FUNCTION,
            source_file=file_path,
            line_number=line,
            parameters=parameters,
            return_type=return_type,
            docstring=final_doc,
            metadata=meta,
        )

    def _make_struct_fact(
        self,
        name: str,
        file_path: Path,
        line: int,
        docstring: str | None,
        inner_docs: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CodeFact:
        meta = dict(metadata or {})
        meta["lang"] = "rust"
        meta["rust_kind"] = "struct"
        final_doc = docstring
        if inner_docs:
            meta["inner_docstring"] = inner_docs
            if final_doc:
                final_doc = final_doc + "\n" + inner_docs
            else:
                final_doc = inner_docs
        return CodeFact(
            name=name,
            kind=FactKind.CLASS,
            source_file=file_path,
            line_number=line,
            docstring=final_doc,
            metadata=meta,
        )

    def _make_enum_fact(
        self,
        name: str,
        file_path: Path,
        line: int,
        docstring: str | None,
        inner_docs: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CodeFact:
        meta = dict(metadata or {})
        meta["lang"] = "rust"
        meta["rust_kind"] = "enum"
        final_doc = docstring
        if inner_docs:
            meta["inner_docstring"] = inner_docs
            if final_doc:
                final_doc = final_doc + "\n" + inner_docs
            else:
                final_doc = inner_docs
        return CodeFact(
            name=name,
            kind=FactKind.CLASS,
            source_file=file_path,
            line_number=line,
            docstring=final_doc,
            metadata=meta,
        )

    def _make_trait_fact(
        self,
        name: str,
        file_path: Path,
        line: int,
        docstring: str | None,
        inner_docs: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CodeFact:
        meta = dict(metadata or {})
        meta["lang"] = "rust"
        meta["rust_kind"] = "trait"
        final_doc = docstring
        if inner_docs:
            meta["inner_docstring"] = inner_docs
            if final_doc:
                final_doc = final_doc + "\n" + inner_docs
            else:
                final_doc = inner_docs
        return CodeFact(
            name=name,
            kind=FactKind.CLASS,
            source_file=file_path,
            line_number=line,
            docstring=final_doc,
            metadata=meta,
        )

    def _make_impl_fact(
        self,
        name: str,
        file_path: Path,
        line: int,
        docstring: str | None,
        inner_docs: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CodeFact:
        meta = dict(metadata or {})
        meta["lang"] = "rust"
        meta["rust_kind"] = "impl"
        final_doc = docstring
        if inner_docs:
            meta["inner_docstring"] = inner_docs
            if final_doc:
                final_doc = final_doc + "\n" + inner_docs
            else:
                final_doc = inner_docs
        return CodeFact(
            name=name,
            kind=FactKind.CLASS,
            source_file=file_path,
            line_number=line,
            docstring=final_doc,
            metadata=meta,
        )
