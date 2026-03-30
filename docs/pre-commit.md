# Pre-Commit Hooks

The `drift` tool can be integrated as a pre-commit hook to automatically check for documentation drift before each commit.

## Installation

Add the following to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        description: Check for documentation drift (blocks commit if drift found)
        entry: drift --check
        language: system
        pass_filenames: true
        types: [python]

      - id: drift-fix
        name: drift (auto-fix)
        description: Automatically fix documentation drift where possible
        entry: drift --fix
        language: system
        pass_filenames: false
        stages: [commit]
        types: [python]
```

## Checking Only Changed Files

By default, `drift` scans all files in a project. In a pre-commit context, you typically only want to check the files that are part of the current commit. Use the `--diff` flag to compare against a reference commit:

```yaml
- id: drift-check
  name: drift (check)
  description: Check for documentation drift in changed files only
  entry: drift --check --diff HEAD~1
  language: system
  pass_filenames: true
  types: [python]
```

This runs `drift` with `--diff HEAD~1`, which uses `git diff` to identify which files changed in the commit and scans only those files. The `HEAD~1` reference compares against the parent commit. You can adjust this to `HEAD~2`, `main`, or any other valid git ref.

## Reducing Noise with Confidence Threshold

Drift items include a confidence score (0.0–1.0) indicating how likely the item represents real drift. To filter out low-confidence items and reduce noise, use the `--min-confidence` flag:

```yaml
- id: drift-check
  name: drift (check)
  description: Check for documentation drift with high-confidence items only
  entry: drift --check --min-confidence 0.5
  language: system
  pass_filenames: true
  types: [python]
```

A `--min-confidence` value of `0.5` shows only items with confidence >= 0.5. Increase this to 0.7 or 0.8 for stricter filtering.

## Combined Example

A typical pre-commit configuration that checks only changed files with a confidence threshold:

```yaml
repos:
  - repo: local
    hooks:
      - id: drift-check
        name: drift (check)
        description: Check for documentation drift in changed files only
        entry: drift --check --diff HEAD~1 --min-confidence 0.5
        language: system
        pass_filenames: true
        types: [python]

      - id: drift-fix
        name: drift (auto-fix)
        description: Automatically fix documentation drift where possible
        entry: drift --fix --diff HEAD~1 --min-confidence 0.5
        language: system
        pass_filenames: false
        stages: [commit]
        types: [python]
```

## Available Flags

| Flag | Description |
|------|-------------|
| `--diff <ref>` | Scan only files changed vs the specified git ref |
| `--min-confidence <0.0-1.0>` | Only show drift items with confidence >= this value |
| `--check` | Check for drift without modifying files (used in `drift-check` hook) |
| `--fix` | Attempt to auto-fix drift (used in `drift-fix` hook) |

## Notes

- The `--diff` flag requires the project to be in a git repository
- When using `--diff HEAD~1` in a pre-commit hook, the comparison is against the parent of the current HEAD, which represents the staged changes about to be committed
- The `drift-fix` hook runs in the `commit` stage and does not pass filenames (it scans the entire working tree for changed files), so it uses `pass_filenames: false`
