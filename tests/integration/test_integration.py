"""
Integration tests for autoklug
"""
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from autoklug.core.builders import BlazingFastBuilder
from autoklug.core.utils import ConfigManager


class TestIntegration:
    """Integration tests for autoklug"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir) / "test_project"
        self.project_dir.mkdir()
        
        # Create project structure
        (self.project_dir / "api").mkdir()
        (self.project_dir / "layers").mkdir()
        (self.project_dir / "layers" / "shared").mkdir()
        (self.project_dir / "layers" / "thirdparty").mkdir()
        
        # Create test API function
        api_dir = self.project_dir / "api" / "health"
        api_dir.mkdir()
        (api_dir / "get.py").write_text("""
def lambda_handler(event, context):
    return {
        'statusCode': 200,
        'body': '{"message": "healthy"}'
    }
""")
        
        # Create test layer files
        (self.project_dir / "layers" / "shared" / "utils.py").write_text("""
def helper_function():
    return "helper"
""")
        
        (self.project_dir / "layers" / "thirdparty" / "requirements.txt").write_text("""
requests==2.31.0
boto3==1.34.0
""")
        
        # Create test configuration files
        (self.project_dir / ".tool").write_text("""
AWS_PROFILE_BUILD=default
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
APP_NAME=test-app
INFRA=dev
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
API_PATH=./api
""")
        
        (self.project_dir / ".env").write_text("""
DATABASE_URL=postgresql://test:test@localhost:5432/test_db
DEBUG_MODE=true
""")
    
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('autoklug.core.builders.AsyncLayerBuilder')
    @patch('autoklug.core.builders.AsyncFunctionBuilder')
    @patch('autoklug.core.builders.AsyncApiBuilder')
    @patch('autoklug.core.builders.ConfigPermissionsManager')
    def test_builder_initialization(self, mock_config_mgr, mock_api, mock_func, mock_layer):
        """Test that BlazingFastBuilder initializes correctly"""
        with patch.dict(os.environ, {}, clear=True):
            os.chdir(self.project_dir)
            
            builder = BlazingFastBuilder()
            
            assert builder.tool_path is not None
            assert builder.env_path is not None
            assert builder.infra == 'dev'
            assert builder.config is not None
    
    @patch('autoklug.core.builders.AsyncLayerBuilder')
    @patch('autoklug.core.builders.AsyncFunctionBuilder')
    @patch('autoklug.core.builders.AsyncApiBuilder')
    @patch('autoklug.core.builders.ConfigPermissionsManager')
    def test_builder_with_explicit_paths(self, mock_config_mgr, mock_api, mock_func, mock_layer):
        """Test BlazingFastBuilder with explicit tool and env paths"""
        tool_path = str(self.project_dir / ".tool")
        env_path = str(self.project_dir / ".env")
        
        builder = BlazingFastBuilder(tool_path=tool_path, env_path=env_path)
        
        assert builder.tool_path == tool_path
        assert builder.env_path == env_path
        assert builder.infra == 'dev'  # Default when explicitly provided
    
    def test_config_manager_loading(self):
        """Test ConfigManager loads configuration correctly"""
        tool_path = str(self.project_dir / ".tool")
        env_path = str(self.project_dir / ".env")
        
        config = ConfigManager(tool_path, env_path)
        
        assert config.tool_config['APP_NAME'] == 'test-app'
        assert config.tool_config['AWS_REGION'] == 'us-east-1'
        assert config.tool_config['AWS_ACCOUNT_ID'] == '123456789012'
        assert config.env_config['DATABASE_URL'] == 'postgresql://test:test@localhost:5432/test_db'
        assert config.env_config['DEBUG_MODE'] == 'true'
    
    def test_project_detection(self):
        """Test project context detection"""
        from autoklug.utils import detect_project_context, find_best_config_files
        
        with patch.dict(os.environ, {}, clear=True):
            os.chdir(self.project_dir)
            
            context = detect_project_context()
            tool_file, env_file = find_best_config_files(context)
            
            assert context['current_dir'] == str(self.project_dir)
            assert context['infra'] == 'dev'
            assert context['is_public'] == False
            assert './api' in context['api_paths']
            assert './layers' in context['layer_paths']
            assert tool_file == '.tool'
            assert env_file == '.env'
    
    @patch('autoklug.core.builders.AsyncLayerBuilder')
    def test_build_layers_only(self, mock_layer_builder):
        """Test building only layers"""
        mock_instance = MagicMock()
        mock_instance.build.return_value = ['layer-arn-1', 'layer-arn-2']
        mock_layer_builder.return_value = mock_instance
        
        builder = BlazingFastBuilder(
            tool_path=str(self.project_dir / ".tool"),
            env_path=str(self.project_dir / ".env")
        )
        
        import asyncio
        result = asyncio.run(builder.build_layers_only())
        
        assert result is True
        mock_layer_builder.assert_called_once()
        mock_instance.build.assert_called_once()
    
    @patch('autoklug.core.builders.AsyncFunctionBuilder')
    @patch('autoklug.core.builders.AsyncLayerBuilder')
    def test_build_functions_only(self, mock_layer_builder, mock_func_builder):
        """Test building only functions"""
        mock_layer_instance = MagicMock()
        mock_layer_instance.get_existing_layers.return_value = ['layer-arn-1']
        mock_layer_builder.return_value = mock_layer_instance
        
        mock_func_instance = MagicMock()
        mock_func_instance.build.return_value = None
        mock_func_builder.return_value = mock_func_instance
        
        builder = BlazingFastBuilder(
            tool_path=str(self.project_dir / ".tool"),
            env_path=str(self.project_dir / ".env")
        )
        
        import asyncio
        result = asyncio.run(builder.build_functions_only())
        
        assert result is True
        mock_layer_builder.assert_called_once()
        mock_func_builder.assert_called_once()
    
    @patch('autoklug.core.builders.AsyncApiBuilder')
    def test_build_api_only(self, mock_api_builder):
        """Test building only API Gateway"""
        mock_instance = MagicMock()
        mock_instance.build.return_value = None
        mock_api_builder.return_value = mock_instance
        
        builder = BlazingFastBuilder(
            tool_path=str(self.project_dir / ".tool"),
            env_path=str(self.project_dir / ".env")
        )
        
        import asyncio
        result = asyncio.run(builder.build_api_only())
        
        assert result is True
        mock_api_builder.assert_called_once()
        mock_instance.build.assert_called_once()
    
    def test_public_api_detection(self):
        """Test public API detection"""
        # Create public API structure
        (self.project_dir / "api_public").mkdir()
        (self.project_dir / "api_public" / "catalog").mkdir()
        (self.project_dir / "api_public" / "catalog" / "get.py").write_text("""
