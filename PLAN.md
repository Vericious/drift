# Drift — Project Plan

**Detect when documentation no longer matches code.**

Developers write docs. Code evolves. Docs go stale. Nobody notices. Drift scans your codebase, extracts ground truth (function signatures, CLI flags, config options, error messages), compares it against what your docs claim, and tells you exactly what has drifted.

---

## 1. Project Structure

```
drift/
├── README.md
├── LICENSE                  # MIT
├── pyproject.toml           # Project metadata, dependencies, build config
├── .gitignore
├── src/
│   └── drift/
│       ├── __init__.py      # Version, top-level imports
│       ├── __main__.py      # `python -m drift` entry point
│       ├── cli.py           # CLI interface (click)
│       ├── config.py        # Config loading (.drift.toml / pyproject.toml)
│       ├── models.py        # Data models: CodeFact, DocClaim, DriftResult
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── base.py      # Abstract base extractor
│       │   ├── python.py    # Python code extractor (AST-based)
│       │   └── markdown.py  # Markdown doc extractor
│       ├── matchers/
│       │   ├── __init__.py
│       │   └── signature.py # Match doc claims to code facts
│       ├── reporters/
│       │   ├── __init__.py
│       │   ├── console.py   # Terminal output (rich)
│       │   └── json.py      # Machine-readable JSON output
│       └── scanner.py       # Orchestrator: scan → extract → match → report
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # Shared fixtures
│   ├── test_models.py
│   ├── test_extractors/
│   │   ├── __init__.py
│   │   ├── test_python.py
│   │   └── test_markdown.py
│   ├── test_matchers/
│   │   ├── __init__.py
│   │   └── test_signature.py
│   ├── test_reporters/
│   │   ├── __init__.py
│   │   └── test_console.py
│   ├── test_scanner.py
│   └── fixtures/            # Sample Python files + docs for testing
│       ├── sample_module.py
│       └── sample_docs.md
├── docs/
│   └── plans/
│       └── PLAN.md          # This file (symlinked or copied)
└── .drift.toml              # Example config for drift scanning itself
```

---

## 2. Milestones

### Milestone 1: MVP — Python Function Drift (v0.1.0)
**Goal:** Detect when Python function signatures in code don't match what README/docs claim.

**Deliverables:**
- CLI: `drift scan [path]` scans a project and reports drift
- Extracts Python function signatures via AST (name, params, defaults, return type)
- Extracts function references from Markdown docs (code blocks, inline references)
- Matches and compares: missing params, wrong defaults, renamed functions, missing functions
- Console output showing what drifted and where
- JSON output option (`--format json`)
- Installable via `pip install -e .`
- Tests at tier 2+

**Estimated time:** 3-4 sessions

---

### Milestone 2: Docstring Drift + Config (v0.2.0)
**Goal:** Also check docstrings for internal consistency, and support project-level config.

**Deliverables:**
- Parse docstrings (Google/NumPy/Sphinx style) as doc claims
- Compare docstring param lists against actual function signatures
- `.drift.toml` config: include/exclude paths, ignore rules, severity levels
- `pyproject.toml [tool.drift]` support as alternative config location
- `drift init` command to generate starter config
- Improved console output with severity colors (error/warning/info)

**Estimated time:** 2-3 sessions

---

### Milestone 3: CLI Flag Drift + CI Integration (v0.3.0)
**Goal:** Detect when CLI flags in argparse/click/typer don't match docs. Ship CI-friendly output.

**Deliverables:**
- Extract CLI flags from argparse, click, and typer definitions
- Match CLI flags against documented usage examples
- Exit code 1 when drift detected (CI-friendly)
- GitHub Actions example in README
- `--fail-on` flag to control which severity levels cause failure
- SARIF or JUnit output format for CI integration

**Estimated time:** 2-3 sessions

---

### Milestone 4: Multi-language + Plugin Architecture (v0.5.0)
**Goal:** Support beyond Python. Let others add languages.

**Deliverables:**
- Extractor plugin interface (entry points)
- JavaScript/TypeScript extractor (JSDoc + function signatures)
- REST API endpoint extraction (Flask/FastAPI route decorators)
- `drift plugins list` and plugin discovery
- Published to PyPI

**Estimated time:** 3-4 sessions

---

