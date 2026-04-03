"""Configuration loading for Drift.

Loads config from .drift.toml files.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


CONFIG_FILENAME = ".drift.toml"


def find_config(start_path: str | Path) -> Optional[Path]:
    """Walk up from start_path looking for .drift.toml.

    Searches each directory from start_path upward toward the filesystem root.
    Returns the first .drift.toml found, or None if no config file exists.

    Args:
        start_path: Directory or file path to begin searching from.

    Returns:
        Path to .drift.toml if found, otherwise None.
    """
    path = Path(start_path).resolve()

    # If start_path is a file, start from its parent directory
    if path.is_file():
        path = path.parent

    # Walk up the directory tree
    while True:
        candidate = path / CONFIG_FILENAME
        if candidate.is_file():
            return candidate

        parent = path.parent
        if parent == path:
            # Reached the filesystem root (parent equals self)
            return None
        path = parent


@dataclass
class DriftConfig:
    """Configuration for a drift scan."""

    ignore_patterns: list[str] = field(default_factory=list)
    threshold: float = 0.0
    output_format: Literal["text", "json"] = "text"
    # fail_on: comma-separated string of category names, or legacy severity keyword
    # Category names: undocumented, missing_param, renamed, fuzzy_renamed,
    #   wrong_default, wrong_type, wrong_return_type, documented_but_missing,
    #   extra_param, signature_mismatch
    # Legacy severity keywords (map to category sets):
    #   error  -> undocumented, missing_param, renamed, fuzzy_renamed,
    #             wrong_default, wrong_type, wrong_return_type
    #   warning -> above + documented_but_missing
    #   info   -> all categories
    #   none   -> no categories (always exit 0)
    fail_on: str = "error"  # backward compat default
    extractors_enabled: list[str] | None = None  # None = all enabled
    extractors_disabled: list[str] = field(default_factory=list)


def load_config(path: Path | None = None) -> DriftConfig:
    """Load drift configuration from a TOML file.

    Args:
        path: Explicit path to a config file. If None, searches upward from CWD
            for .drift.toml using find_config.

    Returns:
        DriftConfig with loaded values or defaults if file is missing/invalid.

    Raises:
        FileNotFoundError: If an explicit path is given but doesn't exist.
        ValueError: If the TOML file is malformed.
    """
    if path is None:
        config_path = find_config(Path.cwd())
        if config_path is None:
            # No config file found, return defaults
            return DriftConfig()
        path = config_path

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid TOML in {path}: {e}") from e

    # Extract [scan] section
    scan_section = data.get("scan", {})
    if not isinstance(scan_section, dict):
        raise ValueError(f"[scan] must be a table in {path}")

    ignore_patterns = scan_section.get("ignore_patterns", [])
    if not isinstance(ignore_patterns, list):
        raise ValueError(f"ignore_patterns must be a list in {path}")

    threshold = data.get("threshold", 0.0)
    if not isinstance(threshold, (int, float)):
        raise ValueError(f"threshold must be a number in {path}")
    threshold = float(threshold)
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"threshold must be between 0.0 and 1.0 in {path}")

    output_format = data.get("output_format", "text")
    if output_format not in ("text", "json"):
        raise ValueError(f"output_format must be 'text' or 'json' in {path}")

    # fail_on: comma-separated category names, or legacy severity keyword
    # (validated in CLI where the actual category expansion happens)
    fail_on = data.get("fail_on", "error")
    if not isinstance(fail_on, str):
        raise ValueError(f"fail_on must be a string in {path}")

    # Parse [extractors] section
    extractors_enabled: list[str] | None = None
    extractors_disabled: list[str] = []
    extractors_section = data.get("extractors", {})
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
