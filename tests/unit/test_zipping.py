"""
Unit tests for autoklug zipping utilities
"""
import pytest
import tempfile
import os
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from autoklug.core.utils.zipping import (
    create_zip_from_directory,
    compute_sha256,
    compare_function_code,
    compare_layer_code,
    create_function_zip,
    create_layer_zip,
    delete_local_path,
    add_file
)


class TestZippingUtilities:
    """Test cases for zipping utilities"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_dir = Path(self.temp_dir) / "test_function"
        self.test_dir.mkdir()
        
        # Create test files
        (self.test_dir / "main.py").write_text("def lambda_handler(event, context): return 'test'")
        (self.test_dir / "utils.py").write_text("def helper(): return 'helper'")
        (self.test_dir / "__pycache__").mkdir()
        (self.test_dir / "__pycache__" / "main.pyc").write_text("compiled")
        
    def teardown_method(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_zip_from_directory(self):
        """Test creating zip from directory"""
        zip_path = Path(self.temp_dir) / "test.zip"
        sha = create_zip_from_directory(str(self.test_dir), str(zip_path))
        
        assert zip_path.exists()
        assert isinstance(sha, str)
        assert len(sha) > 0
        
        # Verify zip contents
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "main.py" in files
            assert "utils.py" in files
            assert "__pycache__/main.pyc" not in files  # Should be excluded
    
    def test_create_zip_with_function_wrapper(self):
        """Test creating zip with Lambda function wrapper"""
        zip_path = Path(self.temp_dir) / "test_function.zip"
        router_data = [{"method": "GET", "urlRuleAG": "/test", "filePath": "main.py"}]
        
        sha = create_zip_from_directory(
            str(self.test_dir), 
            str(zip_path),
            function_name="test-function",
            short_name="test",
            router_data=router_data
        )
        
        assert zip_path.exists()
        
        # Verify lambda_function.py wrapper was created
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "lambda_function.py" in files
            
            # Check wrapper content
            wrapper_content = zf.read("lambda_function.py").decode()
            assert "lambda_handler" in wrapper_content
            assert "importlib" in wrapper_content
    
    def test_create_zip_with_health_endpoint(self):
        """Test creating zip with health endpoint"""
        health_dir = Path(self.temp_dir) / "health"
        health_dir.mkdir()
        
        zip_path = Path(self.temp_dir) / "health.zip"
        sha = create_zip_from_directory(
            str(health_dir), 
            str(zip_path),
            short_name="health"
        )
        
        assert zip_path.exists()
        
        # Verify health endpoint was created
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "health/get.py" in files
            
            # Check health endpoint content
            health_content = zf.read("health/get.py").decode()
            assert "This endpoint is responding as it should!" in health_content
    
    def test_compute_sha256(self):
        """Test SHA256 computation"""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")
        
        sha = compute_sha256(str(test_file))
        
        assert isinstance(sha, str)
        assert len(sha) > 0
        # SHA should be consistent
        sha2 = compute_sha256(str(test_file))
        assert sha == sha2
    
    def test_compare_function_code_same(self):
        """Test comparing function code when it's the same"""
        zip_path = Path(self.temp_dir) / "test.zip"
        sha = create_zip_from_directory(str(self.test_dir), str(zip_path))
        
        # Mock cloud SHA to be the same
        needs_update = compare_function_code("test-function", str(self.test_dir), sha)
        
        assert not needs_update
    
    def test_compare_function_code_different(self):
        """Test comparing function code when it's different"""
        zip_path = Path(self.temp_dir) / "test.zip"
        sha = create_zip_from_directory(str(self.test_dir), str(zip_path))
        
        # Modify local file
        (self.test_dir / "main.py").write_text("def lambda_handler(event, context): return 'modified'")
        
        # Compare with old SHA
        needs_update = compare_function_code("test-function", str(self.test_dir), sha)
        
        assert needs_update
    
    def test_create_function_zip(self):
        """Test creating function zip content"""
        zip_content = create_function_zip("test-function", str(self.test_dir))
        
        assert isinstance(zip_content, bytes)
        assert len(zip_content) > 0
        
        # Verify it's a valid zip
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(zip_content)
            tmp.flush()
            
            with zipfile.ZipFile(tmp.name, 'r') as zf:
                files = zf.namelist()
                assert "main.py" in files
    
    def test_create_layer_zip(self):
        """Test creating layer zip content"""
        zip_content = create_layer_zip(str(self.test_dir))
        
        assert isinstance(zip_content, bytes)
        assert len(zip_content) > 0
        
        # Verify it's a valid zip
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(zip_content)
            tmp.flush()
            
            with zipfile.ZipFile(tmp.name, 'r') as zf:
                files = zf.namelist()
                assert "main.py" in files
    
    def test_delete_local_path(self):
        """Test deleting local paths"""
        test_file = Path(self.temp_dir) / "test_file.txt"
        test_file.write_text("test")
        
        test_dir = Path(self.temp_dir) / "test_dir"
        test_dir.mkdir()
        (test_dir / "nested.txt").write_text("nested")
        
        # Test file deletion
        assert test_file.exists()
        result = delete_local_path(str(test_file))
        assert result
        assert not test_file.exists()
        
        # Test directory deletion
        assert test_dir.exists()
        result = delete_local_path(str(test_dir))
        assert result
        assert not test_dir.exists()
    
    def test_add_file_permissions(self):
        """Test that add_file preserves permissions"""
        test_file = Path(self.temp_dir) / "executable.py"
        test_file.write_text("#!/usr/bin/env python\nprint('hello')")
        test_file.chmod(0o755)  # Make executable
        
        zip_path = Path(self.temp_dir) / "permissions_test.zip"
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            add_file(zf, str(test_file), "executable.py")
        
        # Verify permissions were preserved
        with zipfile.ZipFile(zip_path, 'r') as zf:
            info = zf.getinfo("executable.py")
            # Check that executable permission is preserved
            assert info.external_attr & 0o111  # Executable bit
    
    def test_file_exclusions(self):
        """Test that unwanted files are excluded"""
        # Create various unwanted files
        (self.test_dir / "main.pyc").write_text("compiled")
        (self.test_dir / "main-darwin.so").write_text("binary")
        (self.test_dir / ".DS_Store").write_text("macos")
        (self.test_dir / "_virtualenv.py").write_text("venv")
        
        zip_path = Path(self.temp_dir) / "exclusions_test.zip"
        create_zip_from_directory(str(self.test_dir), str(zip_path))
        
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            
            # These files should be excluded
            assert "main.pyc" not in files
            assert "main-darwin.so" not in files
            assert ".DS_Store" not in files
            assert "_virtualenv.py" not in files
            
            # These files should be included
            assert "main.py" in files
            assert "utils.py" in files
