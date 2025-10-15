"""
Testing Framework Integration Module

Provides testing capabilities for Lambda functions and deployments.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import click
from .utils import ConfigManager, log_header, log_step, log_success, log_error, log_info, log_detail


class TestResult:
    """Represents the result of a test"""
    
    def __init__(self, name: str, success: bool, duration: float, 
                 error: Optional[str] = None, details: Optional[Dict] = None):
        self.name = name
        self.success = success
        self.duration = duration
        self.error = error
        self.details = details or {}
    
    def __str__(self):
        status = "✅ PASS" if self.success else "❌ FAIL"
        return f"{status} {self.name} ({self.duration:.2f}s)"


class TestSuite:
    """Manages a collection of tests"""
    
    def __init__(self, name: str):
        self.name = name
        self.tests: List[Callable] = []
        self.results: List[TestResult] = []
    
    def add_test(self, test_func: Callable):
        """Add a test function to the suite"""
        self.tests.append(test_func)
    
    async def run_all(self) -> List[TestResult]:
        """Run all tests in the suite"""
        log_header(f"RUNNING TEST SUITE: {self.name}")
        
        self.results = []
        
        for i, test_func in enumerate(self.tests, 1):
            log_step(str(i), f"Running test: {test_func.__name__}")
            
            start_time = time.time()
            try:
                # Run the test
                if asyncio.iscoroutinefunction(test_func):
                    result = await test_func()
                else:
                    result = test_func()
                
                duration = time.time() - start_time
                
                # Determine success
                if isinstance(result, bool):
                    success = result
                    error = None
                elif isinstance(result, dict):
                    success = result.get('success', True)
                    error = result.get('error')
                else:
                    success = True
                    error = None
                
                test_result = TestResult(
                    name=test_func.__name__,
                    success=success,
                    duration=duration,
                    error=error
                )
                
                self.results.append(test_result)
                
                if success:
                    log_success(f"Test passed: {test_func.__name__}")
                else:
                    log_error(f"Test failed: {test_func.__name__}")
                    if error:
                        log_error(f"Error: {error}")
                
            except Exception as e:
                duration = time.time() - start_time
                test_result = TestResult(
                    name=test_func.__name__,
                    success=False,
                    duration=duration,
                    error=str(e)
                )
                self.results.append(test_result)
                log_error(f"Test error: {test_func.__name__} - {e}")
        
        # Summary
        passed = sum(1 for r in self.results if r.success)
        total = len(self.results)
        log_info(f"Test suite completed: {passed}/{total} tests passed")
        
        return self.results


class LambdaFunctionTester:
    """Tests Lambda functions locally and remotely"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.lambda_client = config.session.client('lambda')
    
    async def test_function_locally(self, function_path: str, test_event: Dict) -> TestResult:
        """Test a Lambda function locally"""
        log_info(f"Testing function locally: {function_path}")
        
        try:
            # Import the function module
            import importlib.util
            spec = importlib.util.spec_from_file_location("lambda_function", function_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Create mock context
            class MockContext:
                def __init__(self):
                    self.function_name = "test-function"
                    self.function_version = "$LATEST"
                    self.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
                    self.memory_limit_in_mb = 128
                    self.remaining_time_in_millis = 30000
                    self.log_group_name = "/aws/lambda/test-function"
                    self.log_stream_name = "2023/01/01/[$LATEST]test"
                    self.aws_request_id = "test-request-id"
            
            context = MockContext()
            
            # Call the function
            start_time = time.time()
            result = module.lambda_handler(test_event, context)
            duration = time.time() - start_time
            
            # Validate result
            success = self._validate_lambda_response(result)
            
            return TestResult(
                name=f"local_test_{Path(function_path).stem}",
                success=success,
                duration=duration,
                details={'result': result}
            )
            
        except Exception as e:
            return TestResult(
                name=f"local_test_{Path(function_path).stem}",
                success=False,
                duration=0,
                error=str(e)
            )
    
    async def test_function_remotely(self, function_name: str, test_event: Dict) -> TestResult:
        """Test a Lambda function remotely"""
        log_info(f"Testing function remotely: {function_name}")
        
        try:
            start_time = time.time()
            
            # Invoke the function
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_event)
            )
            
            duration = time.time() - start_time
            
            # Parse response
            payload = json.loads(response['Payload'].read())
            
            # Check for errors
            if 'FunctionError' in response:
                error = payload.get('errorMessage', 'Unknown error')
                return TestResult(
                    name=f"remote_test_{function_name}",
                    success=False,
                    duration=duration,
                    error=error
                )
            
            # Validate response
            success = self._validate_lambda_response(payload)
            
            return TestResult(
                name=f"remote_test_{function_name}",
                success=success,
                duration=duration,
                details={'response': payload}
            )
            
        except Exception as e:
            return TestResult(
                name=f"remote_test_{function_name}",
                success=False,
                duration=0,
                error=str(e)
            )
    
    def _validate_lambda_response(self, response: Any) -> bool:
        """Validate Lambda function response"""
        if not isinstance(response, dict):
            return False
        
        # Check for required fields in API Gateway response
        if 'statusCode' in response:
            return response.get('statusCode', 0) >= 200 and response.get('statusCode', 0) < 300
        
        # For other responses, just check if it's not None
        return response is not None


