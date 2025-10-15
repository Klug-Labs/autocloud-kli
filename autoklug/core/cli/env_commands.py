"""
Environment management commands for autoklug CLI
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from click import echo, style

from ...env import save_env, load_env, list_envs, delete_env
from ...utils import log_header, log_success, log_error


@click.group()
def env_commands():
    """🌍 Environment management commands"""
    pass


@env_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--name', '-n', help='Environment name to save as')
def save(tool, env, name):
    """💾 Save environment to AWS Secrets Manager"""
    
    # Validate files exist if explicitly provided
    if tool and not Path(tool).exists():
        echo(style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if env and not Path(env).exists():
        echo(style(f"❌ Env file not found: {env}", fg='red'))
        sys.exit(1)
    
    async def run_save():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool, env)
            
            log_header("SAVING ENVIRONMENT")
            success = await save_env(builder.config, name)
            
            if success:
                log_success("Environment saved successfully!")
            else:
                log_error("Environment save failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Environment save error: {e}")
            sys.exit(1)
    
    asyncio.run(run_save())


@env_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--name', '-n', help='Environment name to load')
def load(tool, name):
    """📥 Load environment from AWS Secrets Manager"""
    
    async def run_load():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool)
            
            log_header("LOADING ENVIRONMENT")
            success = await load_env(builder.config, name)
            
            if success:
                log_success("Environment loaded successfully!")
            else:
                log_error("Environment load failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Environment load error: {e}")
            sys.exit(1)
    
    asyncio.run(run_load())


@env_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
def list(tool):
    """📋 List available environments"""
    
    async def run_list():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool)
            
            log_header("AVAILABLE ENVIRONMENTS")
            await list_envs(builder.config)
            
        except Exception as e:
            log_error(f"Environment list error: {e}")
            sys.exit(1)
    
    asyncio.run(run_list())


@env_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--name', '-n', help='Environment name to delete')
def delete(tool, name):
    """🗑️ Delete environment from AWS Secrets Manager"""
    
    async def run_delete():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool)
            
            log_header("DELETING ENVIRONMENT")
            success = await delete_env(builder.config, name)
            
            if success:
                log_success("Environment deleted successfully!")
            else:
                log_error("Environment deletion failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Environment deletion error: {e}")
            sys.exit(1)
    
    asyncio.run(run_delete())
