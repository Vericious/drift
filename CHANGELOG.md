# Changelog

## 2026-03-26

### DRIFT-026 — Flask Route Extractor

**Task:** Create `src/drift/extractors/flask_routes.py` — extract API endpoint facts from Flask apps using AST parsing.

**What was done:**
- Created `src/drift/extractors/flask_routes.py` implementing the `Extractor` base class
- Handles `@app.route`, `@blueprint.route` (with `methods=[...]` list)
- Handles Flask 2.0+ shortcut decorators: `@app.get`, `@app.post`, `@bp.get`, `@bp.post`, etc.
- Two-pass AST: first collects `Blueprint(name, ..., url_prefix=...)` info, then resolves full paths for route decorators
- Fact name format: `"METHOD /path"` (e.g., `GET /api/v1/posts`, `POST /users`)
- Metadata includes: `methods` (list), `endpoint` (path), `blueprint` (internal Blueprint name), `function_name`
- `FactKind.API_ENDPOINT` already existed in models — no changes needed there
- Registered extractor in `src/drift/extractors/__init__.py` and `src/drift/extractors/registry.py`

**Fixture:** `tests/fixtures/sample_flask.py` — Flask app with multiple route styles, 3 Blueprints (`api`, `auth`, `utility`), Flask 2.0+ shortcuts

**Tests:** `tests/test_extractors/test_flask_routes.py` — 16 tests covering: `can_handle`, fact kinds, name format, app routes, methods list, Flask 2.0+ shortcuts, Blueprint routes, Blueprint shortcuts, metadata fields, multiple blueprints, source file/line number

**Result:** All 231 tests pass

---

### DRIFT-027 — FastAPI Route Extractor

**Task:** Create `src/drift/extractors/fastapi_routes.py` — extract API endpoint facts from FastAPI apps using AST parsing.

**What was done:**
- Created `src/drift/extractors/fastapi_routes.py` implementing the `Extractor` base class
- Handles `@app.get/post/put/delete/patch`, `@router.get`, etc.
- Handles `@app.api_route("/path", methods=[...])` for multi-method endpoints
- Two-pass AST: first collects `APIRouter(prefix=...)` prefixes, then resolves full paths for route decorators
- Extracts `response_model`, `status_code` (including `status.HTTP_201_CREATED` attribute form), and `tags` from decorator kwargs
- Extracts function parameters (name, type annotation, default) from the route function signature
- Fact name format: `"METHOD /path"` (e.g., `GET /api/v1/posts`, `POST /items`)
- Metadata: `methods`, `endpoint`, `router`, `status_code`, `response_model`, `tags`, `function_name`
- Registered extractor in `src/drift/extractors/__init__.py` and `src/drift/extractors/registry.py`

**Fixture:** `tests/fixtures/sample_fastapi.py` — FastAPI app with multiple routers, HTTP methods, status codes, response models, tags, and Annotated-style parameters

**Tests:** `tests/test_extractors/test_fastapi_routes.py` — 19 tests covering all requirements
- All 250 tests in the project pass

---

### DRIFT-028 — Environment Variable Extractor

**Task:** Create `src/drift/extractors/env_vars.py` — extract env var usage as CONFIG_KEY facts using AST.

**What was done:**
- Created `src/drift/extractors/env_vars.py` implementing the `Extractor` base class
- Detects `os.environ["VAR"]` (required=True), `os.environ.get("VAR")` (required=False), and `os.getenv("VAR")` (required=False)
- Handles `os.environ.get("VAR", default)` and `os.getenv("VAR", "default")` with default value extraction
- Handles `os.environ["VAR"]` (Subscript) and `.get()` / `os.getenv()` (Call) AST node patterns
- Deduplicates same var name in same file
- Produces CONFIG_KEY facts with name=var_name, metadata: env_var, required, default, source
- Registered extractor in `src/drift/extractors/__init__.py` and `src/drift/extractors/registry.py`

**Fixture:** `tests/fixtures/sample_env_vars.py` — 12 env var references covering all patterns

**Tests:** `tests/test_extractors/test_env_vars.py` — 14 tests covering all requirements
- All 264 tests in the project pass

---

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
