# Drift

> Detect when your documentation no longer matches your code.

**Status: v0.5.0**

Drift parses your codebase and your documentation, then tells you exactly where they've diverged.

## Install (development)

```bash
pip install -e ".[dev]"
```

## v0.5.0 Highlights

Drift v0.5.0 adds major new features:

### TypeScript Support
Extract function signatures from `.ts` and `.tsx` files with full JSDoc parsing. Matches TypeScript interfaces, types, and enums against documentation.

### Confidence Scoring
Every drift item now includes a confidence score (0.0–1.0) indicating how likely it is to be real drift vs. a false positive. Use `--min-confidence` to filter:

```bash
drift scan . --min-confidence 0.5
```

### Baseline Diff
Save a baseline of your current drift state, then track only *new* drift items:

```bash
drift scan . --baseline              # Save baseline
drift scan . --baseline              # Show only new drift
drift scan . --update-baseline       # Update baseline to current state
```

### Git-Diff Filtering
Scan only files changed since a git ref:

```bash
drift scan . --diff HEAD~1           # Scan changed files since last commit
drift scan . --diff-branch main      # Scan changed vs main branch
```

### New Output Formats
Additional output formats for CI and tooling:

```bash
drift scan . --json                  # JSON output
drift scan . --sarif                 # SARIF v2.1.0 for GitHub Advanced Security
drift scan . --html                  # Self-contained HTML report
drift scan . --diff-output           # Unified diff showing exact changes needed
drift scan . --patch                 # Git-compatible patches for auto-fixing
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

Drift v0.5.0 was validated by running `drift scan .` on itself (2026-03-30).

**Result: 880+ tests passing**

---

## CLI Flag Detection

Drift v0.4.0+ detects when CLI flags documented in your markdown don't match what your `argparse` or `click` CLI actually registers.

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

## Pre-commit Hook

You can use drift as a pre-commit hook to catch documentation drift before it enters your repo.

### Setup

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        description: Check for documentation drift (blocks commit if drift found)
        entry: drift check
        language: system
        pass_filenames: true
        types: [python]
```

### With auto-fix (experimental)

For extractors that support auto-fixing:

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        entry: drift check
        language: system
        pass_filenames: true
        types: [python]
      - id: drift-fix
        name: drift (auto-fix)
        entry: drift fix
        language: system
        pass_filenames: false
        stages: [commit]
        types: [python]
```

### Hook options

| Hook ID | Description | Exit code |
|---------|-------------|-----------|
| `drift-check` | Check for documentation drift | 0 = clean, 1 = drift found |

## CI Integration

Drift can be integrated into GitHub Actions using the official composite action.

### Setup

Copy `.github/actions/drift-check/action.yml` to your repository and add a workflow:

```yaml
# .github/workflows/drift.yml
name: Documentation Drift Check

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  drift-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/drift-check
        with:
          paths: .
          fail-on: error
```

### Inputs

| Input | Description | Default |
|-------|-------------|---------|
| `paths` | Paths to scan | `.` |
| `severity` | Minimum severity to report (error, warning, info, all) | `all` |
| `fail-on` | Exit code 1 when drift at this severity (error, warning, info, none) | `error` |

### SARIF Support

Drift's GitHub Action uploads results as SARIF, enabling GitHub's code scanning alerts integration. Results appear in the Security tab of your repository.

See `.github/actions/drift-check/action.yml` for the full action definition.

## Extending with Plugins

Drift supports **third-party extractors** via the `drift.extractors` entry_point group. See [docs/plugins.md](docs/plugins.md) for the full plugin authoring guide.

Example `pyproject.toml` addition for a plugin package:

```toml
[project.entry-points."drift.extractors"]
my-extractor = "my_package.extractor:MyExtractor"
```

After installing the plugin package, `drift list-extractors` will show it alongside built-in extractors, and `drift scan` will use it automatically.

## Development

```bash
pytest
```