### Milestone 5: Smart Matching + Drift Score (v1.0.0)
**Goal:** Go from "exact match" to intelligent fuzzy matching. Give projects a drift score.

**Deliverables:**
- Fuzzy matching for renamed/moved functions
- Project-wide drift score (0-100)
- Trend tracking (compare against previous scan)
- `drift badge` — generate a shield.io badge for README
- Pre-commit hook support
- Comprehensive docs site
- Stable API, semver commitment

**Estimated time:** 3-4 sessions

---

## 3. MVP Scope — Detailed Task Breakdown

### Task 1: Project Scaffolding
**What:** Create the project skeleton — directory structure, pyproject.toml, empty modules, basic CLI entry point that prints version.

**Files to create:**
- `pyproject.toml` (project metadata, dependencies, `[project.scripts]` entry)
- `src/drift/__init__.py` (version string)
- `src/drift/__main__.py` (entry point)
- `src/drift/cli.py` (click group with `--version` flag)
- `README.md` (template per ENGINEERING.md)
- `LICENSE` (MIT)
- `.gitignore` (Python standard)
- `tests/__init__.py`
- `tests/conftest.py`

**Dependencies to declare:**
- `click>=8.0` (CLI framework)
- `rich>=13.0` (terminal output)
- `tomli>=2.0;python_version<"3.11"` (TOML parsing fallback)

**Dev dependencies:**
- `pytest>=7.0`
- `pytest-cov`

**Test:** `pip install -e .` works, `drift --version` prints version, `pytest` passes (even with zero tests).

**Independently testable:** Yes — install and run `drift --version`.

---

### Task 2: Data Models
**What:** Define the core data structures that everything else operates on.

**Files to create:**
- `src/drift/models.py`
- `tests/test_models.py`

**Models (dataclasses):**

```python
@dataclass
class Parameter:
    name: str
    type_annotation: str | None = None
    default: str | None = None
    kind: str = "POSITIONAL_OR_KEYWORD"  # maps to inspect.Parameter.kind

@dataclass
class CodeFact:
    """A ground-truth fact extracted from source code."""
    kind: str              # "function", "class", "cli_flag", "config_option"
    name: str              # Qualified name: "module.function_name"
    file_path: str         # Where it was found
    line_number: int       # Line in source
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    decorators: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)  # Extension point

@dataclass
class DocClaim:
    """A claim about code found in documentation."""
    kind: str              # "function_ref", "param_ref", "code_block", "inline_ref"
    name: str              # What it claims to reference
    file_path: str         # Doc file where claim was found
    line_number: int
    parameters: list[Parameter] = field(default_factory=list)
    return_type: str | None = None
    raw_text: str = ""     # The original text of the claim
    metadata: dict = field(default_factory=dict)

@dataclass
class DriftItem:
    """A single piece of drift between a fact and a claim."""
    severity: str          # "error", "warning", "info"
    category: str          # "missing_param", "extra_param", "wrong_default", etc.
    message: str           # Human-readable description
    code_fact: CodeFact | None = None
    doc_claim: DocClaim | None = None

@dataclass
class DriftReport:
    """Complete drift analysis result."""
    items: list[DriftItem] = field(default_factory=list)
    facts_found: int = 0
    claims_found: int = 0
    scan_path: str = ""
    scan_time: float = 0.0

    @property
    def has_drift(self) -> bool:
        return any(item.severity == "error" for item in self.items)
```

**Test:** Create instances, verify fields, test `has_drift` property, test serialization to dict.

**Independently testable:** Yes — pure data, no dependencies on other modules.

---

### Task 3: Python Code Extractor
**What:** Parse Python source files using `ast` to extract function/class signatures as `CodeFact` objects.

**Files to create:**
- `src/drift/extractors/__init__.py`
- `src/drift/extractors/base.py` (abstract `Extractor` class)
- `src/drift/extractors/python.py`
- `tests/test_extractors/__init__.py`
- `tests/test_extractors/test_python.py`
- `tests/fixtures/sample_module.py`

**Base extractor interface:**
```python
class Extractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path) -> list[CodeFact]: ...

    @abstractmethod
    def can_handle(self, file_path: Path) -> bool: ...
```

