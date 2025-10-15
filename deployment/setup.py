"""
PyPI deployment configuration for autoklug
"""
from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    with open("README.md", "r", encoding="utf-8") as fh:
        return fh.read()

# Read requirements
def read_requirements():
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        return [line.strip() for line in fh if line.strip() and not line.startswith("#")]

# Get version from __init__.py
def get_version():
    with open("autoklug/__init__.py", "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.1.0"

setup(
    name="autoklug",
    version=get_version(),
    author="Lewis Klug",
    author_email="luis@kluglabs.com",
    description="Blazing fast AWS Lambda build system with automatic context detection",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="https://github.com/lewisklug/autoklug",
    project_urls={
        "Bug Reports": "https://github.com/lewisklug/autoklug/issues",
        "Source": "https://github.com/lewisklug/autoklug",
        "Documentation": "https://github.com/lewisklug/autoklug#readme",
    },
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Topic :: System :: Systems Administration",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=read_requirements(),
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.0.0",
            "mkdocstrings>=0.22.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "autoklug=autoklug.main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "autoklug": [
            "templates/*.py",
            "templates/*.txt",
            "templates/*.md",
        ],
    },
    keywords=[
        "aws",
        "lambda",
        "serverless",
        "deployment",
        "build",
        "automation",
        "devops",
        "ci-cd",
    ],
    zip_safe=False,
)
