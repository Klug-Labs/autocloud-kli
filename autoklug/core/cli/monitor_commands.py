"""
Monitoring commands for autoklug CLI
"""
import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from click import echo, style

from ...monitoring import setup_monitoring, monitoring_status, CloudWatchManager
from ...utils import log_header, log_success, log_error


@click.group()
def monitor_commands():
    """📊 Monitoring commands"""
    pass


@monitor_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def setup(tool, env):
    """🔧 Setup monitoring and observability"""
    
    # Validate files exist if explicitly provided
    if tool and not Path(tool).exists():
        echo(style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if env and not Path(env).exists():
        echo(style(f"❌ Env file not found: {env}", fg='red'))
        sys.exit(1)
    
    async def run_setup():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool, env)
            
            log_header("MONITORING SETUP")
            success = await setup_monitoring(builder.config)
            
            if success:
                log_success("Monitoring setup completed successfully!")
            else:
                log_error("Monitoring setup failed!")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Monitoring setup error: {e}")
            sys.exit(1)
    
    asyncio.run(run_setup())


@monitor_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def status(tool, env):
    """📈 Check monitoring status"""
    
    async def run_status():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool, env)
            
            log_header("MONITORING STATUS")
            await monitoring_status(builder.config)
            
        except Exception as e:
            log_error(f"Monitoring status error: {e}")
            sys.exit(1)
    
    asyncio.run(run_status())


@monitor_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--function', '-f', help='Specific function name to get logs for')
@click.option('--lines', '-n', default=50, help='Number of log lines to retrieve')
def logs(tool, env, function, lines):
    """📝 View Lambda function logs"""
    
    async def run_logs():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool, env)
            
            log_header("LAMBDA FUNCTION LOGS")
            cloudwatch = CloudWatchManager(builder.config)
            
            if function:
                logs = await cloudwatch.get_function_logs(function, lines)
                for log_entry in logs:
                    echo(f"{log_entry['timestamp']}: {log_entry['message']}")
            else:
                log_error("Please specify a function name with --function")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Logs error: {e}")
            sys.exit(1)
    
    asyncio.run(run_logs())


@monitor_commands.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
@click.option('--function', '-f', help='Specific function name to get metrics for')
@click.option('--period', default=300, help='Metrics period in seconds')
def metrics(tool, env, function, period):
    """📊 View Lambda function metrics"""
    
    async def run_metrics():
        try:
            from ...core.builders import BlazingFastBuilder
            builder = BlazingFastBuilder(tool, env)
            
            log_header("LAMBDA FUNCTION METRICS")
            cloudwatch = CloudWatchManager(builder.config)
            
            if function:
                metrics = await cloudwatch.get_function_metrics(function, period)
                for metric in metrics:
                    echo(f"{metric['MetricName']}: {metric['Value']}")
            else:
                log_error("Please specify a function name with --function")
                sys.exit(1)
                
        except Exception as e:
            log_error(f"Metrics error: {e}")
            sys.exit(1)
    
    asyncio.run(run_metrics())
