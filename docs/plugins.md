# Plugin System

Drift supports **third-party extractors** via the standard Python `entry_points` mechanism. Plugin extractors are auto-discovered at startup and participate in the normal scan pipeline alongside built-in extractors.

## How It Works

When `drift scan` runs, Drift calls `entry_points(group="drift.extractors")` to discover any installed plugins. Each plugin must expose an `Extractor` subclass and register it using the `@register` decorator.

## Creating a Plugin

### 1. Define Your Extractor

```python
# my_drift_plugin/extractor.py
from pathlib import Path
from typing import Any

from drift.extractors.base import Extractor
from drift.extractors.registry import register
from drift.models import ClaimKind, DocClaim, Parameter


@register
class MyExtractor(Extractor):
    """Extract custom documentation claims from my format."""

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix == ".myext"

    def extract(self, file_path: Path) -> list[Any]:
        claims: list[DocClaim] = []
        # ... extract claims from file_path ...
        return claims
```

### 2. Declare the Entry Point

In your plugin's `pyproject.toml`:

```toml
[project]
name = "drift-my-plugin"
version = "0.1.0"

[project.entry-points."drift.extractors"]
# The key (e.g. "my-extractor") is shown in `drift list-extractors`
# The value is "module.path:ClassName"
my-extractor = "my_drift_plugin.extractor:MyExtractor"
```

The entry point value uses the format `module.path:ClassName` where `ClassName` is the exact name of your Extractor subclass.

### 3. Install in Development Mode

```bash
pip install -e .
# or
pip install my_drift_plugin
```

## Verifying Plugin Discovery

Use `drift list-extractors` to confirm your plugin is loaded:

```bash
$ drift list-extractors
Drift Extractors
┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┓
┃ Name                     ┃ Source   ┃ Handles ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━┩
│ DocstringExtractor       │ built-in │ *       │
│ MyExtractor              │ plugin   │ *.myext │
│ ...
└──────────────────────────┴──────────┴─────────┘

10 extractor(s) loaded
```

## Plugin Extractor Requirements

- **Subclass `Extractor`** from `drift.extractors.base`
- **Use `@register`** decorator (imported from `drift.extractors.registry`)
- **`can_handle(path)`** — return `True` for files this extractor handles
- **`extract(path)`** — return a list of `DocClaim` and/or `CodeFact` objects

### Claim and Fact Objects

```python
from drift.models import ClaimKind, DocClaim, Parameter

# Create a parameter (for parameter documentation claims)
param = Parameter(
    name="param_name",
    type_annotation="str",      # optional
    default=None,              # optional
    kind="keyword",             # "positional", "keyword", "varargs", "varkw"
)

# Create a documentation claim
claim = DocClaim(
    raw_text="The raw documentation text",
    kind=ClaimKind.FUNCTION_SIGNATURE,  # or RETURN_DESCRIPTION, PARAMETER_DESCRIPTION, etc.
    doc_file=Path("README.md"),
    line_number=42,
    name="my_function",         # optional
    parameters=[param],         # optional
)
```

### Available ClaimKind Values

- `FUNCTION_SIGNATURE` — function/class signature documentation
- `PARAMETER_DESCRIPTION` — parameter documentation
- `RETURN_DESCRIPTION` — return value documentation
- `CODE_EXAMPLE` — code examples in documentation
- `CLI_USAGE` — CLI usage documentation
- `CLI_FLAG_REF` — CLI flag references
- `CONFIG_REF` — configuration references

### Error Handling

Your `extract()` method should handle errors gracefully. If it raises an exception, Drift's `--strict` flag controls whether the scan fails or the error is logged and the file is skipped.

```python
def extract(self, file_path: Path) -> list[Any]:
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []  # Return empty list for unreadable files
    # ...
```

## Debugging Plugin Loading

If your plugin isn't being discovered, check:

1. **Is the package installed?** Run `pip list | grep drift` and your plugin package.
2. **Is the entry point correct?** Check `[project.entry-points."drift.extractors"]` in your `pyproject.toml`.
3. **Does the Extractor class exist?** Make sure `module.path:ClassName` points to the right class.
4. **Does it inherit from Extractor?** Only `Extractor` subclasses are auto-discovered.
5. **Is it registered?** The `@register` decorator must be applied to the class.
