# Autoklug - Blazing Fast AWS Lambda Build System

[![PyPI version](https://badge.fury.io/py/autoklug.svg)](https://badge.fury.io/py/autoklug)
[![Python Support](https://img.shields.io/pypi/pyversions/autoklug.svg)](https://pypi.org/project/autoklug/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **blazing fast**, high-performance AWS Lambda deployment system that works globally in any project with automatic context detection. Makes complex AWS infrastructure "stupid simple" with minimal configuration.

## 🚀 Core Principles

- **Unified Developer Experience**: One CLI, consistent interface
- **Build Locally, Deploy Globally**: Local development with seamless AWS deployment  
- **Stupid Simple**: Complex AWS infrastructure made accessible with minimal configuration
- **Production Ready**: Enterprise-grade features with developer-friendly interfaces

```bash
# Autoklug Commands
autoklug init          # Initialize project
autoklug run           # Local development server
autoklug deploy        # Deploy to AWS Lambda
autoklug deploy --validate  # Deploy with enhanced validation
```

## 🚀 Features

- ⚡ **Parallel Processing**: Layers, functions, and APIs built simultaneously
- 🔄 **Smart Comparison**: Only updates what's changed using SHA256 hashing
- 📦 **S3 Requirements Checking**: Compares local requirements.txt with S3
- 🌐 **Public API Detection**: Automatically configures public APIs without authorizers
- 🚦 **Rate Limiting**: Built-in throttling for public APIs
- 🌍 **Global Usage**: Works in any project with auto-detection
- 🎨 **Beautiful CLI**: Click-based CLI with progress bars and colored output
- 🔧 **Zero Configuration**: Just run `autoklug build` from any project

## 📦 Installation

```bash
pip install autoklug
```

## 🎯 Quick Start

### **Zero Configuration Usage**
```bash
# Just run from any project directory - it detects everything!
autoklug build
```

### **With Explicit Configuration**
```bash
# Override auto-detection if needed
autoklug build --tool .tool.dev --env .env.dev
```

### **Individual Components**
```bash
# Build only layers
autoklug layers

# Build only functions  
autoklug functions

# Build only API Gateway
autoklug api
```

### **Local Development**
```bash
# Start local development server
autoklug run

# With custom port
autoklug run --port 8080

# With authorizer simulation
autoklug run --use-authorizer

# With custom configuration
autoklug run --tool .tool.dev --env .env.dev
```

### **Project Analysis**
```bash
# See what the system detects
autoklug detect

# Show configuration
autoklug config
```

## 🔍 Project Context Detection

Autoklug automatically detects:

### **Configuration Files**
- `.tool`, `.tool.dev`, `.tool.prod`, `.tool.public`, etc.
- `.env`, `.env.dev`, `.env.prod`, etc.
- **Preference**: Uses `.tool` and `.env` over environment-specific versions

### **Project Structure**
- **API Directories**: `api/`, `api_public/`, `src/api/`, `functions/`, `lambda/`
- **Layer Directories**: `layers/`, `lambda_layers/`, `src/layers/`

### **Infrastructure Detection**
- **From File Names**: Detects `prod`, `staging`, `dev` from `.tool.*` files
- **Default**: Uses `dev` if not detected
- **Public APIs**: Detects from `api_public/` or `.tool.public.*` files

## 📊 Example Detection Output

```bash
$ autoklug detect

🔍 Project Context Detection
========================================
Current directory: /path/to/my-project
Detected infrastructure: prod
Public API detected: True

📁 Configuration Files:
Tool files found: ['.tool.public.prod', '.tool.dev', '.tool']
Env files found: ['.env.prod', '.env.dev', '.env']
Selected tool file: .tool.public.prod
Selected env file: .env.prod

📂 Project Structure:
API paths found: ['./api', './api_public']
Layer paths found: ['./layers']
```

## 🎨 CLI Commands

| Command | Description | Auto-Detection |
|---------|-------------|----------------|
| `autoklug build` | 🏗️ Build complete infrastructure | ✅ |
| `autoklug layers` | 📦 Build only Lambda layers | ✅ |
| `autoklug functions` | ⚡ Build only Lambda functions | ✅ |
| `autoklug api` | 🌐 Build only API Gateway | ✅ |
| `autoklug run` | 🚀 Start local development server | ✅ |
| `autoklug config` | ⚙️ Show configuration info | ✅ |
| `autoklug detect` | 🔍 Show project detection | ✅ |
| `autoklug demo` | 🎨 Run logging demo | ❌ |

## 🔧 Project Structure Support

Autoklug works with any of these common project structures:

### **Standard Structure**
```
my-project/
├── .tool
├── .env
├── api/
│   ├── health/
│   │   └── get.py
│   └── users/
│       ├── get.py
│       └── post.py
└── layers/
    ├── shared/
    └── thirdparty/
        └── requirements.txt
```

### **Public API Structure**
```
my-project/
├── .tool.public
├── .env
├── api_public/
│   ├── health/
│   └── catalog/
└── layers/
```

### **Environment-Specific Structure**
```
my-project/
├── .tool.dev
├── .tool.prod
├── .env.dev
├── .env.prod
├── api/
└── layers/
```

## ⚙️ Configuration Files

### **`.tool` File Example**
```bash
# AWS Configuration
AWS_PROFILE_BUILD=default
AWS_REGION=eu-west-3
AWS_ACCOUNT_ID=123456789012

# Application Configuration
APP_NAME=my-app
PUBLIC_APP_NAME=my-app-public
INFRA=dev

# Lambda Configuration
LAMBDA_RUNTIME=python3.11
LAMBDA_ROLE=arn:aws:iam::123456789012:role/lambda-execution-role

# Layer Configuration
LAYER_PATH=./layers
LAYER_COMPATIBLE_RUNTIMES=python3.11
LAYER_ARCHITECTURE=x86_64

# API Configuration
API_PATH=./api
AUTHORIZER_FUNCTION_NAME=api-my-app-dev-authorizer

# S3 Configuration for requirements.txt checking (auto-generated from APP_NAME)
# Bucket name will be: <APP_NAME>-requirements-txt-bucket
# Example: my-app-requirements-txt-bucket
```

### **`.env` File Example**
```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/my_app_dev

# External Services
UPLOADS_CDN=https://cdn.example.com
API_BASE_URL=https://api.example.com

# Feature Flags
ENABLE_FEATURE_X=true
DEBUG_MODE=true
```

## 🚀 Performance Benefits

- **Parallel Processing**: Up to 10 concurrent Lambda updates
- **Smart Comparison**: SHA256 hashing prevents unnecessary rebuilds
- **S3 Integration**: Requirements.txt comparison without local rebuilds
- **Boto3 Optimization**: Adaptive retries and connection pooling
- **Async/Await**: Non-blocking I/O operations

## 🎯 Use Cases

### **Development**
- **Local Development**: Quick builds during development
- **Feature Branches**: Deploy to dev environment
- **Testing**: Validate changes before production

### **CI/CD**
- **GitHub Actions**: Automated deployments
- **Jenkins**: Build pipeline integration
- **GitLab CI**: Continuous deployment

### **Production**
- **Blue-Green Deployments**: Zero-downtime updates
- **Rollback Support**: Quick reversion capabilities
- **Monitoring**: Health checks and validation

## 🔧 Advanced Usage

### **Force Layer Updates**
```bash
autoklug build --force-update-layers
```

### **Dry Run Mode**
```bash
autoklug build --dry-run
```

### **Verbose Logging**
```bash
autoklug build --verbose
```

### **Custom Configuration**
```bash
autoklug build --tool .tool.prod --env .env.prod
```

## 🛠️ Development

### **Install Development Dependencies**
```bash
pip install autoklug[dev]
```

### **Run Tests**
```bash
pytest
```

### **Code Formatting**
```bash
black autoklug/
```

### **Type Checking**
```bash
mypy autoklug/
```

## 📚 Documentation

- [Full Documentation](https://github.com/lewisklug/autoklug#readme)
- [API Reference](https://github.com/lewisklug/autoklug/blob/main/docs/api.md)
- [Configuration Guide](https://github.com/lewisklug/autoklug/blob/main/docs/configuration.md)
- [Examples](https://github.com/lewisklug/autoklug/blob/main/docs/examples.md)

## 🤝 Contributing

Contributions are welcome! Please see our [Contributing Guide](https://github.com/lewisklug/autoklug/blob/main/CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Click](https://click.palletsprojects.com/) for CLI
- Uses [Boto3](https://boto3.amazonaws.com/) for AWS integration
- Inspired by modern DevOps practices

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/lewisklug/autoklug/issues)
- **Discussions**: [GitHub Discussions](https://github.com/lewisklug/autoklug/discussions)
- **Email**: luis@kluglabs.com

---

**Made with ❤️ by Luís Miguel Sousa**

*Blazing fast AWS Lambda deployments, globally!* 🚀