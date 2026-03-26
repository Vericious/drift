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
