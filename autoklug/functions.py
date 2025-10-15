"""
Blazing Fast Lambda Function Builder with Parallel Updates
"""
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import groupby
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from .utils import (
    ConfigManager, log, log_header, log_step, log_success, log_warning, 
    log_error, log_info, log_detail, log_progress, log_parallel_operation,
    retry_with_backoff, delete_local_path, create_zip_from_directory, 
    stopwatch, ProgressBar, MultiProgressBar
)


class AsyncFunctionBuilder:
    """Optimized function builder with parallel processing"""
    
    def __init__(self, config: ConfigManager, infra: str, branch: str, 
                 layer_arns: List[str], force_update_layers: bool = False):
        self.config = config
        self.infra = infra
        self.branch = branch
        self.layer_arns = layer_arns
        self.force_update_layers = force_update_layers
        self.lambda_client = config.lambda_client
        
        # Load router data
        self.router = self._load_router()
        
        # Group endpoints by function
        self.functions = {}
        for root_path, endpoints in groupby(self.router, lambda x: x['rootPath']):
            self.functions[root_path] = list(endpoints)
        
        log_success(f"Found {len(self.functions)} functions to process")
        log_detail("Functions discovered:")
        for func_name, endpoints in self.functions.items():
            log_detail(f"  • {func_name}: {len(endpoints)} endpoints")
    
    def _load_router(self) -> List[Dict]:
        """Load router data from endpoints"""
        try:
            from setup.endpoints import read_router
            return sorted(read_router(self.config.tool_config, api_path=self.config.api_path),
                         key=lambda x: x['rootPath'])
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
        
        return sorted(router, key=lambda x: x['rootPath'])
    
    async def _get_existing_functions(self) -> Dict[str, Dict]:
        """Get all existing Lambda functions with parallel pagination"""
        log("🔍 Retrieving existing Lambda functions...", 'blue')
        
        def get_functions():
            paginator = self.lambda_client.get_paginator('list_functions')
            functions = []
            for page in paginator.paginate():
                functions.extend(page['Functions'])
            return {f['FunctionName']: f for f in functions}
        
        functions = await asyncio.get_event_loop().run_in_executor(None, get_functions)
        log(f"Found {len(functions)} existing functions", 'green')
        return functions
    
    async def _process_function(self, function_name: str, endpoints: List[Dict], 
                              existing_functions: Dict[str, Dict]) -> bool:
        """Process a single function (create or update)"""
        expected_name = self.config.get_lambda_name(function_name)
        
        log(f"🔧 Processing function: {function_name} -> {expected_name}", 'blue')
        
        if expected_name not in existing_functions:
            return await self._create_function(function_name, endpoints, expected_name)
        else:
            return await self._update_function(function_name, endpoints, expected_name, 
                                             existing_functions[expected_name])
    
    async def _create_function(self, function_name: str, endpoints: List[Dict], 
                             expected_name: str) -> bool:
        """Create a new Lambda function"""
        log(f"📦 Creating new function: {expected_name}", 'yellow')
        
        zfnid = str(uuid4())
        zfn = Path('./') / f'{zfnid}.zip'
        
        try:
            # Create ZIP
            create_zip_from_directory(
                Path(self.config.api_path) / function_name,
                zfn,
                function_name=expected_name,
                short_name=function_name,
                router_data=endpoints
            )
            
            def create_func():
                with open(zfn, 'rb') as f:
                    return retry_with_backoff(lambda: self.lambda_client.create_function(
                        FunctionName=expected_name,
                        Runtime=self.config.tool_config.get('LAMBDA_RUNTIME', 'python3.11'),
                        Role=self.config.tool_config.get('LAMBDA_ROLE'),
                        Handler='lambda_function.lambda_handler',
                        Code={'ZipFile': f.read()},
                        Timeout=30,
                        MemorySize=2048,
                        PackageType='Zip',
                        Environment={'Variables': self.config.env_config},
                        Tags={
                            'app': self.config.app_name,
                            'infra': self.infra,
                        },
                        Layers=self.layer_arns,
                        Architectures=['x86_64']
                    ))
            
            await asyncio.get_event_loop().run_in_executor(None, create_func)
            log(f"✅ Created function: {expected_name}", 'green')
            return True
            
        except Exception as e:
            log(f"❌ Failed to create function {expected_name}: {e}", 'red')
            return False
        finally:
            delete_local_path(zfn)
    
    async def _update_function(self, function_name: str, endpoints: List[Dict],
                             expected_name: str, existing_config: Dict) -> bool:
        """Update existing Lambda function"""
        log(f"🔄 Updating function: {expected_name}", 'blue')
        
        # Check if code needs updating
        needs_code_update = await self._check_code_update(function_name, endpoints, expected_name, existing_config)
        
        # Check if configuration needs updating
        needs_config_update = await self._check_config_update(expected_name, existing_config)
        
        if needs_code_update:
            await self._update_function_code(function_name, endpoints, expected_name)
        
        if needs_config_update:
            await self._update_function_config(expected_name)
        
        if not needs_code_update and not needs_config_update:
            log(f"✅ Function {expected_name} is up to date", 'green')
        
        return True
    
    async def _check_code_update(self, function_name: str, endpoints: List[Dict],
                               expected_name: str, existing_config: Dict) -> bool:
        """Check if function code needs updating"""
        # Get current SHA
        def get_current_sha():
            return retry_with_backoff(lambda: self.lambda_client.get_function(
                FunctionName=expected_name
            )['Configuration']['CodeSha256'])
        
        current_sha = await asyncio.get_event_loop().run_in_executor(None, get_current_sha)
        
        # Create local ZIP and compare
        zfnid = str(uuid4())
        zfn = Path('./') / f'{zfnid}.zip'
        
        try:
            local_sha = create_zip_from_directory(
                Path(self.config.api_path) / function_name,
                zfn,
                function_name=expected_name,
                short_name=function_name,
                router_data=endpoints
            )
            
            return current_sha != local_sha
        finally:
            delete_local_path(zfn)
    
    async def _check_config_update(self, expected_name: str, existing_config: Dict) -> bool:
        """Check if function configuration needs updating"""
        existing_envvars = existing_config.get('Environment', {}).get('Variables', {})
        existing_envvars = {k: v for k, v in existing_envvars.items() 
                          if not k.startswith('VITE_')}
        
        existing_layers = [l['Arn'] for l in existing_config.get('Layers', [])]
        
        # Compare environment variables
        env_different = existing_envvars != self.config.env_config
        
        # Compare layers
        layers_different = set(existing_layers) != set(self.layer_arns)
        
        # Compare other config
        config_different = (
            existing_config.get('Role') != self.config.tool_config.get('LAMBDA_ROLE') or
            existing_config.get('Timeout') != 30 or
            existing_config.get('MemorySize') != 2048 or
            existing_config.get('Runtime') != self.config.tool_config.get('LAMBDA_RUNTIME', 'python3.11')
        )
        
        return env_different or layers_different or config_different or self.force_update_layers
    
    async def _update_function_code(self, function_name: str, endpoints: List[Dict], 
                                  expected_name: str):
        """Update function code"""
        log(f"📦 Updating code for: {expected_name}", 'yellow')
        
        zfnid = str(uuid4())
        zfn = Path('./') / f'{zfnid}.zip'
        
        try:
            create_zip_from_directory(
                Path(self.config.api_path) / function_name,
                zfn,
                function_name=expected_name,
                short_name=function_name,
                router_data=endpoints
            )
            
            def update_code():
                with open(zfn, 'rb') as f:
                    return retry_with_backoff(lambda: self.lambda_client.update_function_code(
                        FunctionName=expected_name,
                        ZipFile=f.read()
                    ))
            
            await asyncio.get_event_loop().run_in_executor(None, update_code)
            log(f"✅ Updated code for: {expected_name}", 'green')
            
        except Exception as e:
            log(f"❌ Failed to update code for {expected_name}: {e}", 'red')
        finally:
            delete_local_path(zfn)
    
    async def _update_function_config(self, expected_name: str):
        """Update function configuration"""
        log(f"⚙️ Updating config for: {expected_name}", 'yellow')
        
        def update_config():
            return retry_with_backoff(lambda: self.lambda_client.update_function_configuration(
                FunctionName=expected_name,
                Role=self.config.tool_config.get('LAMBDA_ROLE'),
                Timeout=30,
                MemorySize=2048,
                Handler='lambda_function.lambda_handler',
                Environment={'Variables': self.config.env_config},
                Runtime=self.config.tool_config.get('LAMBDA_RUNTIME', 'python3.11'),
                Layers=self.layer_arns
            ))
        
        await asyncio.get_event_loop().run_in_executor(None, update_config)
        log(f"✅ Updated config for: {expected_name}", 'green')
    
    async def build(self) -> Dict[str, bool]:
        """Build all functions in parallel"""
        stopwatch("Function building started")
        
        log_header("FUNCTION BUILDING")
        log_step("2", "Building Lambda functions with parallel processing")
        
        # Get existing functions
        existing_functions = await self._get_existing_functions()
        
        # Process functions in parallel with limited concurrency
        max_workers = min(10, len(self.functions))  # Limit concurrent operations
        log_info(f"Processing {len(self.functions)} functions with {max_workers} concurrent workers")
        
        results = {}
        progress_bar = ProgressBar(len(self.functions), "Building functions")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_function = {
                executor.submit(
                    self._process_function, 
                    function_name, 
                    endpoints, 
                    existing_functions
                ): function_name
                for function_name, endpoints in self.functions.items()
            }
            
            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_function):
                function_name = future_to_function[future]
                try:
                    result = future.result()
                    results[function_name] = result
                    completed += 1
                    progress_bar.update(1, f"Building functions ({completed}/{len(self.functions)})")
                except Exception as e:
                    log_error(f"Error processing function {function_name}: {e}")
                    results[function_name] = False
                    completed += 1
                    progress_bar.update(1, f"Building functions ({completed}/{len(self.functions)})")
        
        # Finish progress bar
        successful = sum(1 for success in results.values() if success)
        progress_bar.finish(f"Functions built: {successful}/{len(results)} successful")
