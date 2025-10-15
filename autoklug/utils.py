"""
Core utilities for the blazing fast build system
"""
import asyncio
import hashlib
import json
import logging
import os
import shutil
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import dotenv_values
from termcolor import cprint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global timing
ZERO = time.perf_counter()

# Console styling
class ConsoleStyle:
    """Console styling constants"""
    HEADER = 'cyan'
    SUCCESS = 'green'
    WARNING = 'yellow'
    ERROR = 'red'
    INFO = 'blue'
    STEP = 'magenta'
    DETAIL = 'white'
    TIMING = 'cyan'
    PROGRESS = 'yellow'

class ProgressBar:
    """Enhanced progress bar for console output with Click integration"""
    
    def __init__(self, total: int, description: str = "Progress", show_percentage: bool = True):
        self.total = total
        self.current = 0
        self.description = description
        self.start_time = time.time()
        self._last_update = 0
        self.show_percentage = show_percentage
        self._completed = False
    
    def update(self, increment: int = 1, description: str = None, show_eta: bool = True):
        """Update progress bar"""
        if self._completed:
            return
            
        self.current += increment
        if description:
            self.description = description
        
        # Only update every 0.1 seconds to avoid spam
        now = time.time()
        if now - self._last_update < 0.1 and self.current < self.total:
            return
        
        self._last_update = now
        self._display(show_eta)
    
    def _display(self, show_eta: bool = True):
        """Display the progress bar"""
        if self.total == 0:
            return
        
        percentage = (self.current / self.total) * 100
        bar_length = 40
        filled_length = int(bar_length * self.current // self.total)
        
        # Create progress bar with different characters
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        
        elapsed = time.time() - self.start_time
        
        # Calculate ETA
        if self.current > 0 and show_eta:
            eta = (elapsed / self.current) * (self.total - self.current)
            if eta < 60:
                eta_str = f"ETA: {eta:.1f}s"
            else:
                minutes = int(eta // 60)
                seconds = eta % 60
                eta_str = f"ETA: {minutes}m {seconds:.0f}s"
        else:
            eta_str = ""
        
        # Format the progress display
        if self.show_percentage:
            progress_text = f"{self.description}: [{bar}] {percentage:5.1f}% ({self.current}/{self.total})"
        else:
            progress_text = f"{self.description}: [{bar}] ({self.current}/{self.total})"
        
        if eta_str:
            progress_text += f" {eta_str}"
        
        # Clear line and print progress
        sys.stdout.write(f'\r{progress_text}')
        sys.stdout.flush()
        
        if self.current >= self.total:
            self._completed = True
            print()  # New line when complete
    
    def finish(self, message: str = "Complete"):
        """Finish the progress bar with a message"""
        if not self._completed:
            self.current = self.total
            self._display(show_eta=False)
        
        elapsed = time.time() - self.start_time
        if elapsed < 1:
            time_str = f"{elapsed*1000:.0f}ms"
        elif elapsed < 60:
            time_str = f"{elapsed:.2f}s"
        else:
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            time_str = f"{minutes}m {seconds:.1f}s"
        
        print(f"✅ {message} ({time_str})")


class MultiProgressBar:
    """Multiple progress bars for parallel operations"""
    
    def __init__(self):
        self.bars = {}
        self.completed = {}
    
    def add_bar(self, key: str, total: int, description: str):
        """Add a progress bar"""
        self.bars[key] = ProgressBar(total, description)
        self.completed[key] = False
    
    def update(self, key: str, increment: int = 1, description: str = None):
        """Update a specific progress bar"""
        if key in self.bars and not self.completed[key]:
            self.bars[key].update(increment, description)
            
            # Check if completed
            if self.bars[key].current >= self.bars[key].total:
                self.completed[key] = True
    
    def finish(self, key: str, message: str = "Complete"):
        """Finish a specific progress bar"""
        if key in self.bars:
            self.bars[key].finish(message)
            self.completed[key] = True
    
    def is_all_complete(self) -> bool:
        """Check if all progress bars are complete"""
        return all(self.completed.values())


def stopwatch(msg: str = ""):
    """Enhanced timing utility with better formatting"""
    global ZERO
    t = time.perf_counter()
    if msg:
        elapsed = t - ZERO
        if elapsed < 1:
            time_str = f"{elapsed*1000:.0f}ms"
        elif elapsed < 60:
            time_str = f"{elapsed:.3f}s"
        else:
            minutes = int(elapsed // 60)
            seconds = elapsed % 60
            time_str = f"{minutes}m {seconds:.1f}s"
        
        cprint(f"⏱️  {msg}: {time_str}", ConsoleStyle.TIMING)
    ZERO = t


def log(message: str, color: Optional[str] = None, prefix: str = ""):
    """Enhanced colored logging utility"""
    if prefix:
        message = f"{prefix} {message}"
    
    if color:
        cprint(message, color)
    else:
        print(message)


def log_header(message: str):
    """Log a header message"""
    print()
    cprint("=" * 60, ConsoleStyle.HEADER)
    cprint(f"🚀 {message}", ConsoleStyle.HEADER)
    cprint("=" * 60, ConsoleStyle.HEADER)
    print()


def log_step(step: str, description: str):
    """Log a build step"""
    cprint(f"📋 Step {step}: {description}", ConsoleStyle.STEP)


def log_success(message: str):
    """Log a success message"""
    cprint(f"✅ {message}", ConsoleStyle.SUCCESS)


def log_warning(message: str):
    """Log a warning message"""
    cprint(f"⚠️  {message}", ConsoleStyle.WARNING)


def log_error(message: str):
    """Log an error message"""
    cprint(f"❌ {message}", ConsoleStyle.ERROR)


def log_info(message: str):
    """Log an info message"""
    cprint(f"ℹ️  {message}", ConsoleStyle.INFO)


def log_detail(message: str):
    """Log a detailed message"""
    cprint(f"   {message}", ConsoleStyle.DETAIL)


def log_progress(message: str):
    """Log a progress message"""
    cprint(f"🔄 {message}", ConsoleStyle.PROGRESS)


def log_build_summary(results: Dict[str, Any]):
    """Log a comprehensive build summary"""
    print()
    log_header("BUILD SUMMARY")
    
    # Function results
    if 'functions' in results:
        func_results = results['functions']
        successful = sum(1 for success in func_results.values() if success)
        total = len(func_results)
        log_success(f"Functions: {successful}/{total} successful")
        
        if successful < total:
            failed = [name for name, success in func_results.items() if not success]
            log_warning(f"Failed functions: {', '.join(failed)}")
    
    # Layer results
    if 'layers' in results:
        layer_count = len(results['layers'])
        log_success(f"Layers: {layer_count} configured")
    
    # API results
    if 'api' in results:
        api_info = results['api']
        log_success(f"API: {api_info.get('name', 'Unknown')}")
        if 'endpoint' in api_info:
            log_detail(f"Endpoint: {api_info['endpoint']}/live")
    
    # Timing information
    if 'timing' in results:
        timing = results['timing']
        log_info(f"Total build time: {timing.get('total', 'Unknown')}")
    
    print()


def log_parallel_operation(operation: str, count: int, completed: int):
    """Log parallel operation progress"""
    percentage = (completed / count) * 100 if count > 0 else 0
    cprint(f"⚡ {operation}: {completed}/{count} ({percentage:.1f}%)", ConsoleStyle.PROGRESS)


def detect_project_context() -> dict:
    """Detect project context from the current directory"""
    current_dir = Path.cwd()
    
    # Look for common project files
    tool_files = []
    env_files = []
    
    # Check for .tool files
    for tool_file in current_dir.glob('.tool*'):
        if tool_file.is_file():
            tool_files.append(str(tool_file))
    
    # Check for .env files
    for env_file in current_dir.glob('.env*'):
        if env_file.is_file():
            env_files.append(str(env_file))
    
    # Detect API structure
    api_paths = []
    for api_dir in ['api', 'api_public', 'src/api', 'functions', 'lambda']:
        api_path = current_dir / api_dir
        if api_path.exists() and api_path.is_dir():
            api_paths.append(str(api_path))
    
    # Detect layer structure
    layer_paths = []
    for layer_dir in ['layers', 'lambda_layers', 'src/layers']:
        layer_path = current_dir / layer_dir
        if layer_path.exists() and layer_path.is_dir():
            layer_paths.append(str(layer_path))
    
    # Detect infrastructure from common patterns
    infra = 'dev'  # Default
    if any('prod' in str(f) for f in tool_files):
        infra = 'prod'
    elif any('staging' in str(f) for f in tool_files):
        infra = 'staging'
    
    # Detect if this is a public API project
    is_public = any('public' in str(p) for p in api_paths) or any('public' in str(f) for f in tool_files)
    
    return {
        'tool_files': tool_files,
        'env_files': env_files,
        'api_paths': api_paths,
        'layer_paths': layer_paths,
        'infra': infra,
        'is_public': is_public,
        'current_dir': str(current_dir)
    }


def find_best_config_files(context: dict) -> tuple:
    """Find the best tool and env files to use"""
    tool_files = context['tool_files']
    env_files = context['env_files']
    
    # Prefer .tool over .tool.dev, .tool.prod, etc.
    tool_file = None
    if '.tool' in tool_files:
        tool_file = '.tool'
    elif tool_files:
        tool_file = tool_files[0]  # Use first available
    
    # Prefer .env over .env.dev, .env.prod, etc.
    env_file = None
    if '.env' in env_files:
        env_file = '.env'
    elif env_files:
        env_file = env_files[0]  # Use first available
    
    return tool_file, env_file


def retry_with_backoff(func, max_retries: int = 5, base_delay: float = 1.0):
    """Retry function with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return func()
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            if error_code in ['ThrottlingException', 'TooManyRequestsException']:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    log(f"Retrying after {delay}s (attempt {attempt + 1}/{max_retries})", 'yellow')
                    time.sleep(delay)
                    continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                log(f"Retrying after {delay}s (attempt {attempt + 1}/{max_retries}): {e}", 'yellow')
                time.sleep(delay)
                continue
            raise
    return None


def delete_local_path(path: Path):
    """Safely delete local file or directory"""
    try:
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        return True
    except Exception as e:
        log(f"Error deleting {path}: {e}", 'red')
        return False


def create_zip_from_directory(directory: Path, output_filename: Path, 
                            function_name: Optional[str] = None,
                            short_name: Optional[str] = None,
                            router_data: Optional[List[Dict]] = None) -> str:
    """Create ZIP file from directory with SHA256 hash"""
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(directory)
                zip_file.write(file_path, arcname)
        
        # Add router data if provided
        if router_data:
            router_json = json.dumps(router_data, indent=2)
            zip_file.writestr('router.json', router_json)
    
    # Calculate SHA256
    with open(output_filename, 'rb') as f:
        sha256_hash = hashlib.sha256(f.read()).hexdigest()
    
    return sha256_hash


def create_zip_from_requirements_txt(requirements_path: Path, output_filename: Path) -> str:
    """Create ZIP from requirements.txt using pip"""
    import subprocess
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Install requirements
        subprocess.run([
            'pip', 'install', '-r', str(requirements_path),
            '-t', str(temp_path),
            '--no-deps', '--no-cache-dir'
        ], check=True, capture_output=True)
        
        # Create ZIP
        with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, files in os.walk(temp_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(temp_path)
                    zip_file.write(file_path, arcname)
        
        # Calculate SHA256
        with open(output_filename, 'rb') as f:
            sha256_hash = hashlib.sha256(f.read()).hexdigest()
        
        return sha256_hash


def get_s3_object_hash(s3_client, bucket: str, key: str) -> Optional[str]:
    """Get SHA256 hash of S3 object"""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        return response.get('Metadata', {}).get('sha256')
    except ClientError:
        return None


def upload_to_s3_with_hash(s3_client, file_path: Path, bucket: str, key: str) -> str:
    """Upload file to S3 with SHA256 hash in metadata"""
    with open(file_path, 'rb') as f:
        content = f.read()
        sha256_hash = hashlib.sha256(content).hexdigest()
    
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        Metadata={'sha256': sha256_hash}
    )
    
    return sha256_hash


def current_branch() -> str:
    """Get current git branch"""
    try:
        from git import Repo
        repo = Repo('./')
        return repo.active_branch.name
    except Exception:
        return 'main'


class ConfigManager:
    """Manages configuration from .env and .tool files"""
    
    def __init__(self, tool_path: str, env_path: Optional[str] = None):
        self.tool_config = dotenv_values(tool_path)
        self.env_config = dotenv_values(env_path) if env_path else {}
        
        # Filter out VITE_ variables
        if self.env_config:
            self.env_config = {k: v for k, v in self.env_config.items() 
                             if not k.startswith('VITE_')}
        
        # Determine if this is a public API build
        self.is_public_build = 'public' in tool_path.lower() or 'public' in self.tool_config.get('API_PATH', '')
        
        # Setup AWS session
        self.session = boto3.Session(
            profile_name=self.tool_config.get('AWS_PROFILE_BUILD')
        )
        
        # Create clients with optimized config
        config = Config(
            region_name=self.tool_config.get('AWS_REGION'),
            retries={'max_attempts': 10, 'mode': 'adaptive'},
            max_pool_connections=50
        )
        
        self.lambda_client = self.session.client('lambda', config=config)
        self.s3_client = self.session.client('s3', config=config)
        self.apigateway_client = self.session.client('apigatewayv2', config=config)
    
    @property
    def app_name(self) -> str:
        """Get app name based on build type"""
        if self.is_public_build:
            return self.tool_config.get('PUBLIC_APP_NAME', 'public')
        return self.tool_config.get('APP_NAME', 'app')
    
    @property
    def api_path(self) -> str:
        """Get API path based on build type"""
        if self.is_public_build:
            return './api_public'
        return self.tool_config.get('API_PATH', './api')
    
    def get_lambda_name(self, function_name: str) -> str:
        """Generate Lambda function name"""
        return f"api-{self.app_name}-{self.tool_config.get('INFRA', 'dev')}-{function_name}"
