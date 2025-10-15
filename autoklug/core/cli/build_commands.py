"""
Build commands for autoklug CLI
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from click import echo, style

from ..builders import BlazingFastBuilder
from ...utils import log_header, log_success, log_error


@click.group()
def build_commands():
    """🏗️ Build commands"""
    pass


@build_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--force-update-layers', is_flag=True, help='Force update all layers')
@click.option('--verbose', is_flag=True, help='Enable verbose logging')
@click.option('--dry-run', is_flag=True, help='Show what would be built without actually building')
def build(tool, env, force_update_layers, verbose, dry_run):
    """🏗️ Build the complete Lambda infrastructure"""
    
    # Validate files exist if explicitly provided
    if tool and not Path(tool).exists():
        echo(style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if env and not Path(env).exists():
        echo(style(f"❌ Env file not found: {env}", fg='red'))
        sys.exit(1)
    
    async def run_build():
        try:
            builder = BlazingFastBuilder(tool, env, force_update_layers)
            
            if dry_run:
                log_header("DRY RUN MODE")
                log_success("Build would proceed with detected configuration")
                return
            
            success = await builder.build()
            
            if success:
                log_success("Build completed successfully!")
            else:
                log_error("Build failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Build error: {e}")
            sys.exit(1)
    
    asyncio.run(run_build())


@build_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--force-update', is_flag=True, help='Force update layers')
def layers(tool, env, force_update):
    """📦 Build only Lambda layers"""
    
    async def run_layers():
        try:
            builder = BlazingFastBuilder(tool, env, force_update)
            success = await builder.build_layers_only()
            
            if success:
                log_success("Layers built successfully!")
            else:
                log_error("Layer build failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Layer build error: {e}")
            sys.exit(1)
    
    asyncio.run(run_layers())


@build_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def functions(tool, env):
    """⚡ Build only Lambda functions"""
    
    async def run_functions():
        try:
            builder = BlazingFastBuilder(tool, env)
            success = await builder.build_functions_only()
            
            if success:
                log_success("Functions built successfully!")
            else:
                log_error("Function build failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Function build error: {e}")
            sys.exit(1)
    
    asyncio.run(run_functions())


@build_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def api(tool, env):
    """🌐 Build only API Gateway"""
    
    async def run_api():
        try:
            builder = BlazingFastBuilder(tool, env)
            success = await builder.build_api_only()
            
            if success:
                log_success("API Gateway built successfully!")
            else:
                log_error("API Gateway build failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"API Gateway build error: {e}")
            sys.exit(1)
    
    asyncio.run(run_api())
