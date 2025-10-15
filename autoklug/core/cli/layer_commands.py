"""
Layer commands for autoklug CLI
"""
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import click
import requests
from click import echo, style

from ...utils import log_header, log_success, log_error, log_info, log_detail


@click.group()
def layer_commands():
    """📦 Layer commands"""
    pass


@layer_commands.command()
@click.argument('layer_path', type=click.Path())
@click.option('--force', is_flag=True, help='Force overwrite existing files')
def jumpstart(layer_path: str, force: bool):
    """🚀 Jumpstart a layer with bootstrap content from CloudFront"""
    
    layer_path = Path(layer_path).resolve()
    
    log_header("LAYER JUMPSTART")
    log_info(f"Target layer path: {layer_path}")
    
    # Validate layer path
    if not force and layer_path.exists():
        if layer_path.is_file():
            log_error(f"Layer path exists as a file: {layer_path}")
            raise click.Abort()
        elif layer_path.is_dir() and any(layer_path.iterdir()):
            log_error(f"Layer directory is not empty: {layer_path}")
            log_info("Use --force to overwrite existing content")
            raise click.Abort()
    
    try:
        # Create layer directory structure
        layer_path.mkdir(parents=True, exist_ok=True)
        
        # Download and extract bootstrap zip
        bootstrap_url = "https://dox20q8v7zmek.cloudfront.net/main-layer-bootstrap/layer-main.zip"
        log_info(f"Downloading bootstrap from: {bootstrap_url}")
        
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            response = requests.get(bootstrap_url, stream=True)
            response.raise_for_status()
            
            # Download with progress
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        log_detail(f"Download progress: {progress:.1f}%")
            
            temp_file.flush()
            temp_file_path = temp_file.name
        
        log_success("Bootstrap zip downloaded successfully")
        
        # Extract to main/ subdirectory
        main_dir = layer_path / "main"
        main_dir.mkdir(exist_ok=True)
        
        log_info(f"Extracting bootstrap content to: {main_dir}")
        
        with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
            # Extract all files to main directory
            for member in zip_ref.namelist():
                # Skip directory entries
                if member.endswith('/'):
                    continue
                
                # Extract file
                source = zip_ref.open(member)
                target_path = main_dir / member
                
                # Create parent directories if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write file
                with open(target_path, 'wb') as target_file:
                    target_file.write(source.read())
                
                source.close()
        
        log_success("Bootstrap content extracted successfully")
        
        # Create third-party directory and requirements.txt
        third_party_dir = layer_path / "third-party"
        third_party_dir.mkdir(exist_ok=True)
        
        requirements_path = third_party_dir / "requirements.txt"
        log_info(f"Creating requirements.txt at: {requirements_path}")
        
        # Get latest versions of supabase and requests
        try:
            supabase_version = get_latest_package_version("supabase")
            requests_version = get_latest_package_version("requests")
        except Exception as e:
            log_error(f"Failed to get latest package versions: {e}")
            # Fallback to known stable versions
            supabase_version = "2.3.4"
            requests_version = "2.31.0"
        
        requirements_content = f"""# Third-party dependencies for Lambda layer
supabase=={supabase_version}
requests=={requests_version}
"""
        
        with open(requirements_path, 'w') as f:
            f.write(requirements_content)
        
        log_success(f"Created requirements.txt with supabase=={supabase_version} and requests=={requests_version}")
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
        # Show final structure
        log_header("LAYER STRUCTURE CREATED")
        log_info(f"Layer path: {layer_path}")
        log_detail(f"├── main/ (bootstrap content)")
        log_detail(f"└── third-party/")
        log_detail(f"    └── requirements.txt")
        
        log_success("Layer jumpstart completed successfully!")
        
    except requests.RequestException as e:
        log_error(f"Failed to download bootstrap zip: {e}")
        raise click.Abort()
    except zipfile.BadZipFile as e:
        log_error(f"Invalid zip file downloaded: {e}")
        raise click.Abort()
    except Exception as e:
        log_error(f"Unexpected error during jumpstart: {e}")
        raise click.Abort()


def get_latest_package_version(package_name: str) -> str:
    """Get the latest version of a package from PyPI"""
    try:
        response = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=10)
        response.raise_for_status()
        data = response.json()
        return data['info']['version']
    except Exception as e:
        log_detail(f"Could not fetch latest version for {package_name}: {e}")
        raise
