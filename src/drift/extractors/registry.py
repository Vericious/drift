"""Extractor registry for Drift.

Provides auto-registration of Extractor subclasses via the @register decorator.
"""

from drift.extractors.base import Extractor

# Global registry of extractor classes
_EXTRACTORS: list[type[Extractor]] = []
_DISCOVERY_DONE = False


def register(cls: type[Extractor]) -> type[Extractor]:
    """Register an Extractor subclass.

    Usage:
        @register
        class MyExtractor(Extractor):
            ...
    """
    _EXTRACTORS.append(cls)
    return cls


def get_extractors() -> list[type[Extractor]]:
    """Return all registered extractor classes (built-in + plugins)."""
    _ensure_discovered()
    return list(_EXTRACTORS)


def _ensure_discovered() -> None:
    """Ensure extractors have been discovered and registered (idempotent)."""
    global _DISCOVERY_DONE
    if _DISCOVERY_DONE:
        return
    _discover_extractors()
    _DISCOVERY_DONE = True


def _discover_extractors() -> None:
    """Import all built-in extractor modules and load plugins to trigger @register decorators."""
    # Import all known extractor modules
    from drift.extractors import (
        cli_argparse,  # noqa: F401
        cli_click,  # noqa: F401
        cli_typer,  # noqa: F401
        config_file,  # noqa: F401
        dataclass_fields,  # noqa: F401
        decorators,  # noqa: F401
        deprecated,  # noqa: F401
        django_urls,  # noqa: F401
        docstring,  # noqa: F401
        env_vars,  # noqa: F401
        fastapi_routes,  # noqa: F401
        flask_routes,  # noqa: F401
        graphql,  # noqa: F401
        markdown,  # noqa: F401
        openapi,  # noqa: F401
        pydantic,  # noqa: F401
        rst_docs,  # noqa: F401
        sqlalchemy,  # noqa: F401
        terraform,  # noqa: F401
        yaml_config,  # noqa: F401
        dockerfile,  # noqa: F401
        makefile,  # noqa: F401
    )
    from drift import extractor_js  # noqa: F401
    from drift.extractors import typescript  # noqa: F401

    # Import PythonExtractor to trigger @register
    from drift.python_extractor import PythonExtractor  # noqa: F401

    # Load plugins via entry_points
    from drift.plugin import load_plugins
    load_plugins()
