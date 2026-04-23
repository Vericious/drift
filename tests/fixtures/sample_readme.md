# Drift README

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/example/drift)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://python.org)

## Overview

**drift** is a lightweight code事实提取工具 for Python projects. It scans your codebase and builds a database of code facts and their relationships.

## Installation

```bash
pip install drift
# or from source:
git clone https://github.com/example/drift.git
cd drift
pip install -e .
```

## Quick Start

```bash
# Scan current directory
drift scan ./my_project

# Run drift with custom config
drift run --config drift.toml

# Check drift version
drift version
```

## Configuration

drift reads configuration from `drift.toml` or `drift.yaml`.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DRIFT_HOME` | drift home directory | `~/.drift` |
| `DRIFT_DB` | Database path | `~/.drift/drift.db` |
| `DRIFT_LOG_LEVEL` | Logging level | `INFO` |

### Example Configuration

```toml
[drift]
log_level = "debug"
db_path = "/var/data/drift.db"

[extractors]
enabled = ["python", "typescript"]
disabled = ["ruby"]
```

## CLI Reference

### drift scan

Scan a directory for code facts:

```bash
drift scan PATH [--recursive] [--exclude PATTERN]
```

Examples:

```bash
# Scan current directory recursively
drift scan . --recursive

# Scan with exclusions
drift scan ./src --exclude "**/test*.py"

# Scan with specific extractors
drift scan . --extractors python,typescript
```

### drift run

Run drift with a configuration file:

```bash
drift run [--config CONFIG_FILE] [--watch]
```

### drift check

Check code quality:

```bash
drift check [--rules RULE1,RULE2]
```

## API Reference

### Python API

```python
from drift import Drift

client = Drift()
facts = client.scan("./my_project")
for fact in facts:
    print(fact.name, fact.kind)
```

### Extracting Facts

```python
from drift.extractors import PythonExtractor

extractor = PythonExtractor()
facts = extractor.extract("src/my_module.py")
```

## Supported Languages

| Language | Extractor | File Patterns |
|-----------|-----------|--------------|
| Python | `PythonExtractor` | `*.py` |
| TypeScript | `TypeScriptExtractor` | `*.ts`, `*.tsx` |
| YAML | `YamlExtractor` | `*.yaml`, `*.yml` |
| Markdown | `MarkdownExtractor` | `*.md` |

## Architecture

The drift architecture consists of:

- **Scanner**: Walks directories, discovers files
- **Extractors**: Extract facts from specific file types
- **Matcher**: Builds relationships between facts
- **Reporter**: Outputs results in various formats

## Development

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_extractors/test_python.py -v
```

## License

MIT License - see [LICENSE](LICENSE) for details.
