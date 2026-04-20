# Extractors

Drift uses pluggable **extractors** to pull facts and claims from your codebase and documentation.

## How Extractors Work

Extractors are registered in `src/drift/extractors/` and implement a common interface:

- **Fact Extractors** — pull information from code (functions, classes, CLI flags)
- **Claim Extractors** — pull documented information from markdown files

## Built-In Extractors

### Python Extractor (Facts)

Extracts function and class signatures from Python source files.

Covers:
- Function parameters and types
- Default values
- Return types (from type hints)
- Class methods

### CLI Extractor (Facts)

Detects CLI flags registered via `argparse` or `click`.

Parses:
- `argparse.ArgumentParser.add_argument()` calls
- `@click.option()` decorators

### Markdown Extractor (Claims)

Scans `.md` files for documented function signatures and CLI flags.

Recognizes patterns like:

```markdown
## my_function(a, b, c=None)

Function description...
```

Or in code blocks:

```bash
mytool --verbose  # Enable verbose output
```

### TypeScript Extractor (Facts)

Extracts TypeScript type declarations from `.ts` and `.tsx` files via `TypeScriptExtractor` in `src/drift/extractors/typescript.py`.

Handles three declaration forms:

| Form | Example | `FactKind` |
|------|---------|-------------|
| `interface` | `interface User { name: string }` | `FactKind.TS_INTERFACE` |
| `type` alias | `type ID = string \| number` | `FactKind.TS_TYPE` |
| `enum` | `enum Status { Active, Archived }` | `FactKind.TS_ENUM` |

#### Registration & Routing

TypeScript extraction uses the same pluggable architecture as other extractors:

1. **Registration**: `TypeScriptExtractor` is decorated with `@register` in `typescript.py`, which appends it to the global `_EXTRACTORS` list in `src/drift/extractors/registry.py`.

2. **can_handle routing**: When the scanner processes a file, it calls `can_handle(path)` on each registered extractor. `TypeScriptExtractor.can_handle()` returns `True` for paths with `.ts` or `.tsx` suffixes:

   ```python
   def can_handle(self, path: Path) -> bool:
       return path.suffix.lower() in (".ts", ".tsx")
   ```

3. **Discovery**: `_discover_extractors()` in `registry.py` imports `from drift.extractors import typescript` to trigger the `@register` decorator at startup.

#### Parameter Dataclass

Each extracted declaration produces a `CodeFact` with a `parameters` list built from the `Parameter` dataclass (`src/drift/models.py`). For TypeScript, properties become `Parameter` objects:

```python
Parameter(
    name=prop_name,
    type_annotation=prop_type,   # e.g. "string", "number | null"
    default=None,
    kind="positional",
    is_optional=is_optional,       # from `prop?`
    is_readonly=is_readonly,       # from `readonly prop`
)
```

#### TS-Specific FactKinds

Three `FactKind` values are exclusive to TypeScript extraction:

```python
class FactKind(Enum):
    TS_INTERFACE = "ts_interface"
    TS_TYPE      = "ts_type"
    TS_ENUM      = "ts_enum"
```

These are distinct from generic `FUNCTION` or `CLASS` kinds and carry `metadata["ts_kind"]` (e.g., `"TS_INTERFACE"`) plus additional context (`extends` for interfaces, `members` for enums, `is_const` for const enums).

#### JSDocExtractor Relationship

`JSDocExtractor` (`src/drift/extractor_js.py`) runs on the same `.ts`/`.tsx` files as a **companion claim extractor**, extracting JSDoc annotations (`@param`, `@returns`, `@type`, etc.) as `Claim` objects. The TypeScript extractor provides the **code facts** (structure); JSDocExtractor provides the **documentation claims** (intent).

Both run against the same file — the matcher then correlates TypeScript facts with JSDoc claims to detect undocumented types.

#### Architecture Diagram

```
File (.ts / .tsx)
     │
     ├── TypeScriptExtractor.can_handle() ──→ True?
     │        │
     │        └── extract()
     │                 │
     │                 ├── _INTERFACE_RE ──→ CodeFact(kind=TS_INTERFACE)
     │                 ├── _TYPE_ALIAS_RE  ──→ CodeFact(kind=TS_TYPE)
     │                 └── _ENUM_RE        ──→ CodeFact(kind=TS_ENUM)
     │
     └── JSDocExtractor.can_handle() ──→ True?
              │
              └── _extract_jsdoc_claims()
                        │
                        └── Claim objects
                               │
                        Matcher (correlates facts ↔ claims)
```
