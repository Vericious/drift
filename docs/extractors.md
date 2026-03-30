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

Extracts facts from TypeScript and JavaScript source files.

```ascii
┌─────────────────────────────────────────────┐
│  TypeScriptExtractor                         │
│  ┌─────────────────────────────────────┐    │
│  │  can_handle(source)                 │    │
│  │  → routes to JS/TS files (.ts/.js)  │    │
│  └─────────────────────────────────────┘    │
│  ┌─────────────────────────────────────┐    │
│  │  extract(source)                    │    │
│  │  → TypeScriptSignatureExtractor     │    │
│  │  → JSDocExtractor                  │    │
│  │  → creates Parameter dataclasses    │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

**TypeScriptSignatureExtractor** parses:
- Function declarations and signatures
- Interface property names and types
- Type aliases (primitive and union types)

**JSDocExtractor** parses JSDoc comments from TypeScript files for additional type information.

**TS-Specific FactKinds:**
- `TS_FUNCTION` — TypeScript/JavaScript function declarations
- `TS_INTERFACE` — Interface definitions and their properties
- `TS_TYPE` — Type alias declarations
- `TS_ENUM` — Enum declarations

**Parameter dataclass construction:**

```python
Parameter(
    name="username",
    type_annotation="string",
    default=None,
    kind=ParameterKind.POSITIONAL_OR_KEYWORD,
)
```

The TypeScript extractor creates `Parameter` dataclasses matching those used by the Python extractor, enabling consistent cross-language comparison.
