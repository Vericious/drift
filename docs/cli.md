# CLI Reference

## `drift scan`

Scan a project for documentation drift.

```bash
drift scan [PATH] [OPTIONS]
```

**Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `PATH` | Directory to scan | `.` (current directory) |

**Options:**

| Flag | Description |
|------|-------------|
| `--json` | Output results as JSON |

## CLI Flag Detection

Drift v0.4.0+ detects when CLI flags documented in markdown don't match your actual `argparse` or `click` CLI.

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

### What Drift Detects

| Category | Meaning |
|----------|---------|
| `cli_flag` | Flag documented in markdown but not registered |
| `cli_flag_ref` | Registered flag not mentioned in docs |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | No drift detected |
| `1` | Drift detected (error-severity mismatch found) |
| `2` | Invalid arguments / path not found |
