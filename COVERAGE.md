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

## Notes

- Coverage is measured with `--cov=drift --cov-report=term-missing`
- Run `python3 -m pytest --cov=drift --cov-report=term-missing tests/` to reproduce
- Low-coverage modules (registry, pydantic, python_extractor) reflect areas for additional testing
- The `__main__.py` 0% is expected as it's an import-only entry point
