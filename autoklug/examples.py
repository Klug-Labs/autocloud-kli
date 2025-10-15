"""
Example configuration files and usage documentation
"""

# Example .tool file (.tool.dev)
"""
# AWS Configuration
AWS_PROFILE_BUILD=default
AWS_REGION=eu-west-3
AWS_ACCOUNT_ID=123456789012

# Application Configuration
APP_NAME=msg-guest
PUBLIC_APP_NAME=msg-guest-public
INFRA=dev

# Lambda Configuration
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role

# Layer Configuration
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
LAYER_ARCHITECTURE=x86_64

# API Configuration
API_PATH=./api
AUTHORIZER_FUNCTION_NAME=api-msg-guest-dev-authorizer

# S3 Configuration for requirements.txt checking (auto-generated from APP_NAME)
# Bucket name will be: <APP_NAME>-requirements-txt-bucket
# Example: my-app-requirements-txt-bucket
"""

# Example .env file (.env.dev)
"""
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/msg_guest_dev

# External Services
UPLOADS_CDN=https://cdn.example.com
API_BASE_URL=https://api.example.com

# Feature Flags
ENABLE_FEATURE_X=true
DEBUG_MODE=true

# Note: VITE_ variables are automatically filtered out
"""

# Example usage in Python
"""
from builds_v2 import run_build

# Simple build
success = run_build('.tool.dev', '.env.dev', 'dev')

# Build with force update
success = run_build('.tool.dev', '.env.dev', 'dev', force_update_layers=True)
"""

# Example CLI usage
"""
# Basic build
python -m builds_v2.main --tool .tool.dev --env .env.dev --infra dev

# Force update layers
python -m builds_v2.main --tool .tool.dev --env .env.dev --infra dev --force-update-layers

# Build only layers
python -m builds_v2.main --tool .tool.dev --layers-only

# Build only functions
python -m builds_v2.main --tool .tool.dev --functions-only

# Build only API
python -m builds_v2.main --tool .tool.dev --api-only
"""
