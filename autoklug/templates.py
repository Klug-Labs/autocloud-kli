"""
Configuration Templates and Project Initialization Module

Provides templates and initialization for new autoklug projects.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional
import click
from .utils import log_header, log_step, log_success, log_error, log_info, log_detail


class ConfigurationTemplates:
    """Generate configuration templates for different scenarios"""
    
    @staticmethod
    def get_basic_tool_template() -> str:
        """Generate basic .tool template"""
        return """# AWS Configuration
AWS_PROFILE_BUILD=default
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Application Configuration
APP_NAME=my-app
INFRA=dev

# Lambda Configuration
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role
LAMBDA_TIMEOUT=30
LAMBDA_MEMORY_SIZE=512

# Layer Configuration
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
LAYER_ARCHITECTURE=x86_64

# API Configuration
API_PATH=./api
AUTHORIZER_FUNCTION_NAME=api-my-app-dev-authorizer

# Monitoring Configuration
ENABLE_XRAY=true
ENABLE_CLOUDWATCH_ALARMS=true
LOG_RETENTION_DAYS=14
"""

    @staticmethod
    def get_production_tool_template() -> str:
        """Generate production-ready template"""
        return """# Production Configuration
APP_NAME=my-app-prod
INFRA=prod
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Lambda Configuration
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role
LAMBDA_TIMEOUT=60
LAMBDA_MEMORY_SIZE=1024
ENABLE_PROVISIONED_CONCURRENCY=true
PROVISIONED_CONCURRENCY_COUNT=10

# Layer Configuration
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
LAYER_ARCHITECTURE=x86_64

# API Configuration
API_PATH=./api
AUTHORIZER_FUNCTION_NAME=api-my-app-prod-authorizer

# Security Configuration
ENABLE_ENCRYPTION=true
ENABLE_SECRETS_MANAGER=true

# Monitoring Configuration
ENABLE_XRAY=true
ENABLE_CLOUDWATCH_ALARMS=true
LOG_RETENTION_DAYS=30
ALARM_SNS_TOPIC=arn:aws:sns:us-east-1:123456789012:alerts
"""

    @staticmethod
    def get_public_api_tool_template() -> str:
        """Generate public API template"""
        return """# Public API Configuration
APP_NAME=my-public-api
INFRA=public
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012

# Lambda Configuration
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role
LAMBDA_TIMEOUT=30
LAMBDA_MEMORY_SIZE=512

# Layer Configuration
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
LAYER_ARCHITECTURE=x86_64

# Public API Configuration
API_PATH=./api_public
# No authorizer for public API
RATE_LIMIT_REQUESTS_PER_SECOND=100
RATE_LIMIT_BURST=200

# CORS Configuration
CORS_ORIGINS=*
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS
CORS_HEADERS=Content-Type,Authorization

# Monitoring Configuration
ENABLE_XRAY=true
ENABLE_CLOUDWATCH_ALARMS=true
LOG_RETENTION_DAYS=7
"""

    @staticmethod
    def get_basic_env_template() -> str:
        """Generate basic .env template"""
        return """# Environment Variables
# Add your environment-specific variables here

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/mydb
DATABASE_POOL_SIZE=10

# External API Configuration
EXTERNAL_API_URL=https://api.example.com
EXTERNAL_API_KEY=your-api-key-here

# Application Configuration
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=development

# Feature Flags
ENABLE_FEATURE_X=true
ENABLE_FEATURE_Y=false
"""

    @staticmethod
    def get_production_env_template() -> str:
        """Generate production .env template"""
        return """# Production Environment Variables
# WARNING: Never commit production secrets to version control!

# Database Configuration
DATABASE_URL=${DATABASE_URL}
DATABASE_POOL_SIZE=20

# External API Configuration
EXTERNAL_API_URL=${EXTERNAL_API_URL}
EXTERNAL_API_KEY=${EXTERNAL_API_KEY}

# Application Configuration
DEBUG=false
LOG_LEVEL=WARNING
ENVIRONMENT=production

# Feature Flags
ENABLE_FEATURE_X=true
ENABLE_FEATURE_Y=true

