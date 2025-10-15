"""
Zipping utilities for Lambda function and layer comparison

Replicates the zipping technique from builds.py for consistent SHA256 comparison
"""
import os
import zipfile
import hashlib
import base64
import stat
import shutil
from pathlib import Path
from uuid import uuid4
from typing import Optional, Dict, Any, List

import logging

# Configure logging
logger = logging.getLogger(__name__)

def log_detail(message: str):
    """Log a detailed message"""
    logger.info(f"   {message}")

def log_error(message: str):
    """Log an error message"""
    logger.error(f"❌ {message}")


def delete_local_path(path: str) -> bool:
    """Delete a local file or directory"""
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
        return True
    except Exception as e:
        log_error(f"Error deleting {path}: {e}")
        return False


def add_file(zip_file: zipfile.ZipFile, path: str, zip_path: Optional[str] = None):
    """Add a file to the zip archive with proper permissions and timestamps"""
    permission = 0o555 if os.access(path, os.X_OK) else 0o444
    zip_info = zipfile.ZipInfo.from_file(path, zip_path)
    zip_info.date_time = (2019, 1, 1, 0, 0, 0)  # Fixed timestamp for consistency
    zip_info.external_attr = (stat.S_IFREG | permission) << 16
    
    with open(path, "rb") as fp:
        zip_file.writestr(
            zip_info,
            fp.read(),
            compress_type=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        )


