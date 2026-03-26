"""Config file extractor for Drift.

Extracts configuration keys from YAML and TOML files as CONFIG_KEY CodeFacts.
"""

from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


def _flatten_dict(
    d: dict[str, Any],
    prefix: str = "",
    sep: str = ".",
) -> list[tuple[str, Any]]:
    """Flatten a nested dict into dot-notation key paths and leaf values.

    Example:
        {"database": {"host": "localhost", "port": 5432}}
      → [("database.host", "localhost"), ("database.port", 5432)]
    """
    results: list[tuple[str, Any]] = []
    for key, value in d.items():
        full_key = f"{prefix}{sep}{key}" if prefix else key
        if isinstance(value, dict):
            results.extend(_flatten_dict(value, full_key, sep))
        else:
            results.append((full_key, value))
    return results


def _value_type(value: Any) -> str:
    """Return string name of a value's type."""
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


@register
class ConfigFileExtractor(Extractor):
    """Extract CONFIG_KEY facts from YAML and TOML configuration files.

    Parses .yaml, .yml, and .toml files and walks the resulting dict tree,
    producing CodeFact objects with kind="config_key" for each leaf key.
    """

    YAML_EXTS = {".yaml", ".yml"}
    TOML_EXTS = {".toml"}

    def can_handle(self, path: Path) -> bool:
        """Return True for .yaml, .yml, and .toml files."""
        return path.suffix.lower() in self.YAML_EXTS | self.TOML_EXTS

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CONFIG_KEY CodeFacts from a YAML or TOML file."""
        facts: list[CodeFact] = []

        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError):
            return facts

        data: dict[str, Any] | None = None

        if path.suffix.lower() in self.YAML_EXTS:
            data = self._parse_yaml(content)
        elif path.suffix.lower() == ".toml":
            data = self._parse_toml(content)

        if data is None:
            return facts

        flat = _flatten_dict(data)
        for key, value in flat:
            fact = self._build_codefact(key, value, path)
            facts.append(fact)

        return facts

    def _parse_yaml(self, content: str) -> dict[str, Any] | None:
        """Parse YAML content using PyYAML."""
        try:
            import yaml
        except ImportError:
            return None
        try:
            parsed = yaml.safe_load(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _parse_toml(self, content: str) -> dict[str, Any] | None:
        """Parse TOML content using the stdlib tomllib."""
        try:
            import tomllib
        except ImportError:
            return None
        try:
            # tomllib requires bytes on some platforms
            parsed = tomllib.loads(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _build_codefact(
        self,
        key: str,
        value: Any,
        source_file: Path,
    ) -> CodeFact:
        """Build a CodeFact from a config key and its value."""
        val_str = repr(value)
        type_str = _value_type(value)

        params = [
            Parameter(
                name=key,
                type_annotation=type_str,
                default=val_str,
                kind="keyword",
            )
        ]

        return CodeFact(
            name=key,
            kind=FactKind.CONFIG_KEY,
            source_file=source_file,
            line_number=1,
            parameters=params,
            metadata={
                "value": val_str,
                "value_type": type_str,
            },
        )
