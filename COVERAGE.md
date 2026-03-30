# Coverage Baseline

**Date:** 2026-03-26
**pytest:** 9.0.2
**Python:** 3.13.5

## Overall Coverage: 85%

| Module | Coverage | Notes |
|--------|----------|-------|
| `drift/__init__.py` | 100% | |
| `drift/__main__.py` | 0% | CLI entry point (tested via integration) |
| `drift/cli.py` | 89% | CLI layer |
| `drift/config.py` | 87% | Config loading |
| `drift/extractors/__init__.py` | 100% | |
| `drift/extractors/base.py` | 100% | ABC interface |
| `drift/extractors/cli_argparse.py` | 87% | Argparse extractor |
| `drift/extractors/cli_click.py` | 79% | Click extractor |
| `drift/extractors/cli_typer.py` | 83% | Typer extractor |
| `drift/extractors/config_file.py` | 82% | YAML/TOML extractor |
| `drift/extractors/docstring.py` | 96% | Docstring extractor |
| `drift/extractors/markdown.py` | 93% | Markdown extractor |
| `drift/extractors/pydantic.py` | 72% | Pydantic extractor |
| `drift/extractors/registry.py` | 56% | Registry (minimal test coverage) |
| `drift/matcher.py` | 95% | Drift matcher |
| `drift/models.py` | 100% | Data models |
| `drift/python_extractor.py` | 65% | Python function extractor |
| `drift/reporter.py` | 97% | Reporter |
| `drift/scanner.py` | 79% | Scanner orchestration |

## Extractor Metadata Audit (DRIFT-167)

All 24 registered extractors were audited for consistent metadata fields on extracted items.

### Required Fields for CodeFact
- `name`: Function/class/config name (non-empty string)
- `kind`: FactKind enum value
- `source_file`: Path to the source file (non-None)
- `line_number`: Line number in source (non-None)

### Required Fields for DocClaim
- `name`: Extracted function/class name (may be None for anonymous items)
- `kind`: ClaimKind enum value
- `doc_file`: Path to the documentation file (non-None)
- `line_number`: Line number in doc file (non-None)

### Audit Results
| Extractor | Produces | source_file | line_number | name | kind |
|-----------|----------|-------------|--------------|------|------|
| ArgparseExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| ClickExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| TyperExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| ConfigFileExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| DataclassFieldsExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| DecoratorExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| DeprecatedExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| DjangoURLsExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| DockerfileExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| DocstringExtractor | DocClaim | ✓ | ✓ | ✓ | ✓ |
| EnvVarExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| FastAPIRoutesExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| FlaskRoutesExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| GraphQLExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| JSDocExtractor | DocClaim | ✓ | ✓ | ✓ | ✓ |
| MakefileExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| OpenAPIExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| PydanticExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| PythonExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| RSTDocsExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| SQLAlchemyExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| TerraformExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| TypeScriptExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |
| YamlConfigExtractor | CodeFact | ✓ | ✓ | ✓ | ✓ |

**Result: All extractors are compliant.** No missing or inconsistent fields found.

### Metadata Compliance Tests
- `test_all_extractors_return_source_file`: Verifies all CodeFact items have non-None source_file
- `test_all_extractors_return_line_number`: Verifies all CodeFact items have non-None line_number
- `test_extractor_metadata_schema_compliance`: Verifies all CodeFact items have name, kind, source_file, line_number

All tests pass: `python3 -m pytest tests/test_extractors/test_registry.py::TestExtractorMetadataCompliance -v`

## Notes

- Coverage is measured with `--cov=drift --cov-report=term-missing`
- Run `python3 -m pytest --cov=drift --cov-report=term-missing tests/` to reproduce
- Low-coverage modules (registry, pydantic, python_extractor) reflect areas for additional testing
- The `__main__.py` 0% is expected as it's an import-only entry point
