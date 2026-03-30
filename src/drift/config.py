"""Configuration loading for Drift.

Loads config from .drift.toml files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass
class DriftConfig:
    """Configuration for a drift scan."""

    ignore_patterns: list[str] = field(default_factory=list)
    threshold: float = 0.0
    output_format: Literal["text", "json"] = "text"
    fail_on: Literal["error", "warning", "info", "none"] = "error"
    extractors_enabled: list[str] | None = None  # None = all enabled
    extractors_disabled: list[str] = field(default_factory=list)


def load_config(path: Path | None = None) -> DriftConfig:
    """Load drift configuration from a TOML file.

    Args:
        path: Explicit path to a config file. If None, searches CWD for .drift.toml.
              If the file is pyproject.toml, reads from [tool.drift] section.

    Returns:
        DriftConfig with loaded values or defaults if file is missing/invalid.

    Raises:
        FileNotFoundError: If an explicit path is given but doesn't exist.
        ValueError: If the TOML file is malformed.
    """
    if path is None:
        # Search CWD for .drift.toml, then pyproject.toml
        drift_candidate = Path.cwd() / ".drift.toml"
        if drift_candidate.exists():
            path = drift_candidate
        else:
            pyproject_candidate = Path.cwd() / "pyproject.toml"
            if pyproject_candidate.exists():
                path = pyproject_candidate
            else:
                # No config file found, return defaults
                return DriftConfig()

    if not path.exists():
        if path in (Path.cwd() / ".drift.toml", Path.cwd() / "pyproject.toml"):
            # Search didn't find it, return defaults
            return DriftConfig()
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid TOML in {path}: {e}") from e

    # For pyproject.toml, prefer [tool.drift] section
    is_pyproject = path.name == "pyproject.toml"
    tool_drift = data.get("tool", {}).get("drift", {}) if is_pyproject else {}

    # Determine which dict to read from: tool.drift if available, else top-level
    if tool_drift:
        cfg_data = tool_drift
    else:
        cfg_data = data

    # Extract known keys with defaults
    ignore_patterns = cfg_data.get("ignore_patterns", [])
    if not isinstance(ignore_patterns, list):
        raise ValueError(f"ignore_patterns must be a list in {path}")

    threshold = cfg_data.get("threshold", 0.0)
    if not isinstance(threshold, (int, float)):
        raise ValueError(f"threshold must be a number in {path}")
    threshold = float(threshold)
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"threshold must be between 0.0 and 1.0 in {path}")

    output_format = cfg_data.get("output_format", "text")
    if output_format not in ("text", "json"):
        raise ValueError(f"output_format must be 'text' or 'json' in {path}")

    fail_on = cfg_data.get("fail_on", "error")
    if fail_on not in ("error", "warning", "info", "none"):
        raise ValueError(
            f"fail_on must be 'error', 'warning', 'info', or 'none' in {path}"
        )

    # Parse [extractors] section
    extractors_enabled: list[str] | None = None
    extractors_disabled: list[str] = []
    extractors_section = cfg_data.get("extractors", {})
    if isinstance(extractors_section, dict):
        if "enabled" in extractors_section:
            enabled_val = extractors_section["enabled"]
            if isinstance(enabled_val, list):
                extractors_enabled = enabled_val
            elif enabled_val != "all":
                raise ValueError(
                    f"extractors.enabled must be a list or 'all' in {path}"
                )
        if "disabled" in extractors_section:
            disabled_val = extractors_section["disabled"]
            if isinstance(disabled_val, list):
                extractors_disabled = disabled_val
            else:
                raise ValueError(f"extractors.disabled must be a list in {path}")

    return DriftConfig(
        ignore_patterns=ignore_patterns,
        threshold=threshold,
        output_format=output_format,
        fail_on=fail_on,
        extractors_enabled=extractors_enabled,
        extractors_disabled=extractors_disabled,
    )
