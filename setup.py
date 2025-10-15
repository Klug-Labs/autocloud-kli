"""
Autoklug - Blazing Fast AWS Lambda Build System

A high-performance, parallel AWS Lambda deployment system that's blazing fast!
Works globally in any project with automatic context detection.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

# Read version from __init__.py
def get_version():
    init_file = this_directory / "autoklug" / "__init__.py"
    with open(init_file) as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "2.0.0"

setup(
    name="autoklug",
    version=get_version(),
    author="Luís Miguel Sousa",
    author_email="luis@kluglabs.com",
    description="Blazing Fast AWS Lambda Build System with Global Project Detection",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/lewisklug/autoklug",
    project_urls={
        "Bug Reports": "https://github.com/lewisklug/autoklug/issues",
        "Source": "https://github.com/lewisklug/autoklug",
        "Documentation": "https://github.com/lewisklug/autoklug#readme",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: Console",
    ],
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "boto3>=1.26.0",
        "python-dotenv>=0.19.0",
        "termcolor>=1.1.0",
        "GitPython>=3.1.0",
        "flask>=2.0.0",
        "flask-cors>=3.0.0",
        "requests>=2.25.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
        "docs": [
            "mkdocs>=1.4.0",
            "mkdocs-material>=8.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "autoklug=autoklug.main:cli",
        ],
    },
    keywords=[
        "aws", "lambda", "serverless", "build", "deployment", 
        "api-gateway", "infrastructure", "devops", "ci-cd"
    ],
    include_package_data=True,
    package_data={
        "autoklug": ["*.md", "*.txt", "*.yml", "*.yaml"],
    },
    zip_safe=False,
)
