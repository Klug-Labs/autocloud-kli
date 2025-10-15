"""
Core builders for autoklug
"""
import asyncio
from typing import Optional

from ...utils import (
    ConfigManager, log_header, log_step, log_success, log_warning, 
    log_error, log_info, log_detail, log_progress, log_build_summary,
    stopwatch, current_branch, detect_project_context, find_best_config_files
)
from ...layers import AsyncLayerBuilder
from ...functions import AsyncFunctionBuilder
from ...api import AsyncApiBuilder
from ...config_permissions import ConfigPermissionsManager


class BlazingFastBuilder:
    """Main builder class that orchestrates the entire build process"""
    
    def __init__(self, tool_path: Optional[str] = None, env_path: Optional[str] = None, 
                 force_update_layers: bool = False):
        # Detect project context if not provided
        if not tool_path or not env_path:
            context = detect_project_context()
            detected_tool, detected_env = find_best_config_files(context)
            
            self.tool_path = tool_path or detected_tool
            self.env_path = env_path or detected_env
            self.infra = context['infra']
            
            log_info(f"Auto-detected project context:")
            log_detail(f"  Directory: {context['current_dir']}")
            log_detail(f"  Infrastructure: {self.infra}")
            log_detail(f"  Public API: {context['is_public']}")
            log_detail(f"  API paths found: {context['api_paths']}")
            log_detail(f"  Layer paths found: {context['layer_paths']}")
        else:
            self.tool_path = tool_path
            self.env_path = env_path
            self.infra = 'dev'  # Default when explicitly provided
        
        self.force_update_layers = force_update_layers
        
        # Load configuration
        self.config = ConfigManager(self.tool_path, self.env_path)
        self.branch = current_branch()
        
        log_header("BLAZING FAST BUILD SYSTEM v2")
        log_info(f"Tool config: {self.tool_path}")
        log_info(f"Env config: {self.env_path or 'None'}")
        log_info(f"Infrastructure: {self.infra}")
        log_info(f"Branch: {self.branch}")
        log_info(f"Public build: {self.config.is_public_build}")
        log_info(f"API path: {self.config.api_path}")
    
    async def build(self) -> bool:
        """Run the complete build process"""
        stopwatch("Total build started")
        
        try:
            log_header("STARTING BLAZING FAST BUILD")
            
            # Step 1: Build layers
            log_step("1", "Building Lambda layers")
            layer_builder = AsyncLayerBuilder(self.config, self.infra, self.branch)
            layer_arns = await layer_builder.build()
            
            # Step 2: Build functions
            log_step("2", "Building Lambda functions")
            function_builder = AsyncFunctionBuilder(
                self.config, self.infra, self.branch, layer_arns, self.force_update_layers
            )
            function_results = await function_builder.build()
            
            # Step 3: Build API
            log_step("3", "Building API Gateway")
            api_builder = AsyncApiBuilder(self.config, self.infra, self.branch)
            api_id, endpoint = await api_builder.build()
            
            # Step 4: Post-build tasks
            log_step("4", "Running post-build tasks")
            config_manager = ConfigPermissionsManager(self.config, self.infra, self.branch)
            post_build_results = await config_manager.run_post_build_tasks(
                api_id, endpoint, function_results
            )
            
            # Build summary
            log_build_summary(function_results, layer_arns, api_id, endpoint)
            
            stopwatch("Total build completed")
            return True
            
        except Exception as e:
            log_error(f"Build failed: {e}")
            stopwatch("Total build completed")
            return False
    
    async def build_layers_only(self) -> bool:
        """Build only layers"""
        try:
            log_header("BUILDING LAMBDA LAYERS")
            layer_builder = AsyncLayerBuilder(self.config, self.infra, self.branch)
            await layer_builder.build()
            return True
        except Exception as e:
            log_error(f"Layer build failed: {e}")
            return False
    
    async def build_functions_only(self) -> bool:
        """Build only functions"""
        try:
            log_header("BUILDING LAMBDA FUNCTIONS")
            # Get layer ARNs first
            layer_builder = AsyncLayerBuilder(self.config, self.infra, self.branch)
            layer_arns = await layer_builder.get_existing_layers()
            
            function_builder = AsyncFunctionBuilder(
                self.config, self.infra, self.branch, layer_arns, self.force_update_layers
            )
            await function_builder.build()
            return True
        except Exception as e:
            log_error(f"Function build failed: {e}")
            return False
    
    async def build_api_only(self) -> bool:
        """Build only API Gateway"""
        try:
            log_header("BUILDING API GATEWAY")
            api_builder = AsyncApiBuilder(self.config, self.infra, self.branch)
            await api_builder.build()
            return True
        except Exception as e:
            log_error(f"API Gateway build failed: {e}")
            return False
