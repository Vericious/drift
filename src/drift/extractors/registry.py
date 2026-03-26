"""Extractor registry for Drift.

Provides auto-registration of Extractor subclasses via the @register decorator.
"""


from drift.extractors.base import Extractor

# Global registry of extractor classes
_EXTRACTORS: list[type[Extractor]] = []


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
    """Return all registered extractor classes."""
    return list(_EXTRACTORS)


def _discover_extractors() -> None:
    """Import all extractor modules to trigger their @register decorators."""
    # Import all known extractor modules
    from drift.extractors import (
        cli_argparse,  # noqa: F401
        cli_click,  # noqa: F401
        cli_typer,  # noqa: F401
        config_file,  # noqa: F401
        dataclass_fields,  # noqa: F401
        docstring,  # noqa: F401
        env_vars,  # noqa: F401
        fastapi_routes,  # noqa: F401
        flask_routes,  # noqa: F401
        markdown,  # noqa: F401
        openapi,  # noqa: F401
        pydantic,  # noqa: F401
        rst_docs,  # noqa: F401
    )
    from drift import extractor_js  # noqa: F401
