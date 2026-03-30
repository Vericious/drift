# Pre-commit Hooks

Use drift as a pre-commit hook to catch documentation drift before it enters your repo.

## Quick Start

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

## Checking Only Changed Files

By default, `drift check` scans all files. In a pre-commit context, you typically want to check only the files that changed in this commit. Use `--diff HEAD~1`:

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        description: Check for documentation drift in changed files
        entry: drift check --diff HEAD~1
        language: system
        pass_filenames: true
        types: [python]
```

This compares each file against `HEAD~1` (the commit before the current one) and only reports drift in files that were modified.

## Reducing Noise with Confidence Threshold

Some extractors may produce low-confidence signals. Use `--min-confidence` to filter:

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        description: Check for high-confidence documentation drift
        entry: drift check --diff HEAD~1 --min-confidence 0.5
        language: system
        pass_filenames: true
        types: [python]
```

A confidence of `0.5` means only signals with medium or higher confidence will be reported, reducing false positives.

## Combined: Changed Files + Confidence Filter

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        description: Check for documentation drift in changed files with noise filtering
        entry: drift check --diff HEAD~1 --min-confidence 0.5
        language: system
        pass_filenames: true
        types: [python]
```

## Auto-fix Hook

For extractors that support auto-fixing, you can add a second hook that runs with `pass_filenames: false` (so it can fix all affected files in a batch):

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        description: Check for documentation drift
        entry: drift check --diff HEAD~1 --min-confidence 0.5
        language: system
        pass_filenames: true
        types: [python]

      - id: drift-fix
        name: drift (auto-fix)
        description: Automatically fix documentation drift where possible
        entry: drift fix --diff HEAD~1 --min-confidence 0.5
        language: system
        pass_filenames: false
        stages: [commit]
        types: [python]
```

## Flags Reference

| Flag | Description |
|------|-------------|
| `--diff <ref>` | Compare against `<ref>` (e.g., `HEAD~1`, `origin/main`). Only report drift in files that differ. |
| `--min-confidence <0.0-1.0>` | Minimum confidence threshold. Signals below this are ignored. Default is no filtering. |
| `--check` | Run in check mode (exit non-zero if drift found). This is the default when using the CLI directly. |
| `--fix` | Attempt to auto-fix fixable drift categories. |

## Exit Codes

- `0` — No drift found, or all drift was auto-fixed
- `1` — Drift found in check mode (commit blocked)
- `2` — Error (invalid args, file not found, etc.)
