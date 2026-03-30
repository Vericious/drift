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

## TypeScript Extraction Architecture

Drift v0.5.0 adds first-class TypeScript type extraction via the `TypeScriptExtractor` and `JSDocExtractor`.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DriftScanner                                  │
│   changed_lines=None → full scan  │  changed_lines={...} → filtered  │
└───────────────────────┬─────────────────────────────────────────────┘
                        │
          ┌─────────────┴──────────────┐
          ▼                           ▼
┌─────────────────┐         ┌──────────────────┐
│  CodeFact       │         │  JSDocExtractor  │
│  (from code)    │         │  (from comments) │
│                 │         │                  │
│ TypeScriptExtract│        │ JSDocExtractor   │
│ → TS_INTERFACE   │         │ → DocClaim       │
│ → TS_TYPE        │         │                  │
│ → TS_ENUM        │         │                  │
└────────┬────────┘         └────────┬─────────┘
         │                            │
         └────────────┬──────────────┘
                      ▼
             ┌──────────────────┐
             │  SignatureMatcher │
             │  (fact ↔ claim)  │
             └──────────────────┘
```

### TypeScriptExtractor

**File:** `src/drift/extractors/typescript.py`

Handles `.ts` and `.tsx` files. Extracts:

| Pattern | Kind | Example |
|---------|------|---------|
| `interface Foo { ... }` | `TS_INTERFACE` | `interface User { name: string; age: number }` |
| `type Foo = { ... }` | `TS_TYPE` | `type Config = { debug: boolean }` |
| `enum Foo { ... }` | `TS_ENUM` | `enum Status { Active, Pending }` |

Produces `CodeFact` objects with `metadata['ts_kind']` indicating the type.

**Registration:** Uses `@register` decorator, auto-discovered on startup.

```python
@register
class TypeScriptExtractor(Extractor):
    def can_handle(self, path: Path) -> bool:
        return path.suffix.lower() in (".ts", ".tsx")

    def extract(self, path: Path) -> list[CodeFact]:
        # Parses interface/type/enum declarations
        # Returns CodeFact with FactKind.TS_INTERFACE/TS_TYPE/TS_ENUM
        pass
```

### TS-Specific FactKinds

Defined in `src/drift/models.py`:

```python
class FactKind(Enum):
    # ... other kinds ...
    TS_INTERFACE = "ts_interface"   # interface declarations
    TS_TYPE = "ts_type"             # type alias declarations
    TS_ENUM = "ts_enum"             # enum declarations
```

### Parameter Dataclass

TypeScript extraction uses the `Parameter` dataclass for consistent representation:

```python
from drift.models import Parameter

# Example: extracting interface properties
parameters=[
    Parameter(name="name", type_annotation="string", default=None, kind="positional"),
    Parameter(name="age", type_annotation="number", default=None, kind="positional"),
]
```

### JSDocExtractor

**File:** `src/drift/extractor_js.py`

Extracts JSDoc annotations from `.js`, `.ts`, `.jsx`, `.tsx` files:

| Tag | Kind | Example |
|-----|------|---------|
| `@param {type} name - desc` | `PARAMETER_DESCRIPTION` | `@param {string} username - The user name` |
| `@returns {type} desc` | `RETURN_DESCRIPTION` | `@returns {Promise<User>} - The user object` |
| `@type {type} desc` | `FUNCTION_SIGNATURE` | `@type {Function} - Wrapper function` |
| `@throws {type} desc` | `FUNCTION_SIGNATURE` | `@throws {Error} - On failure` |
| `@see ref` | `FUNCTION_SIGNATURE` | `@see [Docs](../guide.md)` |
| `@name explicitName` | (name override) | `@name getUser` |

### Relationship Between Extractors

1. **TypeScriptExtractor** runs on `.ts/.tsx` files → produces `CodeFact` with `FactKind.TS_*`
2. **JSDocExtractor** runs on `.js/.ts/.jsx/.tsx` files → produces `DocClaim` objects
3. **SignatureMatcher** matches `CodeFact` (from TS code) against `DocClaim` (from JSDoc)

This allows drift to detect when:
- A TypeScript interface is documented in JSDoc but the interface is missing
- A documented JSDoc function has no matching implementation
- Type definitions have changed without updating documentation
