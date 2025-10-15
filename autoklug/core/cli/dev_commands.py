"""
Development commands for autoklug CLI
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from click import echo, style

from ...run import run as run_command
from ...templates import init, template
from ...utils import log_header, log_success, log_error


@click.group()
def dev_commands():
    """🛠️ Development commands"""
    pass


@dev_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--port', '-p', default=5000, help='Port to run the server on')
@click.option('--use-authorizer', is_flag=True, help='Enable API Gateway authorizer simulation')
@click.option('--use-auth-cache', is_flag=True, help='Enable caching for authorizer results')
@click.option('--auth-cache-ttl', default=300, help='TTL for authorizer cache in seconds')
def run(tool, env, port, use_authorizer, use_auth_cache, auth_cache_ttl):
    """🚀 Start local development server"""
    
    # Validate files exist if explicitly provided
    if tool and not Path(tool).exists():
        echo(style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if env and not Path(env).exists():
        echo(style(f"❌ Env file not found: {env}", fg='red'))
        sys.exit(1)
    
    try:
        log_header("LOCAL DEVELOPMENT SERVER")
        run_command(
            tool=tool,
            env=env,
            port=port,
            use_authorizer=use_authorizer,
            use_auth_cache=use_auth_cache,
            auth_cache_ttl=auth_cache_ttl
        )
    except Exception as e:
        log_error(f"Development server error: {e}")
        sys.exit(1)


@dev_commands.command()
@click.argument('project_path', type=click.Path())
@click.option('--type', 'project_type', default='basic', 
              type=click.Choice(['basic', 'production', 'public-api']),
              help='Type of project template to create')
def init_project(project_path, project_type):
    """📁 Initialize new project"""
    
    try:
        log_header("PROJECT INITIALIZATION")
        init(project_path, project_type)
        log_success(f"Project initialized at {project_path}")
    except Exception as e:
        log_error(f"Project initialization error: {e}")
        sys.exit(1)


@dev_commands.command()
@click.option('--type', 'template_type', 
              type=click.Choice(['basic', 'production', 'public-api']),
              help='Show specific template type')
def show_template(template_type):
    """📋 Show configuration templates"""
    
    try:
        log_header("CONFIGURATION TEMPLATES")
        template(template_type)
    except Exception as e:
        log_error(f"Template error: {e}")
        sys.exit(1)
