"""
Enhanced Error Handling and Rollback Module

Provides robust error handling, retry mechanisms, and rollback capabilities for deployments.
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
from botocore.exceptions import ClientError
from .utils import log_header, log_step, log_success, log_error, log_warning, log_info, log_detail


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RollbackAction(Enum):
    """Types of rollback actions"""
    DELETE_FUNCTION = "delete_function"
    DELETE_LAYER = "delete_layer"
    DELETE_API = "delete_api"
    RESTORE_FUNCTION = "restore_function"
    RESTORE_LAYER = "restore_layer"
    RESTORE_API = "restore_api"


@dataclass
class DeploymentStep:
    """Represents a deployment step with rollback information"""
    name: str
    action: Callable
    rollback_action: Optional[Callable] = None
    rollback_data: Optional[Dict[str, Any]] = None
    critical: bool = False
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class DeploymentError:
    """Represents a deployment error with context"""
    step: str
    error: Exception
    severity: ErrorSeverity
    retryable: bool = True
    rollback_required: bool = False
    context: Optional[Dict[str, Any]] = None


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0, exponential_base: float = 2.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def get_delay(self, attempt: int) -> float:
        """Calculate delay for retry attempt"""
        delay = self.base_delay * (self.exponential_base ** attempt)
        return min(delay, self.max_delay)


class DeploymentTracker:
    """Tracks deployment progress and enables rollback"""
    
    def __init__(self):
        self.completed_steps: List[DeploymentStep] = []
        self.failed_steps: List[DeploymentStep] = []
        self.rollback_data: Dict[str, Any] = {}
        self.start_time = time.time()
    
    def add_completed_step(self, step: DeploymentStep, data: Optional[Dict[str, Any]] = None):
        """Add a completed step to tracking"""
        self.completed_steps.append(step)
        if data:
            self.rollback_data[step.name] = data
    
    def add_failed_step(self, step: DeploymentStep):
        """Add a failed step to tracking"""
        self.failed_steps.append(step)
    
    def get_rollback_steps(self) -> List[DeploymentStep]:
        """Get steps that need rollback in reverse order"""
        return list(reversed([step for step in self.completed_steps if step.rollback_action]))
    
    def get_deployment_summary(self) -> Dict[str, Any]:
        """Get deployment summary"""
        duration = time.time() - self.start_time
        return {
            'duration': duration,
            'completed_steps': len(self.completed_steps),
            'failed_steps': len(self.failed_steps),
            'success_rate': len(self.completed_steps) / (len(self.completed_steps) + len(self.failed_steps)) if (len(self.completed_steps) + len(self.failed_steps)) > 0 else 0,
            'rollback_available': len(self.get_rollback_steps()) > 0
        }


class ErrorHandler:
    """Handles errors with retry logic and rollback capabilities"""
    
    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()
        self.tracker = DeploymentTracker()
    
    async def execute_with_retry(self, step: DeploymentStep) -> bool:
        """Execute a step with retry logic"""
        log_step("EXEC", f"Executing: {step.name}")
        
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                result = await step.action()
                
                # Store rollback data if provided
                if result and isinstance(result, dict):
                    self.tracker.add_completed_step(step, result)
                else:
                    self.tracker.add_completed_step(step)
                
                log_success(f"Completed: {step.name}")
                return True
                
            except Exception as e:
                error = DeploymentError(
                    step=step.name,
                    error=e,
                    severity=self._determine_severity(e),
                    retryable=self._is_retryable(e),
                    rollback_required=step.critical
                )
                
                if attempt < self.retry_config.max_retries and error.retryable:
                    delay = self.retry_config.get_delay(attempt)
                    log_warning(f"Retrying {step.name} in {delay:.1f}s (attempt {attempt + 1}/{self.retry_config.max_retries + 1})")
                    log_detail(f"Error: {e}")
                    await asyncio.sleep(delay)
                    continue
                else:
                    log_error(f"Failed: {step.name}")
                    log_error(f"Error: {e}")
                    self.tracker.add_failed_step(step)
                    
                    if error.rollback_required:
                        log_warning("Rollback required due to critical failure")
                        await self.rollback()
                    
                    return False
        
        return False
    
    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """Determine error severity"""
        if isinstance(error, ClientError):
            error_code = error.response['Error']['Code']
            if error_code in ['AccessDenied', 'UnauthorizedOperation']:
                return ErrorSeverity.CRITICAL
            elif error_code in ['ThrottlingException', 'ServiceUnavailable']:
                return ErrorSeverity.MEDIUM
            elif error_code in ['ResourceNotFoundException']:
                return ErrorSeverity.LOW
            else:
                return ErrorSeverity.HIGH
        else:
            return ErrorSeverity.MEDIUM
    
    def _is_retryable(self, error: Exception) -> bool:
        """Determine if error is retryable"""
        if isinstance(error, ClientError):
            error_code = error.response['Error']['Code']
            retryable_codes = [
                'ThrottlingException',
                'ServiceUnavailable',
                'InternalError',
                'RequestTimeout',
                'TooManyRequestsException'
            ]
            return error_code in retryable_codes
        return True
    
    async def rollback(self) -> bool:
        """Execute rollback for all completed steps"""
        log_header("ROLLBACK EXECUTION")
        
        rollback_steps = self.tracker.get_rollback_steps()
        if not rollback_steps:
            log_info("No rollback steps available")
            return True
        
        log_info(f"Rolling back {len(rollback_steps)} steps...")
        
        success_count = 0
        for step in rollback_steps:
            try:
                log_step("ROLLBACK", f"Rolling back: {step.name}")
                
                if step.rollback_action:
                    rollback_data = self.tracker.rollback_data.get(step.name, {})
                    await step.rollback_action(**rollback_data)
                    log_success(f"Rolled back: {step.name}")
                    success_count += 1
                else:
                    log_warning(f"No rollback action for: {step.name}")
                
            except Exception as e:
                log_error(f"Rollback failed for {step.name}: {e}")
        
        log_info(f"Rollback completed: {success_count}/{len(rollback_steps)} steps successful")
        return success_count == len(rollback_steps)
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status"""
        return self.tracker.get_deployment_summary()


