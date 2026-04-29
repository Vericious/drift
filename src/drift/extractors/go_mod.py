"""Go go.mod extractor for Drift — DRIFT-250.

Extracts module name, Go version, and dependencies from go.mod files.
"""

from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


@register
class GoModExtractor(Extractor):
    """Extractor for Go go.mod files.

    Extracts:
      - module name (module github.com/user/project)
      - go version (go 1.21)
      - require dependencies (require ...indirect suffix)
      - replace/exclude directives
    """

    def can_handle(self, path: Path) -> bool:
        return path.name == "go.mod"

    def extract(self, path: Path) -> list[CodeFact]:
        facts: list[CodeFact] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return facts

        lines = content.split("\n")
        in_require_block = False
        i = 0
        n = len(lines)

        while i < n:
            raw_line = lines[i]
            line = raw_line.strip()
            orig_line_no = i + 1

            if not line or line.startswith("#"):
                i += 1
                continue

            # Handle require block opening
            if line.startswith("require ("):
                in_require_block = True
                i += 1
                continue

            # Handle require block closing
            if in_require_block:
                if line == ")":
                    in_require_block = False
                    i += 1
                    continue
                # Inside require block — parse each dependency
                parts = line.split()
                if parts:
                    mod = parts[0]
                    version = parts[1] if len(parts) > 1 else ""
                    is_indirect = "// indirect" in raw_line
                    facts.append(self._make_fact(
                        f"go.mod.require.{mod}",
                        version,
                        path,
                        orig_line_no,
                        {"module": mod, "version": version, "indirect": is_indirect, "section": "go.mod.require"},
                    ))
                i += 1
                continue

            if line.startswith("go "):
                facts.append(self._make_fact(
                    "go.mod.go_version",
                    line[2:].strip(),
                    path,
                    orig_line_no,
                    {"key": "go", "section": "go.mod"},
                ))
                i += 1
                continue
            elif line.startswith("module "):
                facts.append(self._make_fact(
                    "go.mod.module",
                    line[7:].strip(),
                    path,
                    orig_line_no,
                    {"key": "module", "section": "go.mod"},
                ))
                i += 1
                continue
            elif line.startswith("replace "):
                # replace module => replacement version
                parts = line[8:].split("=>")
                if parts:
                    orig = parts[0].strip()
                    repl = parts[1].strip() if len(parts) > 1 else ""
                    facts.append(self._make_fact(
                        f"go.mod.replace.{orig}",
                        repl,
                        path,
                        orig_line_no,
                        {"original": orig, "replacement": repl, "section": "go.mod.replace"},
                    ))
                i += 1
                continue
            elif line.startswith("exclude "):
                # exclude module version
                parts = line[8:].split()
                if parts:
                    mod = parts[0]
                    version = parts[1] if len(parts) > 1 else ""
                    facts.append(self._make_fact(
                        f"go.mod.exclude.{mod}",
                        version,
                        path,
                        orig_line_no,
                        {"module": mod, "version": version, "section": "go.mod.exclude"},
                    ))
                i += 1
                continue

            i += 1

        return facts

    def _make_fact(
        self,
        name: str,
        value: str,
        source_file: Path,
        line_number: int,
        metadata: dict[str, Any],
    ) -> CodeFact:
        meta = dict(metadata)
        meta["value"] = value
        meta["value_type"] = "str"

        return CodeFact(
            name=name,
            kind=FactKind.CONFIG_KEY,
            source_file=source_file,
            line_number=line_number,
            parameters=[
                Parameter(name="value", type_annotation="str", default=repr(value), kind="keyword"),
            ],
            metadata=meta,
        )
