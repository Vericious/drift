# Coverage Baseline

**Date:** 2026-03-30
**pytest:** 9.0.2
**Python:** 3.13.5

## Overall Coverage: 79%

| Module | Coverage | Notes |
|--------|----------|-------|
| `drift/__init__.py` | 100% | |
| `drift/__main__.py` | 0% | CLI entry point (tested via integration) |
| `drift/cli.py` | 89% | CLI layer |
| `drift/config.py` | 87% | Config loading |
| `drift/extractor_js.py` | 92% | JavaScript/TypeScript extractor |
| `drift/extractors/__init__.py` | 100% | |
| `drift/extractors/base.py` | 100% | ABC interface |
| `drift/extractors/cli_argparse.py` | 87% | Argparse extractor |
| `drift/extractors/cli_click.py` | 79% | Click extractor |
| `drift/extractors/cli_typer.py` | 85% | Typer extractor |
| `drift/extractors/config_file.py` | 82% | YAML/TOML extractor |
| `drift/extractors/dataclass_fields.py` | 63% | Dataclass fields extractor |
| `drift/extractors/decorators.py` | 90% | Decorator-based extractor |
| `drift/extractors/deprecated.py` | 92% | Deprecated decorator extractor |
| `drift/extractors/django_urls.py` | 60% | Django URL extractor |
| `drift/extractors/dockerfile.py` | 96% | Dockerfile extractor |
| `drift/extractors/docstring.py` | 96% | Docstring extractor |
| `drift/extractors/dotenv.py` | 97% | .env file extractor |
| `drift/extractors/env_vars.py` | 80% | Environment variable extractor |
| `drift/extractors/fastapi_routes.py` | 79% | FastAPI route extractor |
| `drift/extractors/flask_routes.py` | 80% | Flask route extractor |
| `drift/extractors/graphql.py` | 91% | GraphQL schema extractor |
| `drift/extractors/makefile.py` | 95% | Makefile extractor |
| `drift/extractors/markdown.py` | 90% | Markdown extractor |
| `drift/extractors/openapi.py` | 87% | OpenAPI spec extractor |
| `drift/extractors/protocols.py` | 71% | Protocol interface extractor |
| `drift/extractors/pydantic.py` | 72% | Pydantic model extractor |
| `drift/extractors/pyproject.py` | 0% | pyproject.toml extractor (minimal tests) |
| `drift/extractors/registry.py` | 100% | Extractor registry |
| `drift/extractors/rst_docs.py` | 96% | reStructuredText extractor |
| `drift/extractors/sqlalchemy.py` | 78% | SQLAlchemy model extractor |
| `drift/extractors/terraform.py` | 87% | Terraform extractor |
| `drift/extractors/typescript.py` | 83% | TypeScript interface extractor |
| `drift/extractors/yaml_config.py` | 89% | YAML config extractor |
| `drift/git_utils.py` | 75% | Git utilities |
| `drift/matcher.py` | 95% | Drift matcher |
| `drift/models.py` | 98% | Data models |
| `drift/plugin.py` | 75% | Plugin system |
| `drift/python_extractor.py` | 65% | Python function extractor |
| `drift/reporter.py` | 65% | Reporter |
| `drift/reporters/github_pr.py` | 96% | GitHub PR reporter |
| `drift/reporters/github_summary.py` | 91% | GitHub summary reporter |
| `drift/scanner.py` | 80% | Scanner orchestration |

## v0.5.0 Coverage Targets

| Module | Target | Current | Status |
|--------|--------|---------|--------|
| `drift/extractors/registry.py` | 85% | 100% | ✅ Exceeds target |
| `drift/scanner.py` | 90% | 80% | 🔶 Below target |
| `drift/extractors/config_file.py` | 90% | 82% | 🔶 Below target |

## Notes

- Coverage is measured with `--cov=drift --cov-report=term-missing`
- Run `python3 -m pytest --cov=drift --cov-report=term-missing tests/` to reproduce
- Low-coverage modules (python_extractor, reporter, django_urls, pyproject) reflect areas for additional testing
- The `__main__.py` 0% is expected as it's an import-only entry point
- The `pyproject.py` 0% reflects an unmaintained/deprecated extractor