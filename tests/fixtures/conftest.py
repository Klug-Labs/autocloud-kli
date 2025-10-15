"""
Test fixtures for autoklug tests
"""
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_project():
    """Create a temporary project structure for testing"""
    temp_dir = tempfile.mkdtemp()
    project_dir = Path(temp_dir) / "test_project"
    project_dir.mkdir()
    
    # Create basic project structure
    (project_dir / "api").mkdir()
    (project_dir / "layers").mkdir()
    (project_dir / "layers" / "shared").mkdir()
    (project_dir / "layers" / "thirdparty").mkdir()
    
    # Create sample API function
    api_dir = project_dir / "api" / "health"
    api_dir.mkdir()
    (api_dir / "get.py").write_text("""
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': '{"message": "healthy"}'
    }
""")
    
    # Create sample layer files
    (project_dir / "layers" / "shared" / "utils.py").write_text("""
def helper_function():
    return "helper"
""")
    
    (project_dir / "layers" / "thirdparty" / "requirements.txt").write_text("""
requests==2.31.0
boto3==1.34.0
""")
    
    # Create configuration files
    (project_dir / ".tool").write_text("""
AWS_PROFILE_BUILD=default
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
APP_NAME=test-app
INFRA=dev
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
API_PATH=./api
""")
    
    (project_dir / ".env").write_text("""
DATABASE_URL=postgresql://test:test@localhost:5432/test_db
DEBUG_MODE=true
""")
    
    yield project_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_public_project():
    """Create a temporary public API project structure for testing"""
    temp_dir = tempfile.mkdtemp()
    project_dir = Path(temp_dir) / "public_project"
    project_dir.mkdir()
    
    # Create public API structure
    (project_dir / "api_public").mkdir()
    (project_dir / "api_public" / "catalog").mkdir()
    (project_dir / "api_public" / "health").mkdir()
    
    # Create public API functions
    (project_dir / "api_public" / "catalog" / "get.py").write_text("""
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': '{"catalog": []}'
    }
""")
    
    (project_dir / "api_public" / "health" / "get.py").write_text("""
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': '{"status": "healthy"}'
    }
""")
    
    # Create layers
    (project_dir / "layers").mkdir()
    (project_dir / "layers" / "shared").mkdir()
    (project_dir / "layers" / "thirdparty").mkdir()
    
    (project_dir / "layers" / "shared" / "utils.py").write_text("""
def public_helper():
    return "public helper"
""")
    
    (project_dir / "layers" / "thirdparty" / "requirements.txt").write_text("""
requests==2.31.0
""")
    
    # Create public configuration
    (project_dir / ".tool.public").write_text("""
AWS_PROFILE_BUILD=default
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
PUBLIC_APP_NAME=public-app
INFRA=dev
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
API_PATH=./api_public
""")
    
    (project_dir / ".env").write_text("""
PUBLIC_API_KEY=test-key
DEBUG_MODE=true
""")
    
    yield project_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_multi_env_project():
    """Create a temporary multi-environment project structure"""
    temp_dir = tempfile.mkdtemp()
    project_dir = Path(temp_dir) / "multi_env_project"
    project_dir.mkdir()
    
    # Create project structure
    (project_dir / "api").mkdir()
    (project_dir / "layers").mkdir()
    (project_dir / "layers" / "shared").mkdir()
    
    # Create API function
    api_dir = project_dir / "api" / "users"
    api_dir.mkdir()
    (api_dir / "get.py").write_text("""
def lambda_handler(event, context):
    return {'statusCode': 200, 'body': '{"users": []}'}
""")
    
    # Create environment-specific configurations
    (project_dir / ".tool.dev").write_text("""
AWS_PROFILE_BUILD=dev-profile
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
APP_NAME=multi-app-dev
INFRA=dev
LAMBDA_RUNTIME=python3.11
""")
    
    (project_dir / ".tool.prod").write_text("""
AWS_PROFILE_BUILD=prod-profile
AWS_REGION=us-west-2
AWS_ACCOUNT_ID=123456789012
APP_NAME=multi-app-prod
INFRA=prod
LAMBDA_RUNTIME=python3.11
""")
    
    (project_dir / ".env.dev").write_text("""
DATABASE_URL=postgresql://dev:dev@localhost:5432/dev_db
DEBUG_MODE=true
""")
    
    (project_dir / ".env.prod").write_text("""
DATABASE_URL=postgresql://prod:prod@prod-host:5432/prod_db
DEBUG_MODE=false
""")
    
    yield project_dir
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_aws_session():
    """Mock AWS session for testing"""
    from unittest.mock import MagicMock
    
    session = MagicMock()
    session.client.return_value = MagicMock()
    
    return session