def create_zip_from_directory(
    directory: str, 
    output_filename: str, 
    function_name: Optional[str] = None, 
    short_name: Optional[str] = None, 
    router_data: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Create a zip file from a directory and return its SHA256 hash
    
    This replicates the exact zipping technique from builds.py for consistent comparison
    """
    with zipfile.ZipFile(output_filename, 'w') as zipf:
        # Add all files from the directory
        for root, _, files in os.walk(directory):
            for file in files:
                # Skip unwanted files (same exclusions as builds.py)
                if file.endswith('.pyc') or file.endswith('.virtualenv') or file.endswith('.pth'):
                    continue
                if file.endswith('-darwin.so'):
                    continue
                if file == '.DS_Store':
                    continue
                if file == '_virtualenv.py':
                    continue
                if 'site-packages/setuptools' in root or 'site-packages/pip' in root or 'site-packages/pkg_resources' in root or 'site-packages/wheel' in root or 'site-packages/_distutils_hack' in root:
                    continue
                if root.endswith('.dist-info'):
                    continue
                if root.endswith('__pycache__'):
                    continue
                
                # Add file with proper path mapping
                add_file(zipf, os.path.join(root, file),
                         os.path.join(root.replace(str(directory), 'python' if function_name is None else short_name).strip(os.sep), file))

        # Special handling for health endpoint (replicates builds.py logic)
        if short_name == 'health':
            healthid = str(uuid4())
            health_home = f'./TMP_{healthid}.py'
            with open(health_home, 'w') as f:
                f.write(f"""
from main import *
import json

def lambda_handler(event, context):
    return dict(statusCode=200, body=json.dumps("This endpoint is responding as it should! Kudos!"))
""")
            add_file(zipf, health_home, 'health/get.py')
            delete_local_path(health_home)

        # Generate lambda_function.py wrapper (replicates builds.py logic)
        if function_name:
            homeid = str(uuid4())
            fn_home = f'./TMP_{homeid}.py'
            data = router_data
            with open(fn_home, 'w') as f:
                f.write(f"""
from main import *
import importlib
import sys
sys.path.append("/var/task/")

def lambda_handler(event, context):
    method = event['requestContext']['httpMethod']
    resource = event['requestContext']['resourcePath']
    data = {str(data)}
    for ep in data:
        if method.lower() == ep.get('method').lower() and resource == ep.get('urlRuleAG'):
            module_loc = ep.get('filePath')
            module_loc = module_loc.replace('.py', '')
            module_loc = module_loc.replace('/', '.')
            globals()['module'] = importlib.import_module(module_loc)
            return globals()['module'].lambda_handler(event, context)
""")
            add_file(zipf, fn_home, 'lambda_function.py')
            delete_local_path(fn_home)

    return compute_sha256(output_filename)


def compute_sha256(file_path: str) -> str:
    """
    Compute SHA256 hash of a file and return base64 encoded result
    
    This replicates the exact hashing technique from builds.py
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        sha256.update(f.read())
    return base64.b64encode(sha256.digest()).decode('utf-8')


def create_zip_from_requirements_txt(requirements_path: str, zfnid: str, delete: bool = True) -> str:
    """
    Create a zip file from requirements.txt using virtual environment
    
    This replicates the exact technique from builds.py for thirdparty layers
    """
    envname = zfnid.replace('-', '')
    directory = f'./{envname}'
    
    log_detail(f"Creating environment for {envname}")
    create_virtualenv_and_install_requirements(envname, requirements_path)

    # Find the Python executable
    which_python = None
    for _, _, files in os.walk(directory):
        for file in files:
            if file.startswith('python3.'):
                which_python = file
                break
        if which_python:
            break

    log_detail("Fine-tuning files")
    # Clean up unwanted files
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.pyc') or file.endswith('.virtualenv') or file.endswith('.pth') or file.endswith('-darwin.so'):
                delete_local_path(os.path.join(root, file))
            if file == '.DS_Store':
                delete_local_path(os.path.join(root, file))
            if file == '_virtualenv.py':
                delete_local_path(os.path.join(root, file))

    # Create zip file
    zfn = Path('./') / f'{zfnid}.zip'
    with zipfile.ZipFile(zfn, 'w') as zipf:
        for root, _, files in os.walk(directory):
            for file in files:
                add_file(zipf, os.path.join(root, file),
                         os.path.join(root.replace(str(directory), 'python').strip(os.sep), file))

    # Clean up temporary directory
    if delete:
        delete_local_path(directory)

    return compute_sha256(str(zfn))


def create_virtualenv_and_install_requirements(envname: str, requirements_path: str):
    """
    Create a virtual environment and install requirements
    
    This replicates the exact technique from builds.py
    """
    directory = f'./{envname}'
    
    # Create virtual environment
    virtualenv.create_environment(directory, clear=True)
    
    # Install requirements
    python_executable = os.path.join(directory, 'bin', 'python')
    pip_executable = os.path.join(directory, 'bin', 'pip')
    
    # Install requirements
    import subprocess
    subprocess.run([pip_executable, 'install', '-r', requirements_path], check=True)


def compare_function_code(
    function_name: str, 
    local_directory: str, 
    cloud_sha: str, 
    router_data: Optional[List[Dict[str, Any]]] = None
) -> bool:
    """
    Compare local function code with cloud SHA256
    
    Returns True if code needs updating, False if it's the same
    """
    zfnid = str(uuid4())
    zfn = Path('./') / f'{zfnid}.zip'
    
    try:
        # Create zip from local directory
        local_sha = create_zip_from_directory(
            local_directory, 
            str(zfn), 
            function_name=function_name, 
            short_name=Path(local_directory).name,
            router_data=router_data
        )
        
        # Compare SHAs
        needs_update = cloud_sha != local_sha
        
        if needs_update:
            log_detail(f"Function {function_name} needs updating (SHA mismatch)")
        else:
            log_detail(f"Function {function_name} is up to date (SHA match)")
            
        return needs_update
        
    finally:
        # Clean up temporary zip file
        delete_local_path(str(zfn))


def compare_layer_code(
    layer_name: str, 
    local_directory: str, 
    cloud_sha: str
) -> bool:
    """
    Compare local layer code with cloud SHA256
    
    Returns True if layer needs updating, False if it's the same
    """
    zfnid = str(uuid4())
    zfn = Path('./') / f'{zfnid}.zip'
    
    try:
        # Create zip from local directory
        local_sha = create_zip_from_directory(local_directory, str(zfn))
        
        # Compare SHAs
        needs_update = cloud_sha != local_sha
        
        if needs_update:
            log_detail(f"Layer {layer_name} needs updating (SHA mismatch)")
        else:
            log_detail(f"Layer {layer_name} is up to date (SHA match)")
            
        return needs_update
        
    finally:
        # Clean up temporary zip file
        delete_local_path(str(zfn))


def create_function_zip(
    function_name: str, 
    local_directory: str, 
    router_data: Optional[List[Dict[str, Any]]] = None
) -> bytes:
    """
    Create a zip file for Lambda function deployment
    
    Returns the zip file content as bytes
    """
    zfnid = str(uuid4())
    zfn = Path('./') / f'{zfnid}.zip'
    
    try:
        # Create zip from local directory
        create_zip_from_directory(
            local_directory, 
            str(zfn), 
            function_name=function_name, 
            short_name=Path(local_directory).name,
            router_data=router_data
        )
        
        # Read zip content
        with open(zfn, 'rb') as f:
            zip_content = f.read()
            
        return zip_content
        
    finally:
        # Clean up temporary zip file
        delete_local_path(str(zfn))


def create_layer_zip(local_directory: str) -> bytes:
    """
    Create a zip file for Lambda layer deployment
    
    Returns the zip file content as bytes
    """
    zfnid = str(uuid4())
    zfn = Path('./') / f'{zfnid}.zip'
    
    try:
        # Create zip from local directory
        create_zip_from_directory(local_directory, str(zfn))
        
        # Read zip content
        with open(zfn, 'rb') as f:
            zip_content = f.read()
            
        return zip_content
        
    finally:
        # Clean up temporary zip file
        delete_local_path(str(zfn))
