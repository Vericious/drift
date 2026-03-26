"""Sample click CLI for testing the ClickExtractor."""
import click

@click.group()
@click.version_option()
def cli():
    """Sample CLI tool."""
    pass

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--format', '-f', type=click.Choice(['json', 'console']), default='console', help='Output format')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.option('--config', type=click.Path(), default=None, help='Config file path')
def scan(path, format, verbose, config):
    """Scan a project."""
    pass
