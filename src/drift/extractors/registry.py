"""Extractor registry for Drift.

Provides auto-registration of Extractor subclasses via the @register decorator.
"""
from typing import Type

from drift.extractors.base import Extractor


# Global registry of extractor classes
_EXTRACTORS: list[Type[Extractor]] = []


def register(cls: Type[Extractor]) -> Type[Extractor]:
    """Register an Extractor subclass.

    Usage:
        @register
        class MyExtractor(Extractor):
            ...
    """
    _EXTRACTORS.append(cls)
    return cls


def get_extractors() -> list[Type[Extractor]]:
    """Return all registered extractor classes."""
    return list(_EXTRACTORS)


def _discover_extractors() -> None:
    """Import all extractor modules to trigger their @register decorators."""
    # Import all known extractor modules
    from drift.extractors import markdown  # noqa: F401
    from drift.extractors import docstring  # noqa: F401
    from drift.extractors import cli_argparse  # noqa: F401
    from drift.extractors import cli_click  # noqa: F401
    from drift.extractors import cli_typer  # noqa: F401
    from drift.extractors import pydantic  # noqa: F401
    from drift.extractors import config_file  # noqa: F401
    from drift.extractors import flask_routes  # noqa: F401
    from drift.extractors import fastapi_routes  # noqa: F401
    from drift.extractors import env_vars  # noqa: F401
    from drift.extractors import dataclass_fields  # noqa: F401
    from drift.extractors import rst_docs  # noqa: F401
    from drift.extractors import openapi  # noqa: F401
