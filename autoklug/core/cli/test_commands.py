"""
Testing commands for autoklug CLI
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from click import echo, style

from ...testing import test, test_function
from ...utils import log_header, log_success, log_error


@click.group()
def test_commands():
    """🧪 Testing commands"""
    pass


@test_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--local', is_flag=True, help='Run local tests only')
@click.option('--remote', is_flag=True, help='Run remote tests only')
def run_tests(tool, env, local, remote):
    """🧪 Run comprehensive tests"""
    
    # Validate files exist if explicitly provided
    if tool and not Path(tool).exists():
        echo(style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if env and not Path(env).exists():
        echo(style(f"❌ Env file not found: {env}", fg='red'))
        sys.exit(1)
    
    async def run_test():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool, env)
            
            log_header("RUNNING TESTS")
            success = await test(builder.config, local_only=local, remote_only=remote)
            
            if success:
                log_success("Tests completed successfully!")
            else:
                log_error("Tests failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Test error: {e}")
            sys.exit(1)
    
    asyncio.run(run_test())


@test_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.argument('function_name')
@click.option('--local', is_flag=True, help='Run local test only')
@click.option('--remote', is_flag=True, help='Run remote test only')
def test_func(tool, env, function_name, local, remote):
    """🔬 Test specific Lambda function"""
    
    async def run_function_test():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool, env)
            
            log_header(f"TESTING FUNCTION: {function_name}")
            success = await test_function(
                builder.config, 
                function_name, 
                local_only=local, 
                remote_only=remote
            )
            
            if success:
                log_success(f"Function {function_name} tests passed!")
            else:
                log_error(f"Function {function_name} tests failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Function test error: {e}")
            sys.exit(1)
    
    asyncio.run(run_function_test())
