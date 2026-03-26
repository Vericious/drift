# Changelog

## 2026-03-26

### DRIFT-021 — Scanner Graceful Error Recovery

**Task:** Make scanner resilient to malformed files that crash extractors.

**What was done:**
- Refactored `scan()` in `scanner.py` to use `_extract_py()` helper with per-extractor try/except blocks
- Each error entry now includes `[ExtractorName]` prefix for attribution
- Added `strict` parameter to `DriftScanner.__init__`; when True, exceptions propagate (fatal)
- Default: best-effort mode — skip bad files, collect errors, continue
- Added `--strict` flag to CLI `scan` command
- Added `TyperExtractor` and `PydanticExtractor` to the scanner pipeline

**Tests:** 3 new tests in `TestScannerGracefulErrorRecovery`:
- Malformed file: facts from valid file collected, error for bad file, no crash
- Error message includes file path
- `--strict` mode raises exception on malformed file
- All 189 tests pass

---

### DRIFT-013 — Pydantic Settings/Model Extractor

**Task:** Create AST-based extractor for Pydantic BaseSettings/BaseModel fields (`src/drift/extractors/pydantic.py`)

**What was done:**
- Created `src/drift/extractors/pydantic.py` implementing the `Extractor` base class
- Detects classes inheriting from `BaseSettings`, `BaseModel`, `Settings`, or `Base`
- Extracts field assignments from `AnnAssign` nodes (annotated assignments)
- Handles both `Field(default, env='VAR', alias='x', description='...')` calls and plain default values
- Extracts: field name, type annotation (including generics like `list[str]`), default value, description, env var mapping, alias
- Produces `CodeFact` objects with `kind=FactKind.CONFIG_KEY`
- Fact name format: `ClassName.field_name` (e.g., `AppConfig.debug`)
- Registered extractor in `src/drift/extractors/__init__.py`

**Fixture:** `tests/fixtures/sample_settings.py` — BaseSettings class (AppConfig) and BaseModel class (UserModel)

**Tests:** `tests/test_extractors/test_pydantic.py` — 10 tests, all pass
- All 186 tests in the project pass

---

### DRIFT-011 — Typer CLI Flag Extractor

**Task:** Create AST-based extractor for Typer CLI apps (`src/drift/extractors/cli_typer.py`)

**What was done:**
- Created `src/drift/extractors/cli_typer.py` implementing the `Extractor` base class
- Detects `@app.command()` decorated functions
- Extracts `typer.Option()` and `typer.Argument()` calls via AST
- Handles both annotation-style (`name: Annotated[Type, typer.Option(...)]`) and parameter-default-style (`name: Type = typer.Option(...)`) patterns
- Extracts flag names (derives `--flag-name` from Python parameter `flag_name`), types, defaults, help text, required status
- Produces `CodeFact` objects with `kind=FactKind.CLI_FLAG`
- Registered extractor in `src/drift/extractors/__init__.py`

**Fixture:** `tests/fixtures/sample_typer.py` — multi-command Typer app using both Annotated and default-style Options plus Arguments

**Tests:** `tests/test_extractors/test_cli_typer.py` — 15 tests covering all requirements
- All 186 tests in the project pass
