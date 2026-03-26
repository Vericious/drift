# PROJECT: Drift

## What
A Python CLI tool that detects documentation-code drift — finds where docs have gone stale relative to the actual codebase. Extracts facts from code (functions, classes, CLI flags, configs, decorators, OpenAPI routes) and claims from docs (markdown, docstrings), then matches them to find mismatches, missing docs, and renamed symbols.

## Why
Documentation rot is universal and invisible until it causes real damage. No existing tool does cross-format code-to-doc matching with fuzzy rename detection. This is a genuinely useful developer tool.

## Status
v0.4.0-dev — 14 extractors, 382 tests, fuzzy matching, SARIF output, severity filtering, .driftignore, parallel scanning.

## Milestones
- [x] v0.1.0 — Core extraction + matching
- [x] v0.2.0 — CLI, reporters, config file
- [x] v0.3.0 — CLI flag detection (argparse + click)
- [ ] v0.4.0 — Fuzzy matching, renamed detection, SARIF, HTML output
- [ ] v0.5.0 — JS/TS support, CI integration, auto-fix, plugin system

## Scope
- Python-first, expanding to JS/TS
- CLI tool (pip installable)
- CI-friendly (exit codes, SARIF, machine-readable output)

## Non-goals
- IDE plugin (not now)
- SaaS / hosted service
- Real-time file watching (someday, not priority)

## Tech
- Python 3.11+, Typer CLI, Pydantic models
- pytest, mypy strict, ruff
- Lives in `remi-lab/projects/drift/`
