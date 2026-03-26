# Drift

> Detect when your documentation no longer matches your code.

**Status: Pre-Alpha (v0.4.0)**

Drift parses your codebase and your documentation, then tells you exactly where they've diverged.

## Install

```bash
pip install drift
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
drift scan .
```

Drift will:

1. **Extract facts** — function signatures from `.py` files
2. **Extract claims** — documented signatures from `.md` files
3. **Match them** and report mismatches as **drift items**

## Understanding the Output

Drift reports two severity levels:

| Severity | Meaning |
|----------|---------|
| **Error** | Signature mismatch — docs and code clearly disagree |
| **Warning** | Possible drift — default value or type differs |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No drift detected |
| `1` | Drift detected (error-severity mismatch found) |
| `2` | Invalid arguments / path not found |

## Ignoring Files

Place a `.driftignore` file in the scanned directory to exclude specific files or patterns:

```gitignore
# .driftignore
CHANGELOG.md
docs/*.md
```

One pattern per line — simple `.gitignore`-style globs supported.

## Self-Check

Drift v0.4.0 was validated by running `drift scan .` on itself (2026-03-26).

**Result: 161 tests passing**