# Security Configuration
JWT_SECRET=${JWT_SECRET}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
"""

    @staticmethod
    def get_project_structure() -> Dict[str, List[str]]:
        """Get recommended project structure"""
        return {
            "api": [
                "__init__.py",
                "main.py",
                "handlers/",
                "utils/",
                "requirements.txt"
            ],
            "api_public": [
                "__init__.py",
                "main.py",
                "handlers/",
                "utils/",
                "requirements.txt"
            ],
            "layers": [
                "shared/",
                "thirdparty/",
                "requirements.txt"
            ],
            "tests": [
                "__init__.py",
                "test_handlers.py",
                "test_utils.py",
                "conftest.py"
            ],
            "scripts": [
                "deploy.sh",
                "test.sh",
                "lint.sh"
            ],
            "docs": [
                "README.md",
                "API.md",
                "DEPLOYMENT.md"
            ]
        }


class ProjectInitializer:
    """Initialize new autoklug projects"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.templates = ConfigurationTemplates()
    
    def initialize_project(self, project_type: str = "basic", app_name: str = None) -> bool:
        """Initialize a new project"""
        log_header("PROJECT INITIALIZATION")
        
        try:
            # Create project directory
            self.project_path.mkdir(parents=True, exist_ok=True)
            log_step("1", f"Created project directory: {self.project_path}")
            
            # Generate configuration files
            self._create_config_files(project_type, app_name)
            log_step("2", "Created configuration files")
            
            # Create project structure
            self._create_project_structure()
            log_step("3", "Created project structure")
            
            # Create example files
            self._create_example_files()
            log_step("4", "Created example files")
            
            # Create documentation
            self._create_documentation()
            log_step("5", "Created documentation")
            
            log_success("Project initialization completed successfully!")
            log_info(f"Project created at: {self.project_path}")
            log_info("Next steps:")
            log_detail("1. Update .tool file with your AWS account details")
            log_detail("2. Update .env file with your environment variables")
            log_detail("3. Add your Lambda functions to the api/ directory")
            log_detail("4. Run 'autoklug build' to deploy")
            
            return True
            
        except Exception as e:
            log_error(f"Project initialization failed: {e}")
            return False
    
    def _create_config_files(self, project_type: str, app_name: str):
        """Create configuration files"""
        # Create .tool file
        if project_type == "production":
            tool_content = self.templates.get_production_tool_template()
        elif project_type == "public":
            tool_content = self.templates.get_public_api_tool_template()
        else:
            tool_content = self.templates.get_basic_tool_template()
        
        # Replace app name if provided
        if app_name:
            tool_content = tool_content.replace("my-app", app_name)
            tool_content = tool_content.replace("my-public-api", app_name)
        
        tool_file = self.project_path / ".tool"
        tool_file.write_text(tool_content)
        
        # Create .env file
        if project_type == "production":
            env_content = self.templates.get_production_env_template()
        else:
            env_content = self.templates.get_basic_env_template()
        
        env_file = self.project_path / ".env"
        env_file.write_text(env_content)
        
        # Create .env.example file
        env_example_file = self.project_path / ".env.example"
        env_example_file.write_text(env_content)
    
    def _create_project_structure(self):
        """Create recommended project structure"""
        structure = self.templates.get_project_structure()
        
        for directory, files in structure.items():
            dir_path = self.project_path / directory
            dir_path.mkdir(exist_ok=True)
            
            for file_or_dir in files:
                file_path = dir_path / file_or_dir
                if file_or_dir.endswith('/'):
                    # It's a directory
                    file_path.mkdir(exist_ok=True)
                else:
                    # It's a file
                    if not file_path.exists():
                        file_path.touch()
    
    def _create_example_files(self):
        """Create example files"""
        # Create example Lambda function
        api_dir = self.project_path / "api"
        if api_dir.exists():
            main_py = api_dir / "main.py"
            main_py.write_text('''"""
Example Lambda function handler
"""

import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """
    Example Lambda function handler
    
    Args:
        event: AWS Lambda event object
        context: AWS Lambda context object
    
    Returns:
        dict: Response object
    """
    logger.info("Processing request")
    
    # Extract request data
    http_method = event.get('httpMethod', 'GET')
    path = event.get('path', '/')
    body = event.get('body', '{}')
    
    # Parse body if it's JSON
    try:
        if body:
            body_data = json.loads(body)
        else:
            body_data = {}
    except json.JSONDecodeError:
        body_data = {}
    
    # Process request
    response_data = {
        'message': 'Hello from Lambda!',
        'method': http_method,
        'path': path,
        'body': body_data,
        'timestamp': context.aws_request_id
    }
    
    # Return response
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        },
        'body': json.dumps(response_data)
    }
''')
            
            # Create requirements.txt
            requirements_txt = api_dir / "requirements.txt"
            requirements_txt.write_text('''# Lambda function dependencies
# Add your Python dependencies here

# Example dependencies
requests>=2.28.0
boto3>=1.26.0
''')
    
    def _create_documentation(self):
        """Create project documentation"""
        docs_dir = self.project_path / "docs"
        if docs_dir.exists():
            # Create README.md
            readme_md = docs_dir / "README.md"
            readme_md.write_text('''# My Autoklug Project

This project is built with [Autoklug](https://github.com/lewisklug/autoklug) - a blazing fast AWS Lambda deployment system.

## Quick Start

1. **Configure AWS credentials** in `.tool` file
2. **Set environment variables** in `.env` file
3. **Add your Lambda functions** to the `api/` directory
4. **Deploy** with `autoklug build`

## Project Structure

```
├── api/                    # Lambda functions
├── layers/                 # Lambda layers
├── tests/                  # Test files
├── scripts/                # Deployment scripts
├── docs/                   # Documentation
├── .tool                   # AWS configuration
├── .env                    # Environment variables
└── .env.example            # Environment variables template
```

## Commands

- `autoklug build` - Build and deploy
- `autoklug deploy` - Deploy with validation
- `autoklug run` - Local development server
- `autoklug validate` - Validate configuration
- `autoklug status` - Show deployment status

## Documentation

- [API Documentation](API.md)
- [Deployment Guide](DEPLOYMENT.md)
''')
            
            # Create API.md
            api_md = docs_dir / "API.md"
            api_md.write_text('''# API Documentation

## Endpoints

### GET /
Returns a hello message with request information.

**Response:**
```json
{
  "message": "Hello from Lambda!",
  "method": "GET",
  "path": "/",
  "body": {},
  "timestamp": "request-id"
}
```

## Error Handling

All endpoints return standard HTTP status codes:
- `200` - Success
- `400` - Bad Request
- `401` - Unauthorized
- `404` - Not Found
- `500` - Internal Server Error

## Authentication

Configure authentication in your `.tool` file using the `AUTHORIZER_FUNCTION_NAME` setting.
''')
            
            # Create DEPLOYMENT.md
            deployment_md = docs_dir / "DEPLOYMENT.md"
            deployment_md.write_text('''# Deployment Guide

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Python 3.8+** installed
4. **Autoklug** installed (`pip install autoklug`)

## Configuration

### 1. AWS Configuration (.tool file)

```bash
# Update these values in your .tool file
AWS_PROFILE_BUILD=your-profile
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=your-account-id
APP_NAME=your-app-name
```

### 2. Environment Variables (.env file)

```bash
# Add your environment-specific variables
DATABASE_URL=your-database-url
API_KEY=your-api-key
```

## Deployment

### Development Deployment

```bash
# Build and deploy to development
autoklug build

# Or with explicit configuration
autoklug build --tool .tool.dev --env .env.dev
```

### Production Deployment

```bash
# Deploy with validation and rollback
autoklug deploy --tool .tool.prod --env .env.prod
```

### Local Development

```bash
# Start local development server
autoklug run

# With custom port
autoklug run --port 8080
```

## Monitoring

```bash
# Check deployment status
autoklug status

# View logs
autoklug logs --function-name my-function

# View metrics
autoklug metrics --function-name my-function
```

## Troubleshooting

### Common Issues

1. **AWS Credentials**: Ensure your AWS profile is configured correctly
2. **Permissions**: Check that your AWS user has the required permissions
3. **Configuration**: Validate your `.tool` and `.env` files

### Validation

```bash
# Validate configuration before deployment
autoklug validate
```
''')


