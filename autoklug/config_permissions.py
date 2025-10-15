"""
Configuration and Permissions Manager
"""
import asyncio
import json
from typing import Dict, List, Optional, Tuple

from .utils import (
    ConfigManager, log, retry_with_backoff, stopwatch
)


class ConfigPermissionsManager:
    """Manages configuration updates and permissions for the build system"""
    
    def __init__(self, config: ConfigManager, infra: str, branch: str):
        self.config = config
        self.infra = infra
        self.branch = branch
        self.lambda_client = config.lambda_client
        self.apigateway_client = config.apigateway_client
    
    async def update_function_configurations(self, function_results: Dict[str, bool]) -> Dict[str, bool]:
        """Update configurations for all functions that were successfully built"""
        log("⚙️ Updating function configurations...", 'blue')
        
        successful_functions = [name for name, success in function_results.items() if success]
        
        if not successful_functions:
            log("⚠️ No successful functions to configure", 'yellow')
            return {}
        
        # Update configurations in parallel
        config_results = {}
        
        def update_function_config(function_name: str) -> bool:
            try:
                expected_name = self.config.get_lambda_name(function_name)
                
                return retry_with_backoff(lambda: self.lambda_client.update_function_configuration(
                    FunctionName=expected_name,
                    Role=self.config.tool_config.get('LAMBDA_ROLE'),
                    Timeout=30,
                    MemorySize=2048,
                    Handler='lambda_function.lambda_handler',
                    Environment={'Variables': self.config.env_config},
                    Runtime=self.config.tool_config.get('LAMBDA_RUNTIME', 'python3.11'),
                    Layers=self.config.layer_arns if hasattr(self.config, 'layer_arns') else []
                ))
            except Exception as e:
                log(f"❌ Failed to update config for {function_name}: {e}", 'red')
                return False
        
        # Process configurations in parallel
        tasks = [asyncio.get_event_loop().run_in_executor(None, update_function_config, fn) 
                for fn in successful_functions]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, function_name in enumerate(successful_functions):
            config_results[function_name] = not isinstance(results[i], Exception)
        
        successful_configs = sum(1 for success in config_results.values() if success)
        log(f"✅ Updated configurations for {successful_configs}/{len(successful_functions)} functions", 'green')
        
        return config_results
    
    async def setup_api_permissions(self, api_id: str, endpoint: str) -> bool:
        """Setup API Gateway permissions for Lambda functions"""
        log("🔐 Setting up API permissions...", 'blue')
        
        try:
            # Get function names from router
            function_names = []
            for ep in self.config.router if hasattr(self.config, 'router') else []:
                function_name = self.config.get_lambda_name(ep['rootPath'])
                if function_name not in function_names:
                    function_names.append(function_name)
            
            if not function_names:
                log("⚠️ No functions found for permission setup", 'yellow')
                return True
            
            def add_permission(function_name: str) -> bool:
                try:
                    source_arn = f"arn:aws:execute-api:{self.config.tool_config.get('AWS_REGION')}:{self.config.tool_config.get('AWS_ACCOUNT_ID')}:{api_id}/*/*/*"
                    
                    retry_with_backoff(lambda: self.lambda_client.add_permission(
                        FunctionName=function_name,
                        StatementId=f'invoke_{api_id}',
                        Action='lambda:InvokeFunction',
                        Principal='apigateway.amazonaws.com',
                        SourceArn=source_arn
                    ))
                    return True
                except self.lambda_client.exceptions.ResourceConflictException:
                    # Permission already exists
                    return True
                except self.lambda_client.exceptions.NotFoundException:
                    log(f"⚠️ Function {function_name} not found for permission", 'yellow')
                    return False
                except Exception as e:
                    log(f"❌ Error adding permission for {function_name}: {e}", 'red')
                    return False
            
            # Add permissions in parallel
            tasks = [asyncio.get_event_loop().run_in_executor(None, add_permission, fn) 
                    for fn in function_names]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful_permissions = sum(1 for result in results if result is True)
            log(f"✅ Added permissions for {successful_permissions}/{len(function_names)} functions", 'green')
            
            return successful_permissions > 0
            
        except Exception as e:
            log(f"❌ Error setting up API permissions: {e}", 'red')
            return False
    
    async def setup_cors_configuration(self, api_id: str) -> bool:
        """Setup CORS configuration for the API"""
        log("🌐 Setting up CORS configuration...", 'blue')
        
        try:
            # CORS is handled in the OpenAPI spec, but we can add additional configuration here if needed
            log("✅ CORS configuration handled in OpenAPI spec", 'green')
            return True
            
        except Exception as e:
            log(f"❌ Error setting up CORS: {e}", 'red')
            return False
    
    async def setup_rate_limiting(self, api_id: str) -> bool:
        """Setup rate limiting for public APIs"""
        if not self.config.is_public_build:
            log("ℹ️ Skipping rate limiting for non-public API", 'blue')
            return True
        
        log("🚦 Setting up rate limiting for public API...", 'blue')
        
        try:
            # Rate limiting is configured in the OpenAPI spec
            # Additional throttling can be configured here if needed
            
            def create_usage_plan():
                return retry_with_backoff(lambda: self.apigateway_client.create_usage_plan(
                    Name=f"{self.api_name}-usage-plan",
                    Description=f"Usage plan for {self.api_name}",
                    Throttle={
                        'burstLimit': 100,
                        'rateLimit': 50
                    },
                    Quota={
                        'limit': 10000,
                        'period': 'DAY'
                    }
                ))
            
            usage_plan = await asyncio.get_event_loop().run_in_executor(None, create_usage_plan)
            log(f"✅ Created usage plan: {usage_plan['Id']}", 'green')
            
            return True
            
        except Exception as e:
            log(f"⚠️ Error setting up rate limiting: {e}", 'yellow')
            return True  # Non-critical error
    
    async def validate_deployment(self, api_id: str, endpoint: str) -> bool:
        """Validate the deployment by testing endpoints"""
        log("🔍 Validating deployment...", 'blue')
        
        try:
            import requests
            
            # Test health endpoint if it exists
            health_url = f"{endpoint}/live/health"
            
            def test_health():
                try:
                    response = requests.get(health_url, timeout=10)
                    return response.status_code == 200
                except Exception:
                    return False
            
            health_ok = await asyncio.get_event_loop().run_in_executor(None, test_health)
            
            if health_ok:
                log("✅ Health endpoint responding", 'green')
            else:
                log("⚠️ Health endpoint not responding", 'yellow')
            
            return True
            
        except Exception as e:
            log(f"⚠️ Error validating deployment: {e}", 'yellow')
            return True  # Non-critical error
    
    async def cleanup_old_versions(self, function_names: List[str]) -> bool:
        """Clean up old function versions to save space"""
        log("🧹 Cleaning up old function versions...", 'blue')
        
        try:
            def cleanup_function(function_name: str) -> bool:
                try:
                    expected_name = self.config.get_lambda_name(function_name)
                    
                    # List all versions
                    response = retry_with_backoff(lambda: self.lambda_client.list_versions_by_function(
                        FunctionName=expected_name
                    ))
                    
                    versions = response.get('Versions', [])
                    
                    # Keep only the latest 3 versions
                    if len(versions) > 3:
                        versions_to_delete = sorted(versions, key=lambda x: x['Version'])[:-3]
                        
                        for version in versions_to_delete:
                            if version['Version'] != '$LATEST':
                                try:
                                    retry_with_backoff(lambda: self.lambda_client.delete_function(
                                        FunctionName=f"{expected_name}:{version['Version']}"
                                    ))
                                except Exception:
                                    pass  # Ignore deletion errors
                    
                    return True
                except Exception:
                    return False
            
            # Cleanup in parallel
            tasks = [asyncio.get_event_loop().run_in_executor(None, cleanup_function, fn) 
                    for fn in function_names]
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            log("✅ Cleanup completed", 'green')
            return True
            
        except Exception as e:
            log(f"⚠️ Error during cleanup: {e}", 'yellow')
            return True  # Non-critical error
    
    async def run_post_build_tasks(self, api_id: str, endpoint: str, 
                                 function_results: Dict[str, bool]) -> Dict[str, bool]:
        """Run all post-build configuration and permission tasks"""
        stopwatch("Post-build tasks started")
        
        log("🚀 Running post-build tasks...", 'blue')
        
        results = {}
        
        # Update function configurations
        config_results = await self.update_function_configurations(function_results)
        results['config_updates'] = config_results
        
        # Setup API permissions
        permissions_ok = await self.setup_api_permissions(api_id, endpoint)
        results['permissions'] = permissions_ok
        
        # Setup CORS
        cors_ok = await self.setup_cors_configuration(api_id)
        results['cors'] = cors_ok
        
        # Setup rate limiting for public APIs
        rate_limiting_ok = await self.setup_rate_limiting(api_id)
        results['rate_limiting'] = rate_limiting_ok
        
        # Validate deployment
        validation_ok = await self.validate_deployment(api_id, endpoint)
        results['validation'] = validation_ok
        
        # Cleanup old versions
        successful_functions = [name for name, success in function_results.items() if success]
        cleanup_ok = await self.cleanup_old_versions(successful_functions)
        results['cleanup'] = cleanup_ok
        
        # Summary
        successful_tasks = sum(1 for success in results.values() if success is True)
        total_tasks = len(results)
        
        log(f"🎯 Post-build tasks completed: {successful_tasks}/{total_tasks} successful", 'green')
        stopwatch("Post-build tasks completed")
        
        return results
