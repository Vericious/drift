# Drift v0.4.0 Plan — Typer CLI + Pydantic Settings Drift

**Goal:** Extend CLI flag detection to Typer (the popular modern CLI framework built on click), and add detection for Pydantic settings/config drift.

---

## Context

v0.3.0 shipped: argparse + click CLI flag drift detection (161 tests passing).

v0.4.0 targets two new extractors and the associated documentation drift detection.

---

## Tasks

### DRIFT-011 — Typer CLI Extractor
**Title:** Implement Typer CLI flag extractor

**Spec:**
1. Create `src/drift/extractors/cli_typer.py`
2. Detect `@app.command()` decorated functions and `typer.Option()` / `typer.Argument()` calls
3. Extract flag names, types, defaults, help text
4. Register extractor in `src/drift/extractors/__init__.py`
5. Create `tests/test_extractors/test_cli_typer.py` with fixtures
6. Fixtures: `tests/fixtures/sample_typer.py` with annotated Typer app

**Effort:** Medium — Typer uses `click` under the hood, patterns are similar to cli_click.py

**Dependencies:** None (can run in parallel with DRIFT-012)

---

### DRIFT-012 — Typer Documentation Drift
**Title:** Detect drift between Typer CLI flags and markdown docs

**Spec:**
1. Update markdown extractor to recognize Typer flag patterns in docs
2. Add `cli_typer_flag` and `cli_typer_flag_ref` categories to models.py
3. Add tests in `tests/test_e2e.py` for Typer drift scenarios
4. Update README.md if not already done in DRIFT-009 scope

**Effort:** Small

**Dependencies:** DRIFT-011

---

### DRIFT-013 — Pydantic Settings Extractor
**Title:** Implement Pydantic settings/config extractor

**Spec:**
1. Create `src/drift/extractors/pydantic.py`
2. Detect `BaseSettings` subclasses and `Field()` definitions
3. Extract: field name, type annotation, default value, env var mapping
4. Register extractor
5. Create fixtures: `tests/fixtures/sample_settings.py` with annotated settings
6. Tests: `tests/test_extractors/test_pydantic.py`

**Effort:** Medium — Pydantic introspects differently than AST, needs `inspect` or direct model analysis

**Dependencies:** None

---

### DRIFT-014 — Pydantic Settings Drift Detection
**Title:** Detect drift between Pydantic settings and documentation

**Spec:**
1. Update markdown extractor to recognize Pydantic settings patterns
2. Add `pydantic_field` and `pydantic_field_ref` categories
3. Common patterns to detect in docs:
   - `FOO_BAR` env var references
   - `settings.FOO` or `config.foo` references
   - Field names in prose
4. E2E tests in `tests/test_e2e.py`

**Effort:** Small

**Dependencies:** DRIFT-013

---

### DRIFT-015 — Unified CLI Reporter for All Frameworks
**Title:** Consolidate CLI flag output across argparse, click, typer

**Spec:**
1. Create `src/drift/reporters/cli.py` to format all CLI drift uniformly
2. Consolidate error/warning categories: `cli_flag`, `cli_flag_ref`, `cli_typer_flag`, `pydantic_field`
3. Update `console.py` reporter to use new unified CLI reporter
4. Ensure all 3 CLI frameworks + pydantic appear consistently in output

**Effort:** Small

**Dependencies:** DRIFT-011, DRIFT-012, DRIFT-013, DRIFT-014

---

### DRIFT-016 — v0.4.0 Release
**Title:** Tag and ship drift v0.4.0

**Spec:**
1. Update `__version__` to `0.4.0`
2. Update version string in `tests/test_cli.py`
3. Run full test suite — target 200+ tests
4. `git add`, commit, tag `v0.4.0`
5. Update CHANGELOG.md

**Effort:** Tiny

**Dependencies:** All above

---

## Dependency Graph

```
DRIFT-011 (Typer extractor)  ──┐
                               ├── DRIFT-012 (Typer drift)
DRIFT-013 (Pydantic extractor)─┤
                               ├── DRIFT-014 (Pydantic drift)
                               │
                               └── DRIFT-015 (Unified reporter) ── DRIFT-016 (Release)
```

**Optimal order:** DRIFT-011 and DRIFT-013 in parallel, then DRIFT-012 and DRIFT-014 in parallel, then DRIFT-015, then DRIFT-016.

---

## Definition of v0.4.0 Done

v0.4.0 ships when:
- Typer CLI flags are extracted and matched against docs (error + warning)
- Pydantic settings fields are extracted and matched against docs (error + warning)
- Unified CLI/settings output in console reporter
- 200+ tests passing
- `v0.4.0` tagged and pushed
- README updated with new capabilities

---

## Out of Scope for v0.4.0

- Auto-generating Pydantic settings from env vars
- Typer subcommands (groups of commands)
- Pydantic v2 `ConfigDict` (future work)