@pytest.fixture
def mock_lambda_client():
    """Mock Lambda client for testing"""
    from unittest.mock import MagicMock
    
    client = MagicMock()
    
    # Mock common Lambda operations
    client.list_functions.return_value = {
        'Functions': [
            {
                'FunctionName': 'test-function',
                'FunctionArn': 'arn:aws:lambda:us-east-1:123456789012:function:test-function',
                'Runtime': 'python3.11',
                'LastModified': '2024-01-01T00:00:00.000Z'
            }
        ]
    }
    
    client.get_function.return_value = {
        'Configuration': {
            'FunctionName': 'test-function',
            'CodeSha256': 'test-sha256',
            'Runtime': 'python3.11',
            'Environment': {'Variables': {'TEST_VAR': 'test_value'}},
            'Layers': [{'Arn': 'arn:aws:lambda:us-east-1:123456789012:layer:test-layer:1'}]
        }
    }
    
    client.publish_layer_version.return_value = {
        'LayerVersionArn': 'arn:aws:lambda:us-east-1:123456789012:layer:test-layer:1'
    }
    
    return client


@pytest.fixture
def mock_api_gateway_client():
    """Mock API Gateway client for testing"""
    from unittest.mock import MagicMock
    
    client = MagicMock()
    
    # Mock common API Gateway operations
    client.get_apis.return_value = {
        'Items': [
            {
                'ApiId': 'test-api-id',
                'Name': 'test-api',
                'ApiEndpoint': 'https://test-api-id.execute-api.us-east-1.amazonaws.com'
            }
        ]
    }
    
    client.import_api.return_value = {
        'ApiId': 'test-api-id',
        'ApiEndpoint': 'https://test-api-id.execute-api.us-east-1.amazonaws.com'
    }
    
    client.create_stage.return_value = {
        'StageName': 'live',
        'StageArn': 'arn:aws:apigateway:us-east-1:123456789012:api/test-api-id/stage/live'
    }
    
    client.create_deployment.return_value = {
        'DeploymentId': 'test-deployment-id',
        'DeploymentArn': 'arn:aws:apigateway:us-east-1:123456789012:api/test-api-id/deployment/test-deployment-id'
    }
    
    return client


@pytest.fixture
def sample_router_data():
    """Sample router data for testing"""
    return [
        {
            'method': 'GET',
            'urlRule': '/health',
            'urlRuleAG': '/health',
            'rootPath': 'health',
            'filePath': 'health/get.py'
        },
        {
            'method': 'POST',
            'urlRule': '/users',
            'urlRuleAG': '/users',
            'rootPath': 'users',
            'filePath': 'users/post.py'
        },
        {
            'method': 'GET',
            'urlRule': '/users/{id}',
            'urlRuleAG': '/users/{id}',
            'rootPath': 'users',
            'filePath': 'users/get.py'
        }
    ]


@pytest.fixture
def sample_layer_data():
    """Sample layer data for testing"""
    return {
        'shared': {
            'LayerName': 'layer-main-dev-main',
            'LayerVersionArn': 'arn:aws:lambda:us-east-1:123456789012:layer:layer-main-dev-main:1',
            'Version': 1
        },
        'thirdparty': {
            'LayerName': 'layer-thirdparty-dev-main',
            'LayerVersionArn': 'arn:aws:lambda:us-east-1:123456789012:layer:layer-thirdparty-dev-main:23',
            'Version': 23
        }
    }