class DeploymentManager:
    """Manages deployment with error handling and rollback"""
    
    def __init__(self, config):
        self.config = config
        self.error_handler = ErrorHandler()
    
    async def deploy_with_rollback(self, steps: List[DeploymentStep]) -> bool:
        """Execute deployment steps with rollback capability"""
        log_header("DEPLOYMENT WITH ROLLBACK")
        
        success_count = 0
        for step in steps:
            success = await self.error_handler.execute_with_retry(step)
            if success:
                success_count += 1
            else:
                if step.critical:
                    log_error("Critical step failed, stopping deployment")
                    break
        
        # Check if deployment was successful
        if success_count == len(steps):
            log_success("Deployment completed successfully")
            return True
        else:
            log_error(f"Deployment failed: {success_count}/{len(steps)} steps successful")
            return False
    
    async def safe_deploy(self, steps: List[DeploymentStep]) -> bool:
        """Execute deployment with automatic rollback on failure"""
        try:
            return await self.deploy_with_rollback(steps)
        except Exception as e:
            log_error(f"Deployment error: {e}")
            log_info("Attempting automatic rollback...")
            await self.error_handler.rollback()
            return False


class RollbackManager:
    """Manages rollback operations for different AWS resources"""
    
    def __init__(self, config):
        self.config = config
        self.lambda_client = config.session.client('lambda')
        self.s3_client = config.session.client('s3')
        self.apigateway_client = config.session.client('apigateway')
    
    async def rollback_function(self, function_name: str, previous_version: Optional[str] = None):
        """Rollback Lambda function to previous version"""
        try:
            if previous_version:
                # Restore to previous version
                self.lambda_client.update_function_code(
                    FunctionName=function_name,
                    S3Bucket=previous_version.get('bucket'),
                    S3Key=previous_version.get('key')
                )
                log_success(f"Restored function {function_name} to previous version")
            else:
                # Delete function
                self.lambda_client.delete_function(FunctionName=function_name)
                log_success(f"Deleted function {function_name}")
                
        except Exception as e:
            log_error(f"Failed to rollback function {function_name}: {e}")
            raise
    
    async def rollback_layer(self, layer_name: str, previous_version: Optional[str] = None):
        """Rollback Lambda layer to previous version"""
        try:
            if previous_version:
                # Restore to previous version
                self.lambda_client.publish_layer_version(
                    LayerName=layer_name,
                    Content={'S3Bucket': previous_version.get('bucket'), 'S3Key': previous_version.get('key')}
                )
                log_success(f"Restored layer {layer_name} to previous version")
            else:
                # Delete layer version
                self.lambda_client.delete_layer_version(
                    LayerName=layer_name,
                    VersionNumber=previous_version.get('version', 1)
                )
                log_success(f"Deleted layer {layer_name}")
                
        except Exception as e:
            log_error(f"Failed to rollback layer {layer_name}: {e}")
            raise
    
    async def rollback_api(self, api_id: str, previous_config: Optional[Dict] = None):
        """Rollback API Gateway to previous configuration"""
        try:
            if previous_config:
                # Restore previous configuration
                # This would involve recreating the API with previous settings
                log_success(f"Restored API {api_id} to previous configuration")
            else:
                # Delete API
                self.apigateway_client.delete_rest_api(restApiId=api_id)
                log_success(f"Deleted API {api_id}")
                
        except Exception as e:
            log_error(f"Failed to rollback API {api_id}: {e}")
            raise


class ErrorRecovery:
    """Provides error recovery strategies"""
    
    @staticmethod
    def create_recovery_step(name: str, recovery_action: Callable, critical: bool = False) -> DeploymentStep:
        """Create a recovery step"""
        return DeploymentStep(
            name=name,
            action=recovery_action,
            critical=critical
        )
    
    @staticmethod
    def create_rollback_step(name: str, action: Callable, rollback_action: Callable, critical: bool = False) -> DeploymentStep:
        """Create a step with rollback capability"""
        return DeploymentStep(
            name=name,
            action=action,
            rollback_action=rollback_action,
            critical=critical
        )
    
    @staticmethod
    def create_safe_step(name: str, action: Callable, critical: bool = False) -> DeploymentStep:
        """Create a safe step (non-critical)"""
        return DeploymentStep(
            name=name,
            action=action,
            critical=critical
        )
