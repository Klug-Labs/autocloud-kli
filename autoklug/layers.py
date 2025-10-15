"""
Blazing Fast Layer Builder with S3 requirements.txt checking
"""
import asyncio
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from .utils import (
    ConfigManager, log, log_header, log_step, log_success, log_warning, 
    log_error, log_info, log_detail, log_progress, log_parallel_operation,
    retry_with_backoff, delete_local_path, create_zip_from_directory, 
    create_zip_from_requirements_txt, get_s3_object_hash, upload_to_s3_with_hash, 
    stopwatch, ProgressBar
)


class AsyncLayerBuilder:
    """Optimized layer builder with parallel processing and S3 requirements.txt checking"""
    
    def __init__(self, config: ConfigManager, infra: str, branch: str):
        self.config = config
        self.infra = infra
        self.branch = branch
        self.lambda_client = config.lambda_client
        self.s3_client = config.s3_client
        
        # Layer naming
        self.shared_layer_name = f"layer-main-{infra}-{branch}"
        self.thirdparty_layer_name = f"layer-thirdparty-{infra}-{branch}"
        
        # S3 configuration for requirements.txt
        self.s3_bucket = self._get_s3_bucket_name()
        self.s3_key = f"requirements/{infra}/{branch}/requirements.txt"
    
    def _get_layer_architecture(self) -> str:
        """Get the target architecture for Lambda layers"""
        architecture = self.config.tool_config.get('LAYER_ARCHITECTURE', 'x86_64')
        
        # Validate architecture
        valid_architectures = ['x86_64', 'arm64']
        if architecture not in valid_architectures:
            log_warning(f"Invalid architecture '{architecture}', using x86_64")
            architecture = 'x86_64'
        
        log_detail(f"Using layer architecture: {architecture}")
        return architecture
    
    def _get_s3_bucket_name(self) -> str:
        """Generate unique S3 bucket name based on app name"""
        app_name = self.config.tool_config.get('APP_NAME', 'autoklug')
        # Remove any invalid characters and make lowercase
        clean_app_name = app_name.lower().replace('_', '-').replace(' ', '-')
        # Remove any non-alphanumeric characters except hyphens
        import re
        clean_app_name = re.sub(r'[^a-z0-9-]', '', clean_app_name)
        return f"{clean_app_name}-requirements-txt-bucket"
    
    async def _get_existing_layers(self) -> Tuple[Dict[str, str], Dict[str, str]]:
        """Get existing layers with parallel pagination"""
        log_progress("Retrieving existing layers from AWS...")
        
        def get_layers():
            paginator = self.lambda_client.get_paginator('list_layers')
            layers = []
            for page in paginator.paginate():
                layers.extend(page['Layers'])
            return layers
        
        layers = await asyncio.get_event_loop().run_in_executor(None, get_layers)
        
        # Filter for our layers
        layer_versions = {}
        layer_arns = {}
        
        for layer in layers:
            name = layer.get('LayerName')
            if name in [self.shared_layer_name, self.thirdparty_layer_name]:
                latest_version = layer.get('LatestMatchingVersion', {})
                layer_versions[name] = latest_version.get('Version')
                layer_arns[name] = latest_version.get('LayerVersionArn')
        
        log_success(f"Found {len(layer_versions)} existing layers")
        log_detail(f"Shared layer: {self.shared_layer_name}")
        log_detail(f"Thirdparty layer: {self.thirdparty_layer_name}")
        
        return layer_versions, layer_arns
    
    async def _check_shared_layer(self, existing_versions: Dict[str, str], 
                                existing_arns: Dict[str, str]) -> Optional[str]:
        """Check and update shared layer if needed"""
        log_progress("Checking shared layer for updates...")
        
        if self.shared_layer_name not in existing_versions:
            log_warning("Shared layer doesn't exist, creating new version...")
            return await self._create_shared_layer()
        
        log_detail(f"Shared layer exists (version {existing_versions[self.shared_layer_name]})")
        
        # Get current layer SHA
        def get_layer_sha():
            return retry_with_backoff(lambda: self.lambda_client.get_layer_version(
                LayerName=self.shared_layer_name,
                VersionNumber=existing_versions[self.shared_layer_name]
            )['Content']['CodeSha256'])
        
        current_sha = await asyncio.get_event_loop().run_in_executor(None, get_layer_sha)
        log_detail(f"Current layer SHA: {current_sha[:16]}...")
        
        # Create local ZIP and compare
        zfnid = str(uuid4())
        zfn = Path('./') / f'{zfnid}.zip'
        
        try:
            log_detail("Creating local ZIP for comparison...")
            local_sha = create_zip_from_directory(
                Path(self.config.tool_config.get('LAYER_PATH', './layers')) / 'shared',
                zfn
            )
            log_detail(f"Local layer SHA: {local_sha[:16]}...")
            
            if current_sha != local_sha:
                log_warning("Shared layer content changed, rebuilding...")
                return await self._create_shared_layer()
            else:
                log_success("Shared layer is up to date")
                return existing_arns[self.shared_layer_name]
        finally:
            delete_local_path(zfn)
    
    async def _create_shared_layer(self) -> str:
        """Create new shared layer version"""
        log_progress("Creating new shared layer version...")
        
        zfnid = str(uuid4())
        zfn = Path('./') / f'{zfnid}.zip'
        
        try:
            log_detail("Packaging shared layer code...")
            create_zip_from_directory(
                Path(self.config.tool_config.get('LAYER_PATH', './layers')) / 'shared',
                zfn
            )
            
            def publish_layer():
                with open(zfn, 'rb') as f:
                    return retry_with_backoff(lambda: self.lambda_client.publish_layer_version(
                        LayerName=self.shared_layer_name,
                        Content={'ZipFile': f.read()},
                        CompatibleRuntimes=self.config.tool_config.get(
                            'LAYER_COMPATIBLE_RUNTIMES', 'python3.11'
                        ).split(','),
                        CompatibleArchitectures=[self._get_layer_architecture()]
                    ))
            
            log_detail("Publishing layer to AWS...")
            response = await asyncio.get_event_loop().run_in_executor(None, publish_layer)
            log_success(f"Shared layer created successfully (version {response['Version']})")
            return response['LayerVersionArn']
        finally:
            delete_local_path(zfn)
    
    async def _check_thirdparty_layer(self, existing_versions: Dict[str, str],
                                    existing_arns: Dict[str, str]) -> str:
        """Check thirdparty layer against S3 requirements.txt"""
        log("🔧 Checking thirdparty layer...", 'blue')
        
        # Ensure S3 bucket exists before checking
        await self._ensure_s3_bucket_exists()
        
        # Get S3 requirements.txt hash
        def get_s3_hash():
            return get_s3_object_hash(self.s3_client, self.s3_bucket, self.s3_key)
        
        s3_hash = await asyncio.get_event_loop().run_in_executor(None, get_s3_hash)
        
        if not s3_hash:
            log("📤 No S3 requirements.txt found, uploading current...", 'yellow')
            await self._upload_requirements_to_s3()
            return await self._create_thirdparty_layer()
        
        # Compare with local requirements.txt
        local_req_path = Path(self.config.tool_config.get('LAYER_PATH', './layers')) / 'thirdparty' / 'requirements.txt'
        
        if not local_req_path.exists():
            log("❌ Local requirements.txt not found", 'red')
            return f"arn:aws:lambda:{self.config.tool_config.get('AWS_REGION')}:{self.config.tool_config.get('AWS_ACCOUNT_ID')}:layer:{self.thirdparty_layer_name}:23"
        
        def get_local_hash():
            with open(local_req_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        
        local_hash = await asyncio.get_event_loop().run_in_executor(None, get_local_hash)
        
        if local_hash != s3_hash:
            log("🔄 Requirements.txt changed, updating thirdparty layer...", 'yellow')
            await self._upload_requirements_to_s3()
            return await self._create_thirdparty_layer()
        else:
            log("✅ Thirdparty layer is up to date", 'green')
            if self.thirdparty_layer_name in existing_arns:
                return existing_arns[self.thirdparty_layer_name]
            else:
                return f"arn:aws:lambda:{self.config.tool_config.get('AWS_REGION')}:{self.config.tool_config.get('AWS_ACCOUNT_ID')}:layer:{self.thirdparty_layer_name}:23"
    
    async def _upload_requirements_to_s3(self):
        """Upload current requirements.txt to S3, creating bucket if needed"""
        local_req_path = Path(self.config.tool_config.get('LAYER_PATH', './layers')) / 'thirdparty' / 'requirements.txt'
        
        # Ensure S3 bucket exists
        await self._ensure_s3_bucket_exists()
        
        def upload():
            return upload_to_s3_with_hash(
                self.s3_client, local_req_path, self.s3_bucket, self.s3_key
            )
        
        await asyncio.get_event_loop().run_in_executor(None, upload)
        log("📤 Requirements.txt uploaded to S3", 'green')
    
    async def _ensure_s3_bucket_exists(self):
        """Ensure S3 bucket exists, create if it doesn't"""
        def check_bucket_exists():
            try:
                self.s3_client.head_bucket(Bucket=self.s3_bucket)
                return True
            except self.s3_client.exceptions.NoSuchBucket:
                return False
            except Exception as e:
                log(f"⚠️ Error checking bucket existence: {e}", 'yellow')
                return False
        
        bucket_exists = await asyncio.get_event_loop().run_in_executor(None, check_bucket_exists)
        
        if not bucket_exists:
            log(f"🪣 Creating S3 bucket: {self.s3_bucket}", 'blue')
            
            def create_bucket():
                region = self.config.tool_config.get('AWS_REGION', 'us-east-1')
                
                # Create bucket with appropriate configuration
                if region == 'us-east-1':
                    # us-east-1 doesn't need LocationConstraint
                    self.s3_client.create_bucket(Bucket=self.s3_bucket)
                else:
                    self.s3_client.create_bucket(
                        Bucket=self.s3_bucket,
                        CreateBucketConfiguration={'LocationConstraint': region}
                    )
                
                # Set bucket versioning
                self.s3_client.put_bucket_versioning(
                    Bucket=self.s3_bucket,
                    VersioningConfiguration={'Status': 'Enabled'}
                )
                
                # Set bucket encryption
                self.s3_client.put_bucket_encryption(
                    Bucket=self.s3_bucket,
                    ServerSideEncryptionConfiguration={
                        'Rules': [
                            {
                                'ApplyServerSideEncryptionByDefault': {
                                    'SSEAlgorithm': 'AES256'
                                }
                            }
                        ]
                    }
                )
                
                log(f"✅ S3 bucket created: {self.s3_bucket}", 'green')
            
            await asyncio.get_event_loop().run_in_executor(None, create_bucket)
        else:
            log(f"✅ S3 bucket exists: {self.s3_bucket}", 'green')
    
    async def _create_thirdparty_layer(self) -> str:
        """Create new thirdparty layer version"""
        zfnid = str(uuid4())
        zfn = Path('./') / f'{zfnid}.zip'
        
        try:
            create_zip_from_requirements_txt(
                Path(self.config.tool_config.get('LAYER_PATH', './layers')) / 'thirdparty' / 'requirements.txt',
                zfn
            )
            
            def publish_layer():
                with open(zfn, 'rb') as f:
                    return retry_with_backoff(lambda: self.lambda_client.publish_layer_version(
                        LayerName=self.thirdparty_layer_name,
                        Content={'ZipFile': f.read()},
                        CompatibleRuntimes=self.config.tool_config.get(
                            'LAYER_COMPATIBLE_RUNTIMES', 'python3.11'
                        ).split(','),
                        CompatibleArchitectures=[self._get_layer_architecture()]
                    ))
            
            response = await asyncio.get_event_loop().run_in_executor(None, publish_layer)
            log("✅ Thirdparty layer created successfully", 'green')
            return response['LayerVersionArn']
        finally:
            delete_local_path(zfn)
    
    async def build(self) -> List[str]:
        """Build all layers and return ARNs"""
        stopwatch("Layer building started")
        
        log_header("LAYER BUILDING")
        log_step("1", "Building Lambda layers with parallel processing")
        
        # Get existing layers
        existing_versions, existing_arns = await self._get_existing_layers()
        
        # Build layers in parallel
        log_progress("Building layers in parallel...")
        tasks = [
            self._check_shared_layer(existing_versions, existing_arns),
            self._check_thirdparty_layer(existing_versions, existing_arns)
        ]
        
        shared_arn, thirdparty_arn = await asyncio.gather(*tasks)
        
        # Build final layer configuration
        final_layers = [
            'arn:aws:lambda:eu-west-3:336392948345:layer:AWSSDKPandas-Python313:3',  # pandas
            thirdparty_arn,  # thirdparty layer
            shared_arn,  # shared layer
            f"arn:aws:lambda:eu-west-3:{self.config.tool_config.get('AWS_ACCOUNT_ID')}:layer:pydantic-layer-python313:1"  # pydantic
        ]
        
        log_success(f"Layer configuration complete: {len(final_layers)} layers")
        log_detail("Layer ARNs:")
        for i, arn in enumerate(final_layers, 1):
            log_detail(f"  {i}. {arn}")
        
        stopwatch("Layer building completed")
        
        return final_layers
