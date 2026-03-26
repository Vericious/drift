"""Drift extractors package."""
from drift.extractors.registry import get_extractors

# Import all extractors to trigger their @register decorators
from drift.extractors.markdown import MarkdownExtractor
from drift.extractors.docstring import DocstringExtractor
from drift.extractors.cli_argparse import ArgparseExtractor
from drift.extractors.cli_click import ClickExtractor
from drift.extractors.cli_typer import TyperExtractor
from drift.extractors.pydantic import PydanticExtractor
from drift.extractors.config_file import ConfigFileExtractor

__all__ = [
    "MarkdownExtractor",
    "DocstringExtractor",
    "ArgparseExtractor",
    "ClickExtractor",
    "TyperExtractor",
    "PydanticExtractor",
    "ConfigFileExtractor",
    "get_extractors",
]
