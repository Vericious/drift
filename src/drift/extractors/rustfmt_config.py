"""Rustfmt config extractor for Drift — DRIFT-249.

Extracts formatting rules from rustfmt.toml configuration files.
"""

from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


@register
class RustfmtConfigExtractor(Extractor):
    """Extractor for rustfmt.toml configuration files.

    Extracts rustfmt.toml keys as CONFIG_KEY CodeFacts.
    Handles both standard rustfmt options and edition/requires.
    """

    def can_handle(self, path: Path) -> bool:
        return path.name == "rustfmt.toml"

    def extract(self, path: Path) -> list[CodeFact]:
        facts: list[CodeFact] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return facts

        data = self._parse(content)
        if data is None:
            return facts

        flat = self._flatten_dict(data)
        for key, value in flat:
            facts.append(self._make_fact(key, value, path))

        return facts

    def _parse(self, content: str) -> dict[str, Any] | None:
        """Parse rustfmt.toml content using tomllib."""
        import tomllib

        try:
            return tomllib.loads(content)
        except Exception:
            return None

    def _flatten_dict(
        self,
        d: dict[str, Any],
        prefix: str = "",
    ) -> list[tuple[str, Any]]:
        """Flatten nested dict into dot-notation key paths."""
        results: list[tuple[str, Any]] = []
        for key, value in d.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                results.extend(self._flatten_dict(value, full_key))
            else:
                results.append((full_key, value))
        return results

    def _make_fact(
        self,
        key: str,
        value: Any,
        source_file: Path,
    ) -> CodeFact:
        val_str = repr(value)
        type_str = self._value_type(value)

        params = [
            Parameter(
                name=key,
                type_annotation=type_str,
                default=val_str,
                kind="keyword",
            )
        ]

        return CodeFact(
            name=f"rustfmt.{key}",
            kind=FactKind.CONFIG_KEY,
            source_file=source_file,
            line_number=1,
            parameters=params,
            metadata={
                "value": val_str,
                "value_type": type_str,
                "section": "rustfmt",
            },
        )

    def _value_type(self, value: Any) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, list):
            return "list"
        if value is None:
            return "null"
        return type(value).__name__