# CLI Commands for project initialization
@click.command()
@click.argument('project_path', type=click.Path())
@click.option('--type', '-t', 
              type=click.Choice(['basic', 'production', 'public']),
              default='basic',
              help='Project type to initialize')
@click.option('--app-name', '-n',
              help='Application name (defaults to project directory name)')
def init(project_path, type, app_name):
    """🚀 Initialize a new autoklug project"""
    try:
        project_name = app_name or Path(project_path).name
        initializer = ProjectInitializer(project_path)
        
        success = initializer.initialize_project(type, project_name)
        
        if success:
            click.echo(click.style("✅ Project initialized successfully!", fg='green'))
        else:
            click.echo(click.style("❌ Project initialization failed!", fg='red'))
            sys.exit(1)
            
    except Exception as e:
        click.echo(click.style(f"❌ Error: {e}", fg='red'))
        sys.exit(1)


@click.command()
@click.option('--type', '-t',
              type=click.Choice(['basic', 'production', 'public']),
              default='basic',
              help='Template type to show')
def template(type):
    """📋 Show configuration template"""
    templates = ConfigurationTemplates()
    
    if type == 'production':
        content = templates.get_production_tool_template()
    elif type == 'public':
        content = templates.get_public_api_tool_template()
    else:
        content = templates.get_basic_tool_template()
    
    click.echo(content)
