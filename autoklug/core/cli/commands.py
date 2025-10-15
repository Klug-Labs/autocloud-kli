"""
Main CLI interface for autoklug
"""
import click
from click import echo, style

from ...utils import ConfigManager, log_header, log_info, detect_project_context, find_best_config_files
from .build_commands import build_commands
from .deploy_commands import deploy_commands
from .dev_commands import dev_commands
from .monitor_commands import monitor_commands
from .env_commands import env_commands
from .test_commands import test_commands
from .template_commands import template_commands
from .layer_commands import layer_commands


@click.group()
@click.version_option(version='2.0.0', prog_name='Autoklug')
def cli():
    """🚀 Autoklug - Blazing Fast AWS Lambda Build System"""
    pass


# Add all command groups
cli.add_command(build_commands)
cli.add_command(deploy_commands)
cli.add_command(dev_commands)
cli.add_command(monitor_commands)
cli.add_command(env_commands)
cli.add_command(test_commands)
cli.add_command(template_commands)
cli.add_command(layer_commands)


@cli.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def config(tool, env):
    """⚙️ Show configuration information"""
    try:
        # Detect project context if not provided
        if not tool or not env:
            context = detect_project_context()
            detected_tool, detected_env = find_best_config_files(context)
            
            tool = tool or detected_tool
            env = env or detected_env
            
            log_info(f"Auto-detected project context:")
            log_info(f"  Directory: {context['current_dir']}")
            log_info(f"  Infrastructure: {context['infra']}")
            log_info(f"  Public API: {context['is_public']}")
        
        # Load configuration
        config = ConfigManager(tool, env)
        
        log_header("CONFIGURATION INFORMATION")
        log_info(f"Tool config: {tool}")
        log_info(f"Env config: {env or 'None'}")
        log_info(f"App name: {config.tool_config.get('APP_NAME', 'Not set')}")
        log_info(f"AWS region: {config.tool_config.get('AWS_REGION', 'Not set')}")
        log_info(f"AWS account: {config.tool_config.get('AWS_ACCOUNT_ID', 'Not set')}")
        log_info(f"Lambda runtime: {config.tool_config.get('LAMBDA_RUNTIME', 'Not set')}")
        log_info(f"API path: {config.api_path}")
        log_info(f"Layer path: {config.layer_path}")
        log_info(f"Public build: {config.is_public_build}")
        
    except Exception as e:
        echo(style(f"❌ Error loading configuration: {e}", fg='red'))
        raise click.Abort()


@cli.command()
@click.option('--tool', '-t', help='Path to .tool configuration file')
@click.option('--env', '-e', help='Path to .env file for environment variables')
def detect(tool, env):
    """🔍 Show project detection information"""
    try:
        context = detect_project_context()
        detected_tool, detected_env = find_best_config_files(context)
        
        log_header("PROJECT CONTEXT DETECTION")
        log_info(f"Current directory: {context['current_dir']}")
        log_info(f"Detected infrastructure: {context['infra']}")
        log_info(f"Public API detected: {context['is_public']}")
        
        log_info(f"Configuration files:")
        log_info(f"  Tool files found: {context['tool_files']}")
        log_info(f"  Env files found: {context['env_files']}")
        log_info(f"  Selected tool file: {detected_tool}")
        log_info(f"  Selected env file: {detected_env}")
        
        log_info(f"Project structure:")
        log_info(f"  API paths found: {context['api_paths']}")
        log_info(f"  Layer paths found: {context['layer_paths']}")
        
    except Exception as e:
        echo(style(f"❌ Error detecting project: {e}", fg='red'))
        raise click.Abort()
