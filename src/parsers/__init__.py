"""
Parsers for various project configuration files.

This module provides parsers for extracting dependencies and metadata
from different project configuration formats.
"""

from .pom_parser import parse_pom_xml
from .pyproject_parser import parse_pyproject_toml

__all__ = ['parse_pom_xml', 'parse_pyproject_toml']
