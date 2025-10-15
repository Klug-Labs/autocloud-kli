"""
Blazing Fast API Gateway Builder with Public API Detection
"""
import asyncio
import json
import re
from collections import defaultdict
from itertools import groupby
from typing import Dict, List, Optional, Tuple

from .utils import (
    ConfigManager, log, retry_with_backoff, stopwatch
)


class AsyncApiBuilder:
    """Optimized API Gateway builder with public API detection and rate limiting"""
    
    def __init__(self, config: ConfigManager, infra: str, branch: str):
        self.config = config
        self.infra = infra
        self.branch = branch
        self.apigateway_client = config.apigateway_client
        self.lambda_client = config.lambda_client
        
        # Load router data
        self.router = self._load_router()
        
        # API naming
        if config.is_public_build:
            self.api_name = f"api-public-{infra}-{config.app_name}"
        else:
            self.api_name = f"api-{infra}-{config.app_name}"
        
        log(f"🔍 API Builder initialized for: {self.api_name}", 'blue')
        log(f"📊 Found {len(self.router)} endpoints", 'blue')
    
    def _load_router(self) -> List[Dict]:
        """Load router data from endpoints"""
        try:
            from setup.endpoints import read_router
            return sorted(read_router(self.config.tool_config, api_path=self.config.api_path),
                         key=lambda x: x['urlRule'])
        except ImportError:
            # Fallback if endpoints module not available
            log("⚠️ Could not import endpoints module, using basic router", 'yellow')
            return self._basic_router()
    
    def _basic_router(self) -> List[Dict]:
        """Basic router implementation as fallback"""
        router = []
        api_path = Path(self.config.api_path)
        
        for py_file in api_path.rglob('*.py'):
            if py_file.name == '__init__.py':
                continue
            
            relative_path = py_file.relative_to(api_path)
            path_parts = relative_path.parts[:-1]  # Remove filename
            
            if not path_parts:  # Skip root level files
                continue
            
            root_path = path_parts[0]
            method = py_file.stem.upper()
            
            # Build URL rule
            url_parts = []
            for part in path_parts:
                if part.startswith('__') and part.endswith('__'):
                    param_name = part[2:-2]
                    url_parts.append(f'<{param_name}>')
                else:
                    url_parts.append(part)
            
            url_rule = '/' + '/'.join(url_parts)
            
            router.append({
                'method': method,
                'rootPath': root_path,
                'urlRule': url_rule,
                'filePath': str(relative_path)
            })
        
        return sorted(router, key=lambda x: x['urlRule'])
    
    async def _get_existing_apis(self) -> List[Dict]:
        """Get all existing APIs with parallel pagination"""
        log("🔍 Retrieving existing APIs...", 'blue')
        
        def get_apis():
            paginator = self.apigateway_client.get_paginator('get_apis')
            apis = []
            for page in paginator.paginate():
                apis.extend(page['Items'])
            return apis
        
        apis = await asyncio.get_event_loop().run_in_executor(None, get_apis)
        log(f"Found {len(apis)} existing APIs", 'green')
        return apis
    
    def _find_paths(self) -> Dict[str, Dict]:
        """Build OpenAPI paths from router"""
        paths = defaultdict(dict)
        
        for url_rule, eps in groupby(self.router, lambda x: x['urlRule']):
            eps = list(eps)
            url_rule = url_rule.replace('<', '{').replace('>', '}')
            
            for ep in eps:
                function_name = self.config.get_lambda_name(ep.get('rootPath'))
                paths[url_rule][ep.get('method').lower()] = self._get_path(function_name, ep)
            
            # Add OPTIONS for CORS
            paths[url_rule]['options'] = self._get_options(ep)
        
        return dict(paths)
    
    def _read_parameters(self, matches: List[str]) -> List[Dict]:
        """Convert URL parameters to OpenAPI parameters"""
        return [
            {
                "name": m,
                "in": "path",
                "required": True,
                "schema": {"type": "string"}
            } for m in matches
        ]
    
    def _get_path(self, function_name: str, endpoint: Dict) -> Dict:
        """Build OpenAPI path definition"""
        d = {
            'responses': {
                "200": {
                    "description": "200 response",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Empty"}
                        }
                    }
                }
            },
            'x-amazon-apigateway-integration': {
                "httpMethod": "POST",
                "uri": f"arn:aws:apigateway:{self.config.tool_config.get('AWS_REGION')}:lambda:path/2015-03-31/functions/arn:aws:lambda:{self.config.tool_config.get('AWS_REGION')}:{self.config.tool_config.get('AWS_ACCOUNT_ID')}:function:{function_name}/invocations",
                "payloadFormatVersion": "1.0",
                "type": "aws_proxy"
            }
        }
        
        # Add security for non-public APIs
        if not self.config.is_public_build:
            d['security'] = [{"authorizer": []}]
        
        # Add parameters if needed
        if re.findall(r'<(.*?)>', endpoint.get('urlRule')):
            d['parameters'] = self._read_parameters(re.findall(r'<(.*?)>', endpoint.get('urlRule')))
        
        return d
    
    def _get_options(self, endpoint: Dict) -> Dict:
        """Build OPTIONS method for CORS"""
        d = {
            "responses": {
                "200": {
                    "description": "200 response",
                    "headers": {
                        "Access-Control-Allow-Origin": {"schema": {"type": "string"}},
                        "Access-Control-Allow-Methods": {"schema": {"type": "string"}},
                        "Access-Control-Allow-Headers": {"schema": {"type": "string"}}
                    },
                }
            }
        }
        
        # Add parameters if needed
        if re.findall(r'<(.*?)>', endpoint.get('urlRule')):
            d['parameters'] = self._read_parameters(re.findall(r'<(.*?)>', endpoint.get('urlRule')))
        
        return d
    
    def _build_openapi_spec(self, paths: Dict[str, Dict]) -> Dict:
        """Build complete OpenAPI specification"""
        body = {
            "openapi": "3.0.1",
            "info": {
                "title": self.api_name,
                "description": f"{'Public ' if self.config.is_public_build else ''}API for {self.config.app_name} (infra: {self.infra})",
                "version": "1"
            },
            "paths": paths,
            "components": {
                "schemas": {
                    "Empty": {
                        "title": "Empty Schema",
                        "type": "object"
                    }
                }
            },
            "x-amazon-apigateway-gateway-responses": {
                "DEFAULT_5XX": {
                    "responseParameters": {
                        "gatewayresponse.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
                        "gatewayresponse.header.Access-Control-Allow-Origin": "'*'",
                        "gatewayresponse.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
                    }
                },
                "DEFAULT_4XX": {
                    "responseParameters": {
                        "gatewayresponse.header.Access-Control-Allow-Methods": "'GET,POST,PUT,DELETE,OPTIONS'",
                        "gatewayresponse.header.Access-Control-Allow-Origin": "'*'",
                        "gatewayresponse.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
                    }
                }
            },
            "x-amazon-apigateway-cors": {
                "allowOrigins": ["*"],
                "allowMethods": ["*"],
                "allowHeaders": ["Authorization", "Content-Type", "X-Amz-Date", "X-Api-Key", "X-Amz-Security-Token"]
            }
        }
        
        # Add security schemes for non-public APIs
        if not self.config.is_public_build:
            body["components"]["securitySchemes"] = {
                "authorizer": {
                    "type": "apiKey",
                    "name": "Authorization",
                    "in": "header",
                    "x-amazon-apigateway-authorizer": {
                        "identitySource": "$request.header.Authorization",
                        "authorizerUri": f"arn:aws:apigateway:{self.config.tool_config.get('AWS_REGION')}:lambda:path/2015-03-31/functions/arn:aws:lambda:{self.config.tool_config.get('AWS_REGION')}:{self.config.tool_config.get('AWS_ACCOUNT_ID')}:function:{self.config.tool_config.get('AUTHORIZER_FUNCTION_NAME')}/invocations",
                        "authorizerPayloadFormatVersion": "2.0",
                        "authorizerResultTtlInSeconds": 0,
                        "type": "request",
                        "enableSimpleResponses": True
                    }
                }
            }
        
        # Add rate limiting for public APIs
        if self.config.is_public_build:
            body["x-amazon-apigateway-request-validators"] = {
                "all": {
                    "validateRequestBody": True,
                    "validateRequestParameters": True
                }
            }
            
            # Add throttling configuration
            body["x-amazon-apigateway-throttle"] = {
                "burstLimit": 100,
                "rateLimit": 50
            }
        
        return body
    
    async def _create_api(self, body: Dict) -> Tuple[str, str]:
        """Create new API Gateway"""
        log(f"📦 Creating new API: {self.api_name}", 'yellow')
        
        def create_api():
            return retry_with_backoff(lambda: self.apigateway_client.import_api(
                Body=json.dumps(body),
                FailOnWarnings=True
            ))
        
        response = await asyncio.get_event_loop().run_in_executor(None, create_api)
        api_id = response['ApiId']
        endpoint = response['ApiEndpoint']
        
        log(f"✅ Created API: {self.api_name} (ID: {api_id})", 'green')
        return api_id, endpoint
    
    async def _create_stage_and_deployment(self, api_id: str):
        """Create stage and deployment"""
        log("🎭 Creating stage and deployment...", 'blue')
        
        # Create stage
        def create_stage():
            return retry_with_backoff(lambda: self.apigateway_client.create_stage(
                ApiId=api_id,
                AutoDeploy=True,
                StageName='live'
            ))
        
        await asyncio.get_event_loop().run_in_executor(None, create_stage)
        
        # Create deployment
        def create_deployment():
            return retry_with_backoff(lambda: self.apigateway_client.create_deployment(
                ApiId=api_id,
                StageName='live'
            ))
        
        await asyncio.get_event_loop().run_in_executor(None, create_deployment)
        log("✅ Stage and deployment created", 'green')
    
    async def _update_api(self, api_id: str, body: Dict, existing_paths: Dict[str, List[str]]):
        """Update existing API if needed"""
        log(f"🔄 Checking if API needs update: {self.api_name}", 'blue')
        
        # Build new paths
        new_paths = self._find_paths()
        new_paths_simple = {k: list([verb for verb in v.keys() if verb not in ['options', 'parameters']]) 
                          for k, v in new_paths.items()}
        
        # Compare paths
        if json.dumps(new_paths_simple, sort_keys=True) != json.dumps(existing_paths, sort_keys=True):
            log("🔄 API paths changed, updating...", 'yellow')
            
            def update_api():
                return retry_with_backoff(lambda: self.apigateway_client.reimport_api(
                    ApiId=api_id,
                    Body=json.dumps(body),
                    FailOnWarnings=True
                ))
            
            await asyncio.get_event_loop().run_in_executor(None, update_api)
            
            # Ensure stage and deployment exist
            await self._ensure_stage_and_deployment(api_id)
            log("✅ API updated successfully", 'green')
        else:
            log("✅ API is up to date", 'green')
    
    async def _ensure_stage_and_deployment(self, api_id: str):
        """Ensure stage and deployment exist"""
        try:
            # Check if stage exists
            def get_stages():
                return retry_with_backoff(lambda: self.apigateway_client.get_stages(ApiId=api_id))
            
            stages_response = await asyncio.get_event_loop().run_in_executor(None, get_stages)
            stages = stages_response.get('Items', [])
            
            live_stage = next((stage for stage in stages if stage.get('StageName') == 'live'), None)
            
            if not live_stage:
                await self._create_stage_and_deployment(api_id)
            else:
                # Check if deployment exists
                def get_deployments():
                    return retry_with_backoff(lambda: self.apigateway_client.get_deployments(ApiId=api_id))
                
                deployments_response = await asyncio.get_event_loop().run_in_executor(None, get_deployments)
                deployments = deployments_response.get('Items', [])
                
                live_deployments = [d for d in deployments if d.get('StageName') == 'live']
                
                if not live_deployments:
                    def create_deployment():
                        return retry_with_backoff(lambda: self.apigateway_client.create_deployment(
                            ApiId=api_id,
                            StageName='live'
                        ))
                    
                    await asyncio.get_event_loop().run_in_executor(None, create_deployment)
                    log("✅ Created missing deployment", 'green')
        
        except Exception as e:
            log(f"⚠️ Error ensuring stage/deployment: {e}", 'yellow')
    
    async def _attach_permissions(self, api_id: str):
        """Attach Lambda permissions for API Gateway"""
        log("🔐 Attaching Lambda permissions...", 'blue')
        
        # Get function names from router
        function_names = list(set([self.config.get_lambda_name(ep['rootPath']) for ep in self.router]))
        
        def add_permission(function_name: str):
            source_arn = f"arn:aws:execute-api:{self.config.tool_config.get('AWS_REGION')}:{self.config.tool_config.get('AWS_ACCOUNT_ID')}:{api_id}/*/*/*"
            
            try:
                return retry_with_backoff(lambda: self.lambda_client.add_permission(
                    FunctionName=function_name,
                    StatementId=f'invoke_{api_id}',
                    Action='lambda:InvokeFunction',
                    Principal='apigateway.amazonaws.com',
                    SourceArn=source_arn
                ))
            except self.lambda_client.exceptions.ResourceConflictException:
                pass  # Permission already exists
            except self.lambda_client.exceptions.NotFoundException:
                pass  # Function doesn't exist yet
        
        # Add permissions in parallel
        tasks = [asyncio.get_event_loop().run_in_executor(None, add_permission, fn) 
                for fn in function_names]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        log(f"✅ Permissions attached for {len(function_names)} functions", 'green')
    
    async def build(self) -> Tuple[str, str]:
        """Build API Gateway"""
        stopwatch("API building started")
        
        log("🚀 Starting API build...", 'blue')
        
        # Get existing APIs
        existing_apis = await self._get_existing_apis()
        
        # Find our API
        api_id = None
        endpoint = None
        
        for api in existing_apis:
            if api.get('Name') == self.api_name:
                api_id = api.get('ApiId')
                endpoint = api.get('ApiEndpoint')
                break
        
        # Build paths and OpenAPI spec
        paths = self._find_paths()
        body = self._build_openapi_spec(paths)
        
        if not api_id:
            # Create new API
            api_id, endpoint = await self._create_api(body)
            await self._create_stage_and_deployment(api_id)
        else:
            # Check if update needed
            try:
                def export_api():
                    return retry_with_backoff(lambda: self.apigateway_client.export_api(
                        ApiId=api_id,
                        IncludeExtensions=True,
                        OutputType='JSON',
                        Specification='OAS30',
                        StageName='live'
                    ))
                
                export_response = await asyncio.get_event_loop().run_in_executor(None, export_api)
                existing_spec = json.loads(export_response['body'].read().decode())
                existing_paths = {k: list([verb for verb in v.keys() if verb not in ['options', 'parameters']]) 
                                for k, v in existing_spec.get('paths', {}).items()}
                
                await self._update_api(api_id, body, existing_paths)
                
            except Exception as e:
                log(f"⚠️ Could not export existing API, creating new deployment: {e}", 'yellow')
                await self._ensure_stage_and_deployment(api_id)
        
        # Attach permissions
        await self._attach_permissions(api_id)
        
        log(f"🎯 API build completed: {self.api_name}", 'green')
        log(f"🌐 API Endpoint: {endpoint}/live", 'green')
        stopwatch("API building completed")
        
        return api_id, endpoint
