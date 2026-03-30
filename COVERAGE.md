# Coverage Baseline

**Date:** 2026-03-30
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

## Notes

- Coverage is measured with `--cov=drift --cov-report=term-missing`
- Run `python3 -m pytest --cov=drift --cov-report=term-missing tests/` to reproduce
- Low-coverage modules (registry, pydantic, python_extractor) reflect areas for additional testing
- The `__main__.py` 0% is expected as it's an import-only entry point

---

## Extractor Metadata Audit (DRIFT-167)

**Date:** 2026-03-30
**Test:** `tests/test_extractor_metadata.py`

### Required Fields

| Object | Required Fields |
|--------|-----------------|
| `CodeFact` | `source_file`, `name`, `kind`, `line_number` |
| `DocClaim` | `doc_file`, `name`, `kind`, `line_number` |

### Findings

#### ✅ All extractors pass metadata schema

All extractors (registry + direct-import) produce items with the required metadata fields. No missing `source_file`, `name`, `kind`, or `line_number` fields were found.

#### ⚠️ Known Inconsistencies

| Extractor | Issue | Severity | Notes |
|-----------|-------|----------|-------|
| `TerraformExtractor` | `line_number=0` for all items | Low | HCL2 parser does not preserve line numbers in the parsed dict AST. This is a HCL library limitation, not a code bug. All Terraform facts return `line_number=0`. |

#### 🔶 Registry Discovery Gaps

Four extractors have `@register` decorators but are **not imported** in `drift.extractors.registry._discover_extractors()`. They are loaded via the plugin mechanism (`entry_points`) or manually imported:

| Extractor | Status |
|-----------|--------|
| `DotenvExtractor` | Gap — has `@register`; not auto-discovered |
| `ProtocolExtractor` | Gap — has `@register`; not auto-discovered |
| `PyprojectExtractor` | Gap — has `@register`; not auto-discovered |
| `RSTDocsExtractor` | Gap — has `@register`; not auto-discovered |

These extractors are functional when loaded via plugins or direct imports but won't appear in `get_extractors()` until added to the registry discovery list.

### Tested Extractors

**Registry (via `get_extractors()`):** ArgparseExtractor, ClickExtractor, TyperExtractor, ConfigFileExtractor, DataclassFieldsExtractor, DecoratorExtractor, DeprecatedExtractor, DjangoURLsExtractor, DocstringExtractor, EnvVarExtractor, FastAPIRoutesExtractor, FlaskRoutesExtractor, PydanticExtractor, TerraformExtractor, SQLAlchemyExtractor, GraphQLExtractor, OpenAPIExtractor, RSTDocsExtractor, YamlConfigExtractor, DockerfileExtractor, MakefileExtractor, TypeScriptExtractor

**Direct-import (scanner.py):** PythonExtractor, MarkdownExtractor, JSDocExtractor
