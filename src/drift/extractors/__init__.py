"""Drift extractors package."""

from drift.extractors.cli_argparse import ArgparseExtractor
from drift.extractors.cli_click import ClickExtractor
from drift.extractors.cli_typer import TyperExtractor
from drift.extractors.config_file import ConfigFileExtractor
from drift.extractors.dataclass_fields import DataclassFieldsExtractor
from drift.extractors.decorators import DecoratorExtractor
from drift.extractors.deprecated import DeprecatedExtractor
from drift.extractors.django_urls import DjangoURLsExtractor
from drift.extractors.docstring import DocstringExtractor
from drift.extractors.env_vars import EnvVarExtractor
from drift.extractors.fastapi_routes import FastAPIRoutesExtractor
from drift.extractors.flask_routes import FlaskRoutesExtractor

# Import all extractors to trigger their @register decorators
from drift.extractors.markdown import MarkdownExtractor
from drift.extractors.pydantic import PydanticExtractor
from drift.extractors.registry import get_extractors
from drift.extractors.terraform import TerraformExtractor
from drift.extractors.sqlalchemy import SQLAlchemyExtractor
from drift.extractor_js import JSDocExtractor

__all__ = [
    "MarkdownExtractor",
    "DocstringExtractor",
    "ArgparseExtractor",
    "ClickExtractor",
    "TyperExtractor",
    "PydanticExtractor",
    "ConfigFileExtractor",
    "FlaskRoutesExtractor",
    "FastAPIRoutesExtractor",
    "DjangoURLsExtractor",
    "SQLAlchemyExtractor",
    "TerraformExtractor",
    "EnvVarExtractor",
    "DataclassFieldsExtractor",
    "DecoratorExtractor",
    "DeprecatedExtractor",
    "JSDocExtractor",
    "get_extractors",
]
