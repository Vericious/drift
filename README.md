# Drift

> Detect when your documentation no longer matches your code.

**Status: Pre-Alpha (v0.1.0)**

Drift parses your codebase and your documentation, then tells you exactly where they've diverged.

## Install (development)

```bash
pip install -e ".[dev]"
```

## Usage

### `drift scan [PATH]`

Scan a project for documentation drift. PATH defaults to `.` (current directory).

```bash
drift scan .
```

Drift will:
1. Extract **facts** — function signatures from `.py` files
2. Extract **claims** — documented signatures from `.md` files
3. Match them and report mismatches as **drift items**

### `drift scan [PATH] --json`

Output results as JSON for machine consumption.

```bash
drift scan . --json
```

JSON output structure:
```json
{
  "scanned_path": ".",
  "summary": {
    "facts": 5,
    "claims": 3,
    "drift_items": 2,
    "errors": 1,
    "warnings": 1
  },
  "has_drift": true,
  "drift_items": [
    {
      "severity": "error",
      "category": "missing_param",
      "message": "Parameter 'b' in my_func is not documented",
      "suggestion": "Add 'b' to docs for my_func",
      "fact": { "name": "my_func", "kind": "function", ... },
      "claim": { "name": "my_func", ... }
    }
  ]
}
```

### Understanding the output

Drift reports two severity levels:

| Severity | Meaning |
|----------|---------|
| **Error** | Signature mismatch — docs and code clearly disagree |
| **Warning** | Possible drift — default value or type differs |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | No drift detected |
| `1` | Drift detected (error-severity mismatch found) |
| `2` | Invalid arguments / path not found |

### `.driftignore`

Place a `.driftignore` file in the scanned directory to exclude specific files or patterns. One pattern per line (simple `.gitignore`-style globs supported).

```
# .driftignore
CHANGELOG.md
docs/*.md
```

## Self-check

Drift v0.2.0 was validated by running `drift scan .` on itself (2026-03-25).

**Result: 44 errors, 214 warnings**

The detected drift is primarily false positives from:

- **Test fixtures**: Test helper functions and pytest fixtures are not meant to be documented
- **Private methods**: Internal `_` prefixed methods and `__init__`, `__repr__` etc. are excluded from documentation expectations
- **Markdown code blocks**: Example code in documentation like `func(a, b, c)` gets picked up as claims for non-existent functions
- **PLAN.md examples**: Example signatures used in planning docs

The meaningful errors (real drift requiring attention):

| Category | Count | Notes |
|----------|-------|-------|
| `scan` missing params in docs | 3 | CLI `scan()` function parameters not documented |
| `DriftReport.has_drift` missing `self` | 1 | Method's `self` param not documented |
| `load_config` return type missing | 1 | Return type annotation missing in docstring |

These are acceptable for v0.2.0 — internal APIs and CLI interfaces don't require the same documentation rigor as public library APIs.

## Development

```bash
pytest
```
