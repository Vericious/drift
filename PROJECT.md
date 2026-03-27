# PROJECT: Drift

## What
A Python CLI tool that detects documentation-code drift — finds where docs have gone stale relative to the actual codebase. Extracts facts from code (functions, classes, CLI flags, configs, decorators, OpenAPI routes) and claims from docs (markdown, docstrings), then matches them to find mismatches, missing docs, and renamed symbols.

## Why
Documentation rot is universal and invisible until it causes real damage. No existing tool does cross-format code-to-doc matching with fuzzy rename detection. This is a genuinely useful developer tool.

## Status
v0.4.0-dev — 17 extractors, 498 tests passing, fuzzy matching, renamed detection, SARIF output, HTML output, pre-commit hooks, plugin system, incremental scan.

## Milestones
- [x] v0.1.0 — Core extraction + matching
- [x] v0.2.0 — CLI, reporters, config file
- [x] v0.3.0 — CLI flag detection (argparse + click)
- [x] v0.4.0 — Fuzzy matching, renamed detection, SARIF, HTML output, pre-commit, plugin system, incremental scan
- [ ] v0.5.0 — JS/TS JSDoc (done), TypeScript interfaces, baseline command, git diff scanning, diff-style output, confidence scoring
- [ ] v0.6.0 — GraphQL schema extraction, Protocol/ABC detection, setup.py extractors, deprecation detection

## Scope
- Python-first, expanding to JS/TS
- CLI tool (pip installable)
- CI-friendly (exit codes, SARIF, machine-readable output)

## Non-goals
- IDE plugin (not now)
- SaaS / hosted service
- Real-time file watching (someday, not priority)

## Tech
- Python 3.11+, Click CLI, Rich for CLI output, Pydantic models
- pytest, mypy strict, ruff, pre-commit
- Lives in `remi-lab/projects/drift/`