**Python extractor must handle:**
- Top-level functions (name, params with types/defaults, return type, decorators)
- Methods inside classes (qualified as `ClassName.method_name`)
- Nested classes/functions (skip — MVP doesn't need them)
- `*args`, `**kwargs`
- Type annotations (as strings, not resolved)
- Default values (as string repr)

**Input:** Path to a `.py` file
**Output:** `list[CodeFact]`

**Test fixture (`sample_module.py`):**
```python
def simple_func(x: int, y: str = "hello") -> bool:
    pass

class MyClass:
    def method(self, data: list[str], verbose: bool = False) -> None:
        pass

def no_annotations(a, b, c=42):
    pass
```

**Tests:** Extract from fixture, verify all params, types, defaults, qualified names.

**Independently testable:** Yes — needs only `models.py`.

---

### Task 4: Markdown Doc Extractor
**What:** Parse Markdown files to find references to code — function signatures in code blocks, inline code references, parameter lists.

**Files to create:**
- `src/drift/extractors/markdown.py`
- `tests/test_extractors/test_markdown.py`
- `tests/fixtures/sample_docs.md`

**What to extract from Markdown:**

1. **Python code blocks** (` ```python `) — parse them as AST if they contain function defs or calls
2. **Inline code** (`` `function_name(arg1, arg2)` ``) — regex-based extraction
3. **Parameter documentation patterns** — lines like `- `param_name` (type): description`
4. **Function signature lines** — patterns like `function_name(param1, param2)` in text

**Input:** Path to a `.md` file
**Output:** `list[DocClaim]`

**Approach:** Use a simple Markdown parser (or regex — no need for a full AST parser for Markdown in MVP). Walk through the file, identify code blocks and inline code, extract claims.

**Test fixture (`sample_docs.md`):**
```markdown
## API Reference

### simple_func

\`\`\`python
simple_func(x: int, y: str = "hello") -> bool
\`\`\`

Takes `x` and `y` parameters.

### old_function

\`\`\`python
old_function(a, b, c)
\`\`\`

This function was renamed but docs weren't updated.
```

**Tests:** Extract claims from fixture, verify names, params, line numbers.

**Independently testable:** Yes — needs only `models.py`.

---

### Task 5: Signature Matcher
**What:** Take a list of `CodeFact`s and a list of `DocClaim`s, match them by name, compare their signatures, produce `DriftItem`s.

**Files to create:**
- `src/drift/matchers/__init__.py`
- `src/drift/matchers/signature.py`
- `tests/test_matchers/__init__.py`
- `tests/test_matchers/test_signature.py`

**Matching logic:**
1. **Name matching:** Match `DocClaim.name` to `CodeFact.name` (exact match, then try unqualified)
2. For each matched pair, compare:
   - **Missing parameters:** Param in doc but not in code → `error: "extra_param"`
   - **Extra parameters:** Param in code but not in doc → `warning: "undocumented_param"`
   - **Wrong defaults:** Same param, different default → `warning: "wrong_default"`
   - **Wrong types:** Same param, different type annotation → `warning: "wrong_type"`
   - **Wrong return type:** → `warning: "wrong_return_type"`
3. **Unmatched doc claims:** Doc references a function that doesn't exist → `error: "documented_but_missing"`
4. **Unmatched code facts:** Function exists but has no doc coverage → `info: "undocumented"`

**Input:** `list[CodeFact]`, `list[DocClaim]`
**Output:** `list[DriftItem]`

**Tests:** Feed known-good and known-drifted pairs, verify correct drift items produced.

**Independently testable:** Yes — pure logic on data models.

---

### Task 6: Console Reporter
**What:** Take a `DriftReport` and render it beautifully to the terminal using Rich.

**Files to create:**
- `src/drift/reporters/__init__.py`
- `src/drift/reporters/console.py`
- `src/drift/reporters/json.py`
- `tests/test_reporters/__init__.py`
- `tests/test_reporters/test_console.py`

**Console output format:**
```
drift v0.1.0 — scanning ./src

Found 12 code facts, 8 doc claims

✗ simple_func — parameter mismatch
  docs/api.md:15 claims: simple_func(x: int, y: str = "world")
  src/app.py:8 actual:  simple_func(x: int, y: str = "hello")
  → default for 'y' differs: "world" (docs) vs "hello" (code)

✗ old_function — documented but not found in code
  docs/api.md:23 references old_function(a, b, c)
  → no matching function found in scanned code

⚠ MyClass.method — undocumented parameters
  src/app.py:14 has parameters not covered in docs: verbose

Summary: 2 errors, 1 warning, 0 info
```

**JSON reporter:** Serialize `DriftReport` to JSON (straightforward `dataclasses.asdict` + `json.dumps`).

**Tests:** Build a `DriftReport`, render to string, verify key elements present.

**Independently testable:** Yes — just formatting data models.

---

### Task 7: Scanner Orchestrator
**What:** Wire everything together. Walk the file tree, dispatch to extractors, run matchers, produce a report.

**Files to create:**
- `src/drift/scanner.py`
- `tests/test_scanner.py`

**Logic:**
1. Walk the target directory
2. For each file, find an extractor that `can_handle` it
3. Collect all `CodeFact`s from code files (`.py`)
4. Collect all `DocClaim`s from doc files (`.md`)
5. Run the signature matcher
6. Build a `DriftReport`
7. Return it

**File discovery defaults:**
- Code: `src/**/*.py`, `*.py` in root
- Docs: `README.md`, `docs/**/*.md`, `*.md` in root
- Exclude: `.git`, `__pycache__`, `.venv`, `node_modules`, `.tox`

**Input:** Path to scan (defaults to `.`)
**Output:** `DriftReport`

**Tests:** Use the test fixtures directory as a mini-project, run scanner, verify end-to-end report.

**Independently testable:** Yes — integration test using fixtures.

---

### Task 8: CLI Wiring + End-to-End Test
**What:** Connect the scanner to the CLI. Add `drift scan` command with options. Write an end-to-end test.

**Files to modify:**
- `src/drift/cli.py` (add `scan` command)

**Files to create:**
- `tests/test_cli.py`

**CLI interface:**
```
drift scan [PATH] [OPTIONS]

Options:
  --format [console|json]   Output format (default: console)
  --code-paths TEXT          Glob patterns for code files (can repeat)
  --doc-paths TEXT           Glob patterns for doc files (can repeat)
  --no-color                 Disable colored output
  -v, --verbose              Show all findings including info-level
  -q, --quiet                Only show errors
```

**Exit codes:**
- `0` — no drift detected
- `1` — drift detected (errors found)
- `2` — scan failed (bad path, no files found, etc.)

**End-to-end test:** Create a temp directory with Python files + Markdown docs, run `drift scan` via Click's test runner, verify output and exit code.

**Independently testable:** Yes — Click's `CliRunner` makes this easy.

---

## 4. Technical Decisions

### Python Version
**3.11+** — We use `tomllib` (3.11 stdlib), modern type syntax, and `dataclasses`. No reason to support older versions for a new dev tool.

### Key Libraries

| Library | Purpose | Why |
|---------|---------|-----|
| **click** | CLI framework | Battle-tested, composable, excellent test runner. Preferred over argparse (too verbose) and typer (unnecessary magic). |
| **rich** | Terminal output | Beautiful tables, colors, panels. No alternative comes close. |
| **tomllib** (stdlib) | Config parsing | Built into 3.11+, no dependency needed. |
| **ast** (stdlib) | Python code parsing | The only correct way to parse Python. No regex. No tree-sitter (overkill for MVP). |
| **pathlib** (stdlib) | File handling | Modern, clean API. |
| **dataclasses** (stdlib) | Data models | Simple, no dependencies. Not Pydantic — we don't need validation/serialization complexity for internal models. |
| **re** (stdlib) | Markdown pattern matching | Good enough for MVP. Code blocks and inline code have predictable patterns. |

**What we avoid:**
- **Pydantic** — Overhead we don't need. Our models are internal, not user-facing API schemas.
- **tree-sitter** — Powerful but heavy dependency. `ast` handles Python perfectly. Save tree-sitter for multi-language milestone.
- **mistune/markdown-it** — Full Markdown AST parsers. We only need code blocks and inline code. Regex is simpler and faster for MVP.
- **typer** — Nice for simple CLIs, but click gives us more control and better test tooling.

### Core Parsing Challenge: Matching Doc Claims to Code Facts

The hard problem is: *how do you know that `simple_func(x, y)` in a doc is referring to `mypackage.utils.simple_func(x: int, y: str)`?*

**MVP approach — name-based matching:**
1. Strip qualifiers: `module.Class.method` → match on `method`, `Class.method`, or full path
2. Exact name match first (highest confidence)
3. Unqualified match second (lower confidence, flag as ambiguous if multiple)
4. No match → `documented_but_missing` or `undocumented`

**Future (Milestone 5):** Fuzzy matching with edit distance, import tracing, cross-reference resolution.

### Data Model Philosophy

- **CodeFact = source of truth.** Extracted mechanically from AST. Always correct.
- **DocClaim = assertion to verify.** Extracted from docs. May be wrong, stale, or ambiguous.
- **DriftItem = the delta.** What changed, how severe, where to look.

The models are deliberately simple dataclasses. No inheritance hierarchies. No ORMs. Just data containers with clear fields.

### Scoring / Reporting

**MVP:** No score. Just a list of drift items with severity levels.
- `error` — Something is definitely wrong (documented function doesn't exist, param mismatch)
- `warning` — Probably wrong (wrong default, undocumented new param)
- `info` — FYI (function exists but isn't documented)

**Future (Milestone 5):** Drift score 0-100 based on weighted item counts.

---

## 5. GitHub Repo Setup

### Repository
- **Name:** `drift`
- **Description:** Detect when your documentation no longer matches your code
- **Topics:** `documentation`, `linter`, `python`, `developer-tools`, `docs`, `code-quality`, `cli`
- **Visibility:** Public

### LICENSE
MIT — standard for dev tools, maximum adoption.

### Initial Commit

The initial commit should contain:
1. `README.md` — project description, "Status: in-progress", planned features
2. `LICENSE` — MIT
3. `pyproject.toml` — complete with metadata, dependencies, entry points
4. `.gitignore` — Python standard (`.venv`, `__pycache__`, `*.egg-info`, `dist/`, `.pytest_cache/`)
5. `src/drift/__init__.py` — version string only
6. `src/drift/__main__.py` — entry point
7. Empty `tests/__init__.py`

**Commit message:** `feat: initial project scaffolding`

Everything else comes in as feature branches per ENGINEERING.md.

---

## 6. Definition of MVP

Drift v0.1.0 is useful on day 1 if a developer can:

1. **Install it:** `pip install drift-doc` (or `pip install -e .` from source)
2. **Run it:** `cd my-project && drift scan`
3. **Get actionable output:** See a list of specific things that are wrong — which function in which doc file doesn't match which function in which code file, and *exactly how* they differ
4. **Trust it:** Zero false positives on the happy path. If Drift says something drifted, it actually drifted. (False negatives are acceptable in MVP — missing some drift is okay, reporting wrong drift is not.)
5. **Integrate it:** `drift scan --format json` for piping to other tools, exit code 1 for CI gates

**The bar:** If you run `drift scan` on a Python project with a README that documents some functions, and one of those functions has changed its signature since the docs were written, Drift tells you exactly what changed. That's useful. That's the MVP.

**What MVP explicitly does NOT do:**
- Parse languages other than Python
- Parse doc formats other than Markdown
- Understand prose ("this function takes a list" in natural language)
- Track drift over time
- Auto-fix anything
- Require configuration (zero-config by default, config is optional)

---

## Appendix: Task Dependency Graph

```
Task 1: Scaffolding          (no deps)
Task 2: Data Models           (no deps — can parallel with Task 1)
Task 3: Python Extractor      (depends on: Task 2)
Task 4: Markdown Extractor    (depends on: Task 2, parallel with Task 3)
Task 5: Signature Matcher     (depends on: Task 2, parallel with Tasks 3-4)
Task 6: Console Reporter      (depends on: Task 2, parallel with Tasks 3-5)
Task 7: Scanner Orchestrator   (depends on: Tasks 3, 4, 5, 6)
Task 8: CLI Wiring + E2E      (depends on: Tasks 1, 7)
```

**Optimal execution order:**
1. Tasks 1 + 2 (parallel)
2. Tasks 3 + 4 + 5 + 6 (parallel, all depend only on Task 2)
3. Task 7 (needs 3, 4, 5, 6)
4. Task 8 (needs everything)

**Minimum sessions to complete MVP:** 3 (if parallelizing tasks within each session)