class DeploymentTester:
    """Tests deployment configurations and resources"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.lambda_client = config.session.client('lambda')
        self.s3_client = config.session.client('s3')
        self.apigateway_client = config.session.client('apigateway')
    
    async def test_lambda_functions_exist(self) -> TestResult:
        """Test that Lambda functions exist"""
        log_info("Testing Lambda functions exist")
        
        try:
            # Get list of functions
            response = self.lambda_client.list_functions()
            functions = response.get('Functions', [])
            
            # Check if any functions exist
            success = len(functions) > 0
            
            return TestResult(
                name="lambda_functions_exist",
                success=success,
                duration=0,
                details={'function_count': len(functions)}
            )
            
        except Exception as e:
            return TestResult(
                name="lambda_functions_exist",
                success=False,
                duration=0,
                error=str(e)
            )
    
    async def test_lambda_layers_exist(self) -> TestResult:
        """Test that Lambda layers exist"""
        log_info("Testing Lambda layers exist")
        
        try:
            # Get list of layers
            response = self.lambda_client.list_layers()
            layers = response.get('Layers', [])
            
            # Check if any layers exist
            success = len(layers) > 0
            
            return TestResult(
                name="lambda_layers_exist",
                success=success,
                duration=0,
                details={'layer_count': len(layers)}
            )
            
        except Exception as e:
            return TestResult(
                name="lambda_layers_exist",
                success=False,
                duration=0,
                error=str(e)
            )
    
    async def test_api_gateway_exists(self) -> TestResult:
        """Test that API Gateway exists"""
        log_info("Testing API Gateway exists")
        
        try:
            # Get list of APIs
            response = self.apigateway_client.get_apis()
            apis = response.get('Items', [])
            
            # Check if any APIs exist
            success = len(apis) > 0
            
            return TestResult(
                name="api_gateway_exists",
                success=success,
                duration=0,
                details={'api_count': len(apis)}
            )
            
        except Exception as e:
            return TestResult(
                name="api_gateway_exists",
                success=False,
                duration=0,
                error=str(e)
            )
    
    async def test_s3_bucket_exists(self) -> TestResult:
        """Test that S3 bucket exists"""
        log_info("Testing S3 bucket exists")
        
        try:
            bucket_name = f"{self.config.app_name}-requirements-txt-bucket"
            
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=bucket_name)
            
            return TestResult(
                name="s3_bucket_exists",
                success=True,
                duration=0,
                details={'bucket_name': bucket_name}
            )
            
        except Exception as e:
            return TestResult(
                name="s3_bucket_exists",
                success=False,
                duration=0,
                error=str(e)
            )


class IntegrationTester:
    """Tests integration between components"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.lambda_client = config.session.client('lambda')
        self.apigateway_client = config.session.client('apigateway')
    
    async def test_api_lambda_integration(self) -> TestResult:
        """Test API Gateway to Lambda integration"""
        log_info("Testing API Gateway to Lambda integration")
        
        try:
            # Get APIs
            apis_response = self.apigateway_client.get_apis()
            apis = apis_response.get('Items', [])
            
            if not apis:
                return TestResult(
                    name="api_lambda_integration",
                    success=False,
                    duration=0,
                    error="No APIs found"
                )
            
            # Get first API
            api_id = apis[0]['Id']
            
            # Get resources
            resources_response = self.apigateway_client.get_resources(restApiId=api_id)
            resources = resources_response.get('Items', [])
            
            # Check if any resources have Lambda integration
            lambda_integrations = 0
            for resource in resources:
                for method in resource.get('resourceMethods', {}):
                    method_response = self.apigateway_client.get_method(
                        restApiId=api_id,
                        resourceId=resource['Id'],
                        httpMethod=method
                    )
                    
                    integration = method_response.get('methodIntegration', {})
                    if integration.get('type') == 'AWS_PROXY':
                        lambda_integrations += 1
            
            success = lambda_integrations > 0
            
            return TestResult(
                name="api_lambda_integration",
                success=success,
                duration=0,
                details={'lambda_integrations': lambda_integrations}
            )
            
        except Exception as e:
            return TestResult(
                name="api_lambda_integration",
                success=False,
                duration=0,
                error=str(e)
            )


