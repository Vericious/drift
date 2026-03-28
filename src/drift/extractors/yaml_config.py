"""YAML configuration file extractor for Drift.

Extracts CONFIG_KEY facts from YAML files following TerraformExtractor pattern.
Handles: docker-compose.yml, app.yml, config.yml, .gitlab-ci.yml, and other YAML configs.
Uses PyYAML (already available via pydantic) or stdlib yaml module.
"""

from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import CodeFact, FactKind, Parameter


def _flatten_dict(d: dict, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Flatten a nested dict into dot-notation keys.
    
    Handles both dict and list values:
      - dict values are recursively flattened
      - list values are indexed: key.0, key.1, key.2, etc.
    """
    items: list[tuple[str, Any]] = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            for i, item in enumerate(v):
                list_key = f"{new_key}{sep}{i}"
                if isinstance(item, dict):
                    items.extend(_flatten_dict(item, list_key, sep=sep).items())
                else:
                    items.append((list_key, item))
        else:
            items.append((new_key, v))
    return dict(items)


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
class YamlConfigExtractor(Extractor):
    """Extract CONFIG_KEY facts from YAML configuration files.

    Handles common YAML config formats including:
      - docker-compose.yml (services, volumes, networks)
      - app.yml / config.yml (application settings)
      - .gitlab-ci.yml (stages, jobs, variables)
      - kubernetes manifests (kind, metadata.name)
      - generic nested YAML configurations

    Fact naming follows dot-notation for nested keys:
      services.db.image
      database.host
      stages.0 (for list items)
    """

    YAML_EXTS = {".yaml", ".yml"}

    def can_handle(self, path: Path) -> bool:
        """Return True for .yaml and .yml files."""
        return path.suffix.lower() in self.YAML_EXTS

    def extract(self, path: Path) -> list[CodeFact]:
        """Extract CONFIG_KEY CodeFacts from a YAML file."""
        facts: list[CodeFact] = []

        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return facts

        data = self._parse_yaml(content)
        if data is None:
            return facts

        if not isinstance(data, dict):
            return facts

        # Flatten and extract facts
        flat = _flatten_dict(data)

        # Detect YAML structure type for metadata
        yaml_kind = self._detect_yaml_kind(data)

        for key, value in flat.items():
            fact = self._build_codefact(key, value, path, yaml_kind)
            facts.append(fact)

        return facts

    def _parse_yaml(self, content: str) -> dict[str, Any] | None:
        """Parse YAML content using stdlib yaml or PyYAML."""
        try:
            import yaml
            HAS_YAML = True
        except ImportError:
            HAS_YAML = False

        if not HAS_YAML:
            return None

        try:
            parsed = yaml.safe_load(content)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    def _detect_yaml_kind(self, data: dict) -> str:
        """Detect the kind of YAML structure for metadata purposes."""
        # Docker Compose
        if "services" in data:
            return "docker-compose"
        # GitLab CI
        if "stages" in data or "job" in data or "jobs" in data:
            return "gitlab-ci"
        # Kubernetes
        if "apiVersion" in data or "kind" in data:
            return "kubernetes"
        # Generic
        return "generic"

    def _build_codefact(
        self,
        key: str,
        value: Any,
        source_file: Path,
        yaml_kind: str = "generic",
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
                "yaml_kind": yaml_kind,
            },
        )
