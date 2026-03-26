# Configuration

Drift is configured via files in your project.

## `.driftignore`

Place a `.driftignore` file in the scanned directory to exclude files or directories.

**Format:** One pattern per line (glob-style).

**Example:**

```gitignore
# .driftignore
CHANGELOG.md
docs/*.md
tests/
```

## Output Formats

### Human-Readable (default)

```
drift scan .
```

Produces colored, structured output showing all drift items.

### JSON

```bash
drift scan . --json
```

Machine-readable output for CI/CD integration.

**JSON output structure:**

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

## Drift Categories

| Category | Meaning |
|----------|---------|
| `missing_param` | Parameter exists in code but not in docs |
| `extra_param` | Parameter documented but not in code |
| `type_mismatch` | Parameter type differs between code and docs |
| `default_mismatch` | Default value differs |
| `cli_flag` | Flag documented but not registered |
| `cli_flag_ref` | Registered flag not documented |
