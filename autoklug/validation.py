"""
AWS Credentials & Permissions Validation Module

Validates AWS credentials and permissions before deployment to prevent mid-process failures.
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple
from botocore.exceptions import ClientError, NoCredentialsError
from .utils import ConfigManager, log_header, log_step, log_success, log_error, log_warning, log_info


class AWSCredentialsValidator:
    """Validate AWS credentials and permissions before deployment"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.session = config.session
        self.required_permissions = {
            'lambda': [
                'lambda:CreateFunction',
                'lambda:UpdateFunctionCode',
                'lambda:UpdateFunctionConfiguration',
                'lambda:PublishLayerVersion',
                'lambda:AddPermission',
                'lambda:GetFunction',
                'lambda:ListFunctions',
                'lambda:ListLayers',
                'lambda:GetLayerVersion',
                'lambda:DeleteFunction',
                'lambda:DeleteLayerVersion'
            ],
            's3': [
                's3:CreateBucket',
                's3:PutObject',
                's3:GetObject',
                's3:HeadBucket',
                's3:PutBucketVersioning',
                's3:PutBucketEncryption',
                's3:ListBucket',
                's3:DeleteObject'
            ],
            'apigateway': [
                'apigateway:POST',
                'apigateway:GET',
                'apigateway:PUT',
                'apigateway:DELETE',
                'apigateway:PATCH',
                'apigateway:CreateApi',
                'apigateway:CreateResource',
                'apigateway:CreateMethod',
                'apigateway:PutIntegration',
                'apigateway:CreateDeployment'
            ],
            'iam': [
                'iam:PassRole',
                'iam:GetRole',
                'iam:CreateRole',
                'iam:AttachRolePolicy',
                'iam:ListRoles',
                'iam:GetRolePolicy'
            ],
            'secretsmanager': [
                'secretsmanager:CreateSecret',
                'secretsmanager:GetSecretValue',
                'secretsmanager:UpdateSecret',
                'secretsmanager:DeleteSecret',
                'secretsmanager:ListSecrets',
                'secretsmanager:DescribeSecret'
            ]
        }
    
    async def validate_all(self) -> Tuple[bool, List[str]]:
        """Validate all AWS credentials and permissions"""
        log_header("AWS CREDENTIALS & PERMISSIONS VALIDATION")
        
        errors = []
        
        # Test AWS credentials
        log_step("1", "Testing AWS credentials")
        if not await self._test_credentials():
            errors.append("AWS credentials are invalid or expired")
            return False, errors
        
        # Test account ID
        log_step("2", "Validating AWS account ID")
        account_id = await self._validate_account_id()
        if not account_id:
            errors.append("Unable to determine AWS account ID")
            return False, errors
        
        # Test region
        log_step("3", "Validating AWS region")
        if not await self._validate_region():
            errors.append(f"AWS region '{self.config.tool_config.get('AWS_REGION')}' is not accessible")
            return False, errors
        
        # Test permissions
        log_step("4", "Testing required permissions")
        permission_errors = await self._test_permissions()
        if permission_errors:
            errors.extend(permission_errors)
            return False, errors
        
        log_success("All AWS credentials and permissions validated successfully")
        log_info(f"Account ID: {account_id}")
        log_info(f"Region: {self.config.tool_config.get('AWS_REGION', 'us-east-1')}")
        return True, []
    
    async def _test_credentials(self) -> bool:
        """Test AWS credentials by calling STS GetCallerIdentity"""
        try:
            sts_client = self.session.client('sts')
            response = sts_client.get_caller_identity()
            
            if response.get('Account'):
                log_success("AWS credentials are valid")
                return True
            else:
                log_error("AWS credentials returned invalid response")
                return False
                
        except NoCredentialsError:
            log_error("No AWS credentials found")
            return False
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidUserID.NotFound':
                log_error("AWS credentials are invalid")
            elif error_code == 'TokenRefreshRequired':
                log_error("AWS credentials have expired")
            else:
                log_error(f"AWS credentials error: {error_code}")
            return False
        except Exception as e:
            log_error(f"Unexpected error testing credentials: {e}")
            return False
    
    async def _validate_account_id(self) -> Optional[str]:
        """Validate and return AWS account ID"""
        try:
            sts_client = self.session.client('sts')
            response = sts_client.get_caller_identity()
            account_id = response.get('Account')
            
            if account_id:
                # Check if account ID matches configuration
                configured_account = self.config.tool_config.get('AWS_ACCOUNT_ID')
                if configured_account and configured_account != account_id:
                    log_warning(f"Account ID mismatch: configured '{configured_account}', actual '{account_id}'")
                    log_warning("Using actual account ID from credentials")
                
                log_success(f"Account ID validated: {account_id}")
                return account_id
            else:
                log_error("Unable to determine AWS account ID")
                return None
                
        except Exception as e:
            log_error(f"Error validating account ID: {e}")
            return None
    
    async def _validate_region(self) -> bool:
        """Validate AWS region accessibility"""
        try:
            region = self.config.tool_config.get('AWS_REGION', 'us-east-1')
            
            # Test region by trying to list Lambda functions
            lambda_client = self.session.client('lambda', region_name=region)
            lambda_client.list_functions(MaxItems=1)
            
            log_success(f"Region '{region}' is accessible")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'InvalidUserID.NotFound':
                log_error(f"Region '{region}' is not accessible")
            else:
                log_error(f"Region '{region}' error: {error_code}")
            return False
        except Exception as e:
            log_error(f"Error validating region: {e}")
            return False
    
    async def _test_permissions(self) -> List[str]:
        """Test all required permissions"""
        errors = []
        
        for service, permissions in self.required_permissions.items():
            log_info(f"Testing {service} permissions...")
            
            service_errors = await self._test_service_permissions(service, permissions)
            if service_errors:
                errors.extend(service_errors)
            else:
                log_success(f"{service} permissions validated")
        
        return errors
    
    async def _test_service_permissions(self, service: str, permissions: List[str]) -> List[str]:
        """Test permissions for a specific service"""
        errors = []
        
        try:
            if service == 'lambda':
                errors.extend(await self._test_lambda_permissions())
            elif service == 's3':
                errors.extend(await self._test_s3_permissions())
            elif service == 'apigateway':
                errors.extend(await self._test_apigateway_permissions())
            elif service == 'iam':
                errors.extend(await self._test_iam_permissions())
            elif service == 'secretsmanager':
                errors.extend(await self._test_secretsmanager_permissions())
                
        except Exception as e:
            errors.append(f"Error testing {service} permissions: {e}")
        
        return errors
    
    async def _test_lambda_permissions(self) -> List[str]:
        """Test Lambda permissions"""
        errors = []
        
        try:
            lambda_client = self.session.client('lambda')
            
            # Test list functions
            lambda_client.list_functions(MaxItems=1)
            
            # Test list layers
            lambda_client.list_layers(MaxItems=1)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                errors.append("Missing Lambda permissions: lambda:ListFunctions, lambda:ListLayers")
            else:
                errors.append(f"Lambda permission error: {error_code}")
        except Exception as e:
            errors.append(f"Lambda permission test failed: {e}")
        
        return errors
    
    async def _test_s3_permissions(self) -> List[str]:
        """Test S3 permissions"""
        errors = []
        
        try:
            s3_client = self.session.client('s3')
            
            # Test list buckets
            s3_client.list_buckets()
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                errors.append("Missing S3 permissions: s3:ListBucket")
            else:
                errors.append(f"S3 permission error: {error_code}")
        except Exception as e:
            errors.append(f"S3 permission test failed: {e}")
        
        return errors
    
    async def _test_apigateway_permissions(self) -> List[str]:
        """Test API Gateway permissions"""
        errors = []
        
        try:
            apigateway_client = self.session.client('apigateway')
            
            # Test list APIs
            apigateway_client.get_apis(limit=1)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                errors.append("Missing API Gateway permissions: apigateway:GET")
            else:
                errors.append(f"API Gateway permission error: {error_code}")
        except Exception as e:
            errors.append(f"API Gateway permission test failed: {e}")
        
        return errors
    
    async def _test_iam_permissions(self) -> List[str]:
        """Test IAM permissions"""
        errors = []
        
        try:
            iam_client = self.session.client('iam')
            
            # Test list roles
            iam_client.list_roles(MaxItems=1)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                errors.append("Missing IAM permissions: iam:ListRoles")
            else:
                errors.append(f"IAM permission error: {error_code}")
        except Exception as e:
            errors.append(f"IAM permission test failed: {e}")
        
        return errors
    
    async def _test_secretsmanager_permissions(self) -> List[str]:
        """Test Secrets Manager permissions"""
        errors = []
        
        try:
            secrets_client = self.session.client('secretsmanager')
            
            # Test list secrets
            secrets_client.list_secrets(MaxResults=1)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                errors.append("Missing Secrets Manager permissions: secretsmanager:ListSecrets")
            else:
                errors.append(f"Secrets Manager permission error: {error_code}")
        except Exception as e:
            errors.append(f"Secrets Manager permission test failed: {e}")
        
        return errors


