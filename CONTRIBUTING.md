# Contributing to Drift

Thank you for contributing to Drift! This guide will help you get started.

## Development Setup

```bash
# Clone the repository
cd ~/code/drift

# Install dependencies
pip install -e ".[dev]"

# Verify installation
python -m drift --version
```

## Running Tests

```bash
# Run all tests
cd ~/code/drift && python -m pytest -q

# Run tests for a specific module
python -m pytest tests/test_scanner.py -q

# Run with verbose output
python -m pytest -v

# Run tests matching a pattern
python -m pytest -k "driftignore"
```

## Adding a New Extractor

Drift uses a registry pattern for extractors. To add a new extractor:

### 1. Create the Extractor File

Create `src/drift/extractors/your_extractor.py`:

```python
from drift.base import CodeExtractor, ClaimExtractor
from drift.models import CodeFact, DocClaim, ClaimKind, FactKind

class YourExtractor(CodeExtractor):
    kind = FactKind.FUNCTION  # or FUNCTION, CLASS, etc.
    
    def matches(self, file_path: Path) -> bool:
        """Return True if this extractor handles the file."""
        return file_path.suffix == ".your_ext"
    
    def extract(self, source_file: Path) -> list[CodeFact]:
        """Extract facts from source file."""
        facts = []
        # Parse file and create CodeFact objects
        return facts

class YourDocExtractor(ClaimExtractor):
    kind = ClaimKind.FUNCTION  # or FUNCTION_SIGNATURE, etc.
    
    def matches(self, file_path: Path) -> bool:
        return file_path.suffix == ".md"
    
    def extract(self, doc_file: Path) -> list[DocClaim]:
        claims = []
        # Parse docs and create DocClaim objects
        return claims
```

### 2. Register the Extractor

In `src/drift/extractors/registry.py`:

```python
from drift.extractors.your_extractor import YourExtractor, YourDocExtractor

# Add to the registry
CODE_EXTRACTORS = [PythonExtractor, YourExtractor, ...]
DOC_CLAIM_EXTRACTORS = [MarkdownClaimExtractor, YourDocExtractor, ...]
```

### 3. Add Tests

Create `tests/test_your_extractor.py`:

```python
from pathlib import Path
import pytest
from drift.extractors.your_extractor import YourExtractor

def test_extracts_functions():
    extractor = YourExtractor()
    # Write temporary source file
    # Assert expected facts extracted
```

## Code Style

- **Type hints**: All functions should have type hints
- **Docstrings**: Public methods need docstrings
- **Error handling**: Use specific exceptions, not bare `except:`
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes

Example:
```python
def extract_function_signatures(source_file: Path) -> list[CodeFact]:
    """Extract function signatures from Python source.
    
    Args:
        source_file: Path to Python file to parse.
        
    Returns:
        List of CodeFact objects for each function found.
        
    Raises:
        SyntaxError: If the file cannot be parsed.
    """
    pass
```

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add SARIF output format
fix: handle empty files in docstring extractor
docs: update README with new extractor example
test: add tests for fuzzy rename matching
refactor: simplify scanner file discovery logic
```

Format: `<type>: <description>`

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

## Project Structure

```
drift/
├── src/drift/
│   ├── base.py              # Base extractor interfaces
│   ├── models.py            # Data models (DriftItem, CodeFact, etc.)
│   ├── reporter.py          # Report generation
│   ├── scanner.py           # File discovery + driftignore
│   ├── matcher.py           # Matching facts to claims
│   ├── cli.py               # CLI commands
│   └── extractors/
│       ├── registry.py      # Extractor registry
│       ├── docstring.py     # Python docstring extractor
│       ├── markdown.py      # Markdown claim extractor
│       └── ...
├── tests/
│   ├── test_scanner.py      # Scanner tests
│   ├── test_reporter.py     # Reporter tests
│   ├── test_matcher.py      # Matcher tests
│   └── extractors/
│       └── test_docstring.py
└── CHANGELOG.md             # Keep updated with changes
```

## Extractor Reference

### CodeExtractor

```python
class CodeExtractor(Protocol):
    kind: FactKind
    def matches(self, file_path: Path) -> bool: ...
    def extract(self, source_file: Path) -> list[CodeFact]: ...
```

### ClaimExtractor

```python
class ClaimExtractor(Protocol):
    kind: ClaimKind
    def matches(self, file_path: Path) -> bool: ...
    def extract(self, doc_file: Path) -> list[DocClaim]: ...
```

### FactKind Options

- `FUNC`, `FUNC_DEF`, `FUNC_CALL` — Function-related
- `CLASS`, `METHOD` — Class-related
- `ATTR` — Attribute/field
- `PARAM` — Function parameter
- `IMPORT` — Import statement
- `DECORATOR` — Decorator

### ClaimKind Options

- `FUNCTION_SIGNATURE` — Signature in docs (e.g., `func(a, b)`)
- `CLASS_SIGNATURE` — Class signature
- `USAGE` — Usage example
- `ATTR` — Attribute documentation

See `src/drift/models.py` for full model definitions.
