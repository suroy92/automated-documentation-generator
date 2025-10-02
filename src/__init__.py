# src/__init__.py
"""
Automated Documentation Generator

A language-agnostic tool for generating project documentation using AI.
"""

__version__ = "1.0.0"
__author__ = "Supratik Roy"

# -----------------------------------

# src/analyzers/__init__.py
"""
Language-specific analyzers for parsing source code.
"""

from .analyzers.base_analyzer import BaseAnalyzer
from .analyzers.py_analyzer import PythonAnalyzer
from .analyzers.js_analyzer import JavaScriptAnalyzer
from .analyzers.java_analyzer import JavaAnalyzer

__all__ = ['BaseAnalyzer', 'PythonAnalyzer', 'JavaScriptAnalyzer', 'JavaAnalyzer']

# -----------------------------------

# tests/__init__.py
"""
Test suite for the automated documentation generator.
"""

# This file can be empty but makes tests/ a package