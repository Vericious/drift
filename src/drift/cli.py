"""CLI interface for Drift."""
import click

from drift import __version__


@click.group()
@click.version_option(version=__version__, prog_name="drift")
def main() -> None:
    """Detect when your documentation no longer matches your code."""
    pass


@main.command()
@click.argument("path", default=".", type=click.Path(exists=True))
def scan(path: str) -> None:
    """Scan a project for documentation drift."""
    click.echo("Scanning... (not yet implemented)")