class DeploymentValidator:
    """Validate deployment configuration and requirements"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
    
    async def validate_deployment_config(self) -> Tuple[bool, List[str]]:
        """Validate deployment configuration"""
        log_header("DEPLOYMENT CONFIGURATION VALIDATION")
        
        errors = []
        
        # Validate required configuration
        log_step("1", "Validating required configuration")
        config_errors = self._validate_required_config()
        if config_errors:
            errors.extend(config_errors)
        
        # Validate file paths
        log_step("2", "Validating file paths")
        path_errors = await self._validate_file_paths()
        if path_errors:
            errors.extend(path_errors)
        
        # Validate Lambda configuration
        log_step("3", "Validating Lambda configuration")
        lambda_errors = self._validate_lambda_config()
        if lambda_errors:
            errors.extend(lambda_errors)
        
        if errors:
            log_error("Deployment configuration validation failed")
            for error in errors:
                log_error(f"  • {error}")
            return False, errors
        
        log_success("Deployment configuration validated successfully")
        return True, []
    
    def _validate_required_config(self) -> List[str]:
        """Validate required configuration parameters"""
        errors = []
        
        required_params = [
            'APP_NAME',
            'AWS_REGION',
            'LAMBDA_RUNTIME',
            'LAMBDA_ROLE'
        ]
        
        for param in required_params:
            if not self.config.tool_config.get(param):
                errors.append(f"Missing required parameter: {param}")
        
        return errors
    
    async def _validate_file_paths(self) -> List[str]:
        """Validate that required file paths exist"""
        errors = []
        
        # Check API path
        api_path = self.config.tool_config.get('API_PATH', './api')
        if not self.config.api_path.exists():
            errors.append(f"API path does not exist: {api_path}")
        
        # Check layer path
        layer_path = self.config.tool_config.get('LAYER_PATH', './layers')
        if not self.config.layer_path.exists():
            errors.append(f"Layer path does not exist: {layer_path}")
        
        return errors
    
    def _validate_lambda_config(self) -> List[str]:
        """Validate Lambda configuration parameters"""
        errors = []
        
        # Validate runtime
        runtime = self.config.tool_config.get('LAMBDA_RUNTIME')
        valid_runtimes = [
            'python3.8', 'python3.9', 'python3.10', 'python3.11', 'python3.12',
            'nodejs18.x', 'nodejs20.x', 'nodejs22.x',
            'java8', 'java11', 'java17', 'java21'
        ]
        
        if runtime and runtime not in valid_runtimes:
            errors.append(f"Invalid Lambda runtime: {runtime}")
        
        # Validate timeout
        timeout = self.config.tool_config.get('LAMBDA_TIMEOUT')
        if timeout:
            try:
                timeout_int = int(timeout)
                if timeout_int < 1 or timeout_int > 900:
                    errors.append(f"Lambda timeout must be between 1 and 900 seconds: {timeout}")
            except ValueError:
                errors.append(f"Invalid Lambda timeout value: {timeout}")
        
        # Validate memory size
        memory = self.config.tool_config.get('LAMBDA_MEMORY_SIZE')
        if memory:
            try:
                memory_int = int(memory)
                if memory_int < 128 or memory_int > 10240:
                    errors.append(f"Lambda memory size must be between 128 and 10240 MB: {memory}")
            except ValueError:
                errors.append(f"Invalid Lambda memory size value: {memory}")
        
        return errors