def lambda_handler(event, context):
    return {'statusCode': 200, 'body': '{"catalog": []}'}
""")
        
        from autoklug.utils import detect_project_context
        
        with patch.dict(os.environ, {}, clear=True):
            os.chdir(self.project_dir)
            
            context = detect_project_context()
            
            assert context['is_public'] == True
            assert './api_public' in context['api_paths']
    
    def test_environment_specific_configs(self):
        """Test environment-specific configuration detection"""
        # Create environment-specific files
        (self.project_dir / ".tool.dev").write_text("""
AWS_PROFILE_BUILD=dev-profile
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
APP_NAME=test-app-dev
INFRA=dev
LAMBDA_RUNTIME=python3.11
""")
        
        (self.project_dir / ".tool.prod").write_text("""
AWS_PROFILE_BUILD=prod-profile
AWS_REGION=us-west-2
AWS_ACCOUNT_ID=123456789012
APP_NAME=test-app-prod
INFRA=prod
LAMBDA_RUNTIME=python3.11
""")
        
        from autoklug.utils import detect_project_context, find_best_config_files
        
        with patch.dict(os.environ, {}, clear=True):
            os.chdir(self.project_dir)
            
            context = detect_project_context()
            tool_file, env_file = find_best_config_files(context)
            
            # Should prefer generic files over environment-specific
            assert tool_file == '.tool'
            assert env_file == '.env'
    
    def test_missing_config_files(self):
        """Test handling of missing configuration files"""
        # Remove config files
        (self.project_dir / ".tool").unlink()
        (self.project_dir / ".env").unlink()
        
        from autoklug.utils import detect_project_context, find_best_config_files
        
        with patch.dict(os.environ, {}, clear=True):
            os.chdir(self.project_dir)
            
            context = detect_project_context()
            
            # Should still detect project structure
            assert './api' in context['api_paths']
            assert './layers' in context['layer_paths']
            
            # Should handle missing files gracefully
            tool_file, env_file = find_best_config_files(context)
            assert tool_file is None or tool_file == ''
            assert env_file is None or env_file == ''