# CLI Commands for testing
@click.command()
@click.option('--tool', '-t', 
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.option('--env', '-e', 
              help='Path to .env file for environment variables (auto-detected if not provided)')
@click.option('--local', is_flag=True,
              help='Run local tests only')
@click.option('--remote', is_flag=True,
              help='Run remote tests only')
@click.option('--integration', is_flag=True,
              help='Run integration tests')
def test(tool, env, local, remote, integration):
    """🧪 Run tests for Lambda functions and deployment"""
    try:
        from .utils import detect_project_context, find_best_config_files
        
        # Auto-detect configuration if not provided
        if not tool or not env:
            context = detect_project_context()
            detected_tool, detected_env = find_best_config_files(context)
            tool = tool or detected_tool
            env = env or detected_env
        
        config = ConfigManager(tool, env)
        
        # Create test suite
        suite = TestSuite("Autoklug Tests")
        
        # Add tests based on options
        if not local and not remote and not integration:
            # Run all tests by default
            local = remote = integration = True
        
        if local:
            # Add local tests
            tester = LambdaFunctionTester(config)
            suite.add_test(lambda: tester.test_function_locally(
                str(config.api_path / "main.py"),
                {"httpMethod": "GET", "path": "/", "body": "{}"}
            ))
        
        if remote:
            # Add remote tests
            deployment_tester = DeploymentTester(config)
            suite.add_test(lambda: deployment_tester.test_lambda_functions_exist())
            suite.add_test(lambda: deployment_tester.test_lambda_layers_exist())
            suite.add_test(lambda: deployment_tester.test_api_gateway_exists())
            suite.add_test(lambda: deployment_tester.test_s3_bucket_exists())
        
        if integration:
            # Add integration tests
            integration_tester = IntegrationTester(config)
            suite.add_test(lambda: integration_tester.test_api_lambda_integration())
        
        # Run tests
        results = asyncio.run(suite.run_all())
        
        # Summary
        passed = sum(1 for r in results if r.success)
        total = len(results)
        
        if passed == total:
            click.echo(click.style(f"✅ All tests passed! ({passed}/{total})", fg='green'))
        else:
            click.echo(click.style(f"❌ Some tests failed! ({passed}/{total})", fg='red'))
            sys.exit(1)
            
    except Exception as e:
        click.echo(click.style(f"❌ Test error: {e}", fg='red'))
        sys.exit(1)


@click.command()
@click.option('--tool', '-t', 
              help='Path to .tool configuration file (auto-detected if not provided)')
@click.option('--env', '-e', 
              help='Path to .env file for environment variables (auto-detected if not provided)')
@click.option('--function-name', '-f',
              help='Specific function name to test')
@click.option('--event-file', '-e',
              help='JSON file containing test event')
def test_function(tool, env, function_name, event_file):
    """🔬 Test a specific Lambda function"""
    try:
        from .utils import detect_project_context, find_best_config_files
        
        # Auto-detect configuration if not provided
        if not tool or not env:
            context = detect_project_context()
            detected_tool, detected_env = find_best_config_files(context)
            tool = tool or detected_tool
            env = env or detected_env
        
        config = ConfigManager(tool, env)
        
        # Load test event
        if event_file:
            with open(event_file, 'r') as f:
                test_event = json.load(f)
        else:
            test_event = {"httpMethod": "GET", "path": "/", "body": "{}"}
        
        # Test function
        tester = LambdaFunctionTester(config)
        
        if function_name:
            # Test remotely
            result = asyncio.run(tester.test_function_remotely(function_name, test_event))
        else:
            # Test locally
            result = asyncio.run(tester.test_function_locally(
                str(config.api_path / "main.py"),
                test_event
            ))
        
        # Display result
        click.echo(str(result))
        
        if not result.success:
            sys.exit(1)
            
    except Exception as e:
        click.echo(click.style(f"❌ Test error: {e}", fg='red'))
        sys.exit(1)
