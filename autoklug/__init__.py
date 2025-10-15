"""
Autoklug - Blazing Fast AWS Lambda Build System

A high-performance, parallel AWS Lambda deployment system that's blazing fast!
Works globally in any project with automatic context detection.
"""

__version__ = "2.0.0"
__author__ = "Luís Miguel Sousa"
__email__ = "luis@kluglabs.com"

from .core.cli.commands import cli

__all__ = ['cli']