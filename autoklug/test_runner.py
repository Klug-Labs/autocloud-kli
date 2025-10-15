#!/usr/bin/env python3
"""
Test runner for autoklug
"""
import sys
import os
import subprocess
from pathlib import Path

def run_tests():
    """Run all tests"""
    print("🧪 Running autoklug tests...")
    
    # Add the autoklug directory to Python path
    autoklug_dir = Path(__file__).parent
    sys.path.insert(0, str(autoklug_dir))
    
    # Run pytest
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/", 
            "-v", 
            "--cov=autoklug", 
            "--cov-report=term-missing",
            "--cov-report=html"
        ], cwd=autoklug_dir)
        
        if result.returncode == 0:
            print("✅ All tests passed!")
        else:
            print("❌ Some tests failed!")
            sys.exit(1)
            
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest pytest-cov")
        sys.exit(1)

def run_unit_tests():
    """Run unit tests only"""
    print("🧪 Running unit tests...")
    
    autoklug_dir = Path(__file__).parent
    sys.path.insert(0, str(autoklug_dir))
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/unit/", 
            "-v"
        ], cwd=autoklug_dir)
        
        if result.returncode == 0:
            print("✅ Unit tests passed!")
        else:
            print("❌ Unit tests failed!")
            sys.exit(1)
            
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest")
        sys.exit(1)

def run_integration_tests():
    """Run integration tests only"""
    print("🧪 Running integration tests...")
    
    autoklug_dir = Path(__file__).parent
    sys.path.insert(0, str(autoklug_dir))
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/integration/", 
            "-v"
        ], cwd=autoklug_dir)
        
        if result.returncode == 0:
            print("✅ Integration tests passed!")
        else:
            print("❌ Integration tests failed!")
            sys.exit(1)
            
    except FileNotFoundError:
        print("❌ pytest not found. Install with: pip install pytest")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if test_type == "unit":
            run_unit_tests()
        elif test_type == "integration":
            run_integration_tests()
        else:
            print("Usage: python test_runner.py [unit|integration]")
            sys.exit(1)
    else:
        run_tests()
