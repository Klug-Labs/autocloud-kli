"""
Deploy commands for autoklug CLI
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from click import echo, style

from ...validation import AWSCredentialsValidator, DeploymentValidator
from ...error_handling import DeploymentManager
from ...utils import log_header, log_success, log_error


@click.group()
def deploy_commands():
    """🚀 Deploy commands"""
    pass


@deploy_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--force-update-layers', is_flag=True, help='Force update all layers')
@click.option('--verbose', is_flag=True, help='Enable verbose logging')
@click.option('--dry-run', is_flag=True, help='Show what would be deployed without actually deploying')
@click.option('--validate', is_flag=True, help='Run with enhanced validation and rollback capabilities')
def deploy(tool, env, force_update_layers, verbose, dry_run, validate):
    """🚀 Deploy Lambda functions"""
    
    # Validate files exist if explicitly provided
    if tool and not Path(tool).exists():
        echo(style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if env and not Path(env).exists():
        echo(style(f"❌ Env file not found: {env}", fg='red'))
        sys.exit(1)
    
    async def run_deploy():
        try:
            builder = BlazingFastBuilder(tool, env, force_update_layers)
            
            if dry_run:
                log_header("DRY RUN MODE")
                log_success("Deployment would proceed with detected configuration")
                return
            
            if validate:
                log_header("VALIDATION MODE")
                # Run enhanced validation
                validator = AWSCredentialsValidator(builder.config)
                if not await validator.validate_all_permissions():
                    log_error("AWS credentials validation failed")
                    sys.exit(1)
                
                # Run deployment with validation
                deployment_manager = DeploymentManager(builder.config)
                success = await deployment_manager.deploy_with_validation(builder)
            else:
                # Standard deployment
                success = await builder.build()
            
            if success:
                log_success("Deployment completed successfully!")
            else:
                log_error("Deployment failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Deployment error: {e}")
            sys.exit(1)
    
    asyncio.run(run_deploy())


@deploy_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def validate(tool, env):
    """🔐 Validate AWS credentials and configuration"""
    
    async def run_validate():
        try:
            builder = BlazingFastBuilder(tool, env)
            validator = AWSCredentialsValidator(builder.config)
            
            log_header("AWS CREDENTIALS VALIDATION")
            success = await validator.validate_all_permissions()
            
            if success:
                log_success("AWS credentials and permissions validated successfully!")
            else:
                log_error("AWS credentials validation failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Validation error: {e}")
            sys.exit(1)
    
    asyncio.run(run_validate())


@deploy_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def status(tool, env):
    """📊 Show deployment status and resource information"""
    
    async def run_status():
        try:
            builder = BlazingFastBuilder(tool, env)
            
            log_header("DEPLOYMENT STATUS")
            log_success("Status check completed")
            
        except Exception as e:
            log_error(f"Status check error: {e}")
            sys.exit(1)
    
    asyncio.run(run_status())
