"""
Environment Management for Autoklug

Tools for saving and loading environment variables to/from AWS Secrets Manager.
"""
import json
import click
from pathlib import Path
from typing import Dict, Optional
import datetime

from .utils import (
    ConfigManager, log_header, log_step, log_success, log_warning, 
    log_error, log_info, log_detail, detect_project_context, find_best_config_files
)


class EnvironmentManager:
    """Manages environment variables using AWS Secrets Manager"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.app_name = config.app_name
        
        # Create secrets client with the region from .tool file
        region = config.tool_config.get('AWS_REGION', 'us-east-1')
        self.secrets_client = config.session.client('secretsmanager', region_name=region)
        
        log_detail(f"Using AWS region: {region}")
    
    def _get_secret_name(self, identifier: str) -> str:
        """Generate secret name for environment"""
        return f"autoklug-envs-{self.app_name}-{identifier}"
    
    def save_env_to_secrets(self, identifier: str, env_file_path: str) -> bool:
        """Save local .env file to AWS Secrets Manager"""
        log_header(f"SAVING ENVIRONMENT: {identifier}")
        
        # Read local .env file
        env_path = Path(env_file_path)
        if not env_path.exists():
            log_error(f"Environment file not found: {env_file_path}")
            return False
        
        try:
            # Read environment variables
            env_vars = {}
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
            
            if not env_vars:
                log_warning("No environment variables found in file")
                return False
            
            # Convert to JSON
            env_json = json.dumps(env_vars, indent=2)
            
            # Save to Secrets Manager
            secret_name = self._get_secret_name(identifier)
            
            try:
                # Check if secret exists
                self.secrets_client.describe_secret(SecretId=secret_name)
                log_info(f"Secret exists, updating: {secret_name}")
                
                # Update existing secret
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=env_json,
                    Description=f"Environment variables for {self.app_name} ({identifier})"
                )
                
            except self.secrets_client.exceptions.ResourceNotFoundException:
                log_info(f"Creating new secret: {secret_name}")
                
                # Create new secret
                self.secrets_client.create_secret(
                    Name=secret_name,
                    Description=f"Environment variables for {self.app_name} ({identifier})",
                    SecretString=env_json
                )
            
            log_success(f"Environment saved to Secrets Manager: {secret_name}")
            log_detail(f"Variables saved: {len(env_vars)}")
            
            return True
            
        except Exception as e:
            log_error(f"Failed to save environment: {e}")
            return False
    
    def load_env_from_secrets(self, identifier: str, output_path: str) -> bool:
        """Load environment from AWS Secrets Manager to local file"""
        log_header(f"LOADING ENVIRONMENT: {identifier}")
        
        try:
            # Get secret from Secrets Manager
            secret_name = self._get_secret_name(identifier)
            
            try:
                response = self.secrets_client.get_secret_value(SecretId=secret_name)
                secret_string = response['SecretString']
                
                # Parse JSON
                env_vars = json.loads(secret_string)
                
                if not env_vars:
                    log_warning("No environment variables found in secret")
                    return False
                
                # Write to local file
                output_file = Path(output_path)
                with open(output_file, 'w') as f:
                    f.write(f"# Environment variables loaded from AWS Secrets Manager\n")
                    f.write(f"# Secret: {secret_name}\n")
                    f.write(f"# Loaded at: {datetime.datetime.now().isoformat()}\n\n")
                    
                    for key, value in env_vars.items():
                        f.write(f"{key}={value}\n")
                
                log_success(f"Environment loaded to: {output_path}")
                log_detail(f"Variables loaded: {len(env_vars)}")
                
                return True
                
            except self.secrets_client.exceptions.ResourceNotFoundException:
                log_error(f"Secret not found: {secret_name}")
                return False
                
        except Exception as e:
            log_error(f"Failed to load environment: {e}")
            return False
    
    def list_environments(self) -> list:
        """List available environments in Secrets Manager"""
        log_header("LISTING ENVIRONMENTS")
        
        try:
            # List secrets with our naming pattern
            prefix = f"autoklug-envs-{self.app_name}-"
            
            paginator = self.secrets_client.get_paginator('list_secrets')
            environments = []
            
            for page in paginator.paginate():
                for secret in page['SecretList']:
                    if secret['Name'].startswith(prefix):
                        identifier = secret['Name'][len(prefix):]
                        environments.append({
                            'identifier': identifier,
                            'secret_name': secret['Name'],
                            'description': secret.get('Description', ''),
                            'last_modified': secret.get('LastChangedDate', ''),
                            'version_id': secret.get('VersionId', '')
                        })
            
            if environments:
                log_success(f"Found {len(environments)} environments:")
                for env in environments:
                    log_detail(f"  • {env['identifier']} - {env['description']}")
            else:
                log_info("No environments found")
            
            return environments
            
        except Exception as e:
            log_error(f"Failed to list environments: {e}")
            return []
    
    def delete_environment(self, identifier: str) -> bool:
        """Delete environment from Secrets Manager"""
        log_header(f"DELETING ENVIRONMENT: {identifier}")
        
        try:
            secret_name = self._get_secret_name(identifier)
            
            # Delete secret
            self.secrets_client.delete_secret(
                SecretId=secret_name,
                ForceDeleteWithoutRecovery=True
            )
            
            log_success(f"Environment deleted: {secret_name}")
            return True
            
        except self.secrets_client.exceptions.ResourceNotFoundException:
            log_warning(f"Environment not found: {identifier}")
            return False
        except Exception as e:
            log_error(f"Failed to delete environment: {e}")
            return False


@click.command()
@click.argument('identifier')
@click.option('--tool', '-t',
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.option('--env', '-e',
              help='Path to .env file to save (defaults to .env.<identifier>)')
def save_env(identifier, tool, env):
    """💾 Save environment variables to AWS Secrets Manager"""
    
    # Detect project context if not provided
    if not tool:
        context = detect_project_context()
        detected_tool, _ = find_best_config_files(context)
        tool = detected_tool
        
        if not tool:
            click.echo(click.style("❌ No .tool file found! Create one to configure your build.", fg='red'))
            sys.exit(1)
    
    # Determine env file path
    if not env:
        env = f".env.{identifier}"
    
    # Validate files exist
    if not Path(tool).exists():
        click.echo(click.style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    if not Path(env).exists():
        click.echo(click.style(f"❌ Environment file not found: {env}", fg='red'))
        sys.exit(1)
    
    # Load configuration
    config = ConfigManager(tool)
    
    # Create environment manager
    env_manager = EnvironmentManager(config)
    
    # Save environment
    success = env_manager.save_env_to_secrets(identifier, env)
    sys.exit(0 if success else 1)


@click.command()
@click.argument('identifier')
@click.option('--tool', '-t',
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.option('--output', '-o',
              help='Output file path (defaults to .env.<identifier>)')
def load_env(identifier, tool, output):
    """📥 Load environment variables from AWS Secrets Manager"""
    
    # Detect project context if not provided
    if not tool:
        context = detect_project_context()
        detected_tool, _ = find_best_config_files(context)
        tool = detected_tool
        
        if not tool:
            click.echo(click.style("❌ No .tool file found! Create one to configure your build.", fg='red'))
            sys.exit(1)
    
    # Determine output file path
    if not output:
        output = f".env.{identifier}"
    
    # Validate tool file exists
    if not Path(tool).exists():
        click.echo(click.style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    # Load configuration
    config = ConfigManager(tool)
    
    # Create environment manager
    env_manager = EnvironmentManager(config)
    
    # Load environment
    success = env_manager.load_env_from_secrets(identifier, output)
    sys.exit(0 if success else 1)


@click.command()
@click.option('--tool', '-t',
              help='Path to .tool configuration file (auto-detected if not provided)')
def list_envs(tool):
    """📋 List available environments in AWS Secrets Manager"""
    
    # Detect project context if not provided
    if not tool:
        context = detect_project_context()
        detected_tool, _ = find_best_config_files(context)
        tool = detected_tool
        
        if not tool:
            click.echo(click.style("❌ No .tool file found! Create one to configure your build.", fg='red'))
            sys.exit(1)
    
    # Validate tool file exists
    if not Path(tool).exists():
        click.echo(click.style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    # Load configuration
    config = ConfigManager(tool)
    
    # Create environment manager
    env_manager = EnvironmentManager(config)
    
    # List environments
    environments = env_manager.list_environments()
    sys.exit(0)


@click.command()
@click.argument('identifier')
@click.option('--tool', '-t',
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.confirmation_option(prompt='Are you sure you want to delete this environment?')
def delete_env(identifier, tool):
    """🗑️ Delete environment from AWS Secrets Manager"""
    
    # Detect project context if not provided
    if not tool:
        context = detect_project_context()
        detected_tool, _ = find_best_config_files(context)
        tool = detected_tool
        
        if not tool:
            click.echo(click.style("❌ No .tool file found! Create one to configure your build.", fg='red'))
            sys.exit(1)
    
    # Validate tool file exists
    if not Path(tool).exists():
        click.echo(click.style(f"❌ Tool file not found: {tool}", fg='red'))
        sys.exit(1)
    
    # Load configuration
    config = ConfigManager(tool)
    
    # Create environment manager
    env_manager = EnvironmentManager(config)
    
    # Delete environment
    success = env_manager.delete_environment(identifier)
    sys.exit(0 if success else 1)
