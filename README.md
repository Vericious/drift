# Drift

> Detect when your documentation no longer matches your code.

**Status: Pre-Alpha (v0.3.0)**

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

Drift v0.3.0 was validated by running `drift scan .` on itself (2026-03-26).

**Result: 161 tests passing**

---

## CLI Flag Detection

Drift v0.3.0+ detects when CLI flags documented in your markdown don't match what your `argparse` or `click` CLI actually registers.

### Example

Your `README.md` says:
```markdown
## Usage

    mytool --verbose  # Enable verbose output
```

But your `cli.py` doesn't register `--verbose`:
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--quiet", action="store_true")  # No --verbose!
```

Running `drift scan .` will report:
```
error: cli_flag 'verbose' documented but not registered in code
  claim: --verbose (README.md:10)
  fact:  available flags are --quiet
```

### What drift detects for CLI

| Category | Meaning |
|----------|---------|
| **cli_flag** | Flag documented in markdown but not registered in argparse/click |
| **cli_flag_ref** | Registered flag not mentioned in docs |

Drift extracts CLI facts from Python files using `argparse.ArgumentParser.add_argument()` and `click.option()` decorators.

## Development

```bash
pytest
```
