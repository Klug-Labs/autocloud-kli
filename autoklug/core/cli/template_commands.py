"""
Template commands for autoklug CLI
"""
import click
from click import echo, style

from ...templates import template
from ...utils import log_header, log_success, log_error


@click.group()
def template_commands():
    """📋 Template commands"""
    pass


@template_commands.command()
@click.option('--type', 'template_type', 
              type=click.Choice(['basic', 'production', 'public-api']),
              help='Show specific template type')
def show(template_type):
    """📋 Show configuration templates"""
    
    try:
        log_header("CONFIGURATION TEMPLATES")
        template(template_type)
    except Exception as e:
        log_error(f"Template error: {e}")
        sys.exit(1)
