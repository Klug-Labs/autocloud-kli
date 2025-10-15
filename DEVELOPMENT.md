# Autoklug Development Guide

## 🚀 Quick Start

### **Installation**
```bash
# Clone the repository
git clone https://github.com/lewisklug/autoklug.git
cd autoklug

# Install in development mode
pip install -e .

# Install development dependencies
pip install -e .[dev]
```

### **Testing**
```bash
# Run tests
pytest

# Run with coverage
pytest --cov=autoklug

# Run specific test
pytest tests/test_main.py
```

### **Code Quality**
```bash
# Format code
black autoklug/

# Lint code
flake8 autoklug/

# Type checking
mypy autoklug/
```

## 📦 Building and Publishing

### **Build Package**
```bash
# Build source distribution
python -m build

# Build wheel
python -m build --wheel
```

### **Publish to PyPI**
```bash
# Install build tools
pip install build twine

# Build package
python -m build

# Upload to PyPI
twine upload dist/*
```

### **Test PyPI**
```bash
# Upload to test PyPI first
twine upload --repository testpypi dist/*

# Install from test PyPI
pip install --index-url https://test.pypi.org/simple/ autoklug
```

## 🧪 Testing the Global Command

### **Local Testing**
```bash
# Install locally
pip install -e .

# Test the global command
autoklug --help
autoklug detect
autoklug build --dry-run
```

### **Virtual Environment Testing**
```bash
# Create clean environment
python -m venv test_env
source test_env/bin/activate  # On Windows: test_env\Scripts\activate

# Install autoklug
pip install autoklug

# Test commands
autoklug --version
autoklug detect
```

## 🔧 Configuration

### **Development Configuration**
Create a `.tool.dev` file for development:
```bash
AWS_PROFILE_BUILD=default
AWS_REGION=eu-west-3
AWS_ACCOUNT_ID=123456789012
APP_NAME=autoklug-dev
INFRA=dev
LAMBDA_RUNTIME=python3.11
LAYER_PATH=./layers
API_PATH=./api
```

### **Test Environment**
Create a `.env.dev` file:
```bash
DATABASE_URL=postgresql://test:test@localhost:5432/test_db
DEBUG_MODE=true
API_BASE_URL=https://api.test.com
```

## 📁 Project Structure

```
autoklug/
├── __init__.py          # Package initialization
├── main.py             # CLI entry point
├── utils.py            # Core utilities and logging
├── layers.py           # Layer building logic
├── functions.py        # Function building logic
├── api.py              # API Gateway building logic
├── config_permissions.py # Post-build configuration
├── examples.py         # Configuration examples
├── demo_logging.py     # Logging demo
├── test_global.py      # Global functionality test
└── requirements.txt    # Dependencies
```

## 🎯 Entry Points

The package uses setuptools entry points to create the global `autoklug` command:

```python
# In setup.py/pyproject.toml
entry_points={
    "console_scripts": [
        "autoklug=autoklug.main:cli",
    ],
}
```

This creates a global command that can be run from anywhere:
```bash
autoklug build
autoklug detect
autoklug --help
```

## 🔍 Debugging

### **Verbose Mode**
```bash
autoklug build --verbose
```

### **Dry Run**
```bash
autoklug build --dry-run
```

### **Configuration Check**
```bash
autoklug config
autoklug detect
```

## 📚 Documentation

### **Generate Documentation**
```bash
# Install docs dependencies
pip install -e .[docs]

# Build documentation
mkdocs build

# Serve documentation locally
mkdocs serve
```

### **Update README**
The main README.md is used for PyPI package description. Keep it updated with:
- Installation instructions
- Usage examples
- Feature descriptions
- Configuration examples

## 🚀 Release Process

### **Version Bumping**
1. Update version in `autoklug/__init__.py`
2. Update version in `setup.py` and `pyproject.toml`
3. Update changelog
4. Commit changes
5. Create git tag
6. Push to GitHub
7. Build and upload to PyPI

### **Automated Releases**
Consider using GitHub Actions for automated releases:
```yaml
name: Publish to PyPI
on:
  release:
    types: [published]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.8
    - name: Install dependencies
      run: |
        pip install build twine
    - name: Build package
      run: python -m build
    - name: Publish to PyPI
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: twine upload dist/*
```

## 🎉 Success Criteria

After successful PyPI deployment, users should be able to:

1. **Install globally**: `pip install autoklug`
2. **Use anywhere**: `autoklug build` from any directory
3. **Auto-detect projects**: Works without configuration files
4. **See help**: `autoklug --help` shows all commands
5. **Detect context**: `autoklug detect` shows project analysis

The package is now globally available and ready for use! 🚀
