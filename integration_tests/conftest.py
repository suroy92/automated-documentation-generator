"""
Pytest configuration and fixtures for integration tests.

This module provides shared fixtures and utilities for testing the
documentation generator against real-world sample projects.
"""

import pytest
from pathlib import Path
from typing import Dict, Any
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.project_analyzer import ProjectAnalyzer
from src.repo_facts import RepoFacts, ProjectType
from src.fact_extractor import FactExtractor
from src.fact_normalizer import FactNormalizer
from src.analyzers.py_analyzer import PythonAnalyzer
from src.analyzers.js_analyzer import JavaScriptAnalyzer
from src.analyzers.ts_analyzer import TypeScriptAnalyzer
from src.analyzers.java_analyzer import JavaAnalyzer


# Sample projects directory
SAMPLES_DIR = Path("D:/Workspace/Document_Analyzer_Samples")


@pytest.fixture
def samples_dir():
    """Fixture providing path to sample projects directory."""
    return SAMPLES_DIR


def analyze_project_full(project_path: Path) -> Dict[str, Any]:
    """
    Perform full project analysis including LADOM generation.

    This function replicates the scan_and_analyze logic from main.py
    to generate LADOM data from a project.

    Args:
        project_path: Path to the project to analyze

    Returns:
        LADOM data dictionary with aggregated file analysis
    """
    # Initialize analyzers
    py_analyzer = PythonAnalyzer()
    js_analyzer = JavaScriptAnalyzer()
    ts_analyzer = TypeScriptAnalyzer()
    java_analyzer = JavaAnalyzer()

    # Map file extensions to analyzers
    analyzer_map = {
        '.py': (py_analyzer, 'python'),
        '.js': (js_analyzer, 'javascript'),
        '.ts': (ts_analyzer, 'typescript'),
        '.tsx': (ts_analyzer, 'typescript'),
        '.java': (java_analyzer, 'java'),
    }

    # Aggregate LADOM data
    aggregated_ladom = {
        "project_name": project_path.name,
        "files": []
    }

    # Scan project for files
    for root, dirs, files in os.walk(str(project_path)):
        # Skip common ignore patterns
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['node_modules', '__pycache__', 'venv', '.venv', 'build', 'dist']]

        for file in files:
            file_path = Path(root) / file
            ext = file_path.suffix.lower()

            if ext in analyzer_map:
                analyzer, file_type = analyzer_map[ext]
                try:
                    ladom_data = analyzer.analyze(str(file_path))
                    if ladom_data and ladom_data.get("files"):
                        aggregated_ladom["files"].extend(ladom_data["files"])
                except Exception as e:
                    # Skip files that fail analysis
                    pass

    return aggregated_ladom


def extract_facts(project_path: Path) -> RepoFacts:
    """
    Extract and normalize facts from a project.

    Args:
        project_path: Path to the project to analyze

    Returns:
        Normalized RepoFacts object
    """
    # Analyze project to get LADOM
    ladom_data = analyze_project_full(project_path)

    # Extract facts from LADOM
    extractor = FactExtractor(str(project_path))
    raw_facts = extractor.extract(ladom_data)

    # Normalize facts
    normalizer = FactNormalizer(str(project_path))
    normalized_facts = normalizer.normalize(raw_facts)

    return normalized_facts


@pytest.fixture
def analyze_project():
    """Fixture providing the analyze_project_full function."""
    return analyze_project_full


@pytest.fixture
def get_facts():
    """Fixture providing the extract_facts function."""
    return extract_facts


def assert_project_type(facts: RepoFacts, expected_type: ProjectType, reason: str = ""):
    """
    Assert that project type matches expected type with helpful error message.

    Args:
        facts: RepoFacts object
        expected_type: Expected ProjectType
        reason: Optional reason for the assertion
    """
    actual = facts.project.type
    assert actual == expected_type, (
        f"Project type mismatch{': ' + reason if reason else ''}. "
        f"Expected {expected_type.value}, got {actual.value}"
    )


def assert_primary_language(facts: RepoFacts, expected_language: str, reason: str = ""):
    """
    Assert that primary language matches expected language.

    Args:
        facts: RepoFacts object
        expected_language: Expected language name
        reason: Optional reason for the assertion
    """
    primary = facts.get_primary_language()
    assert primary is not None, f"No primary language detected{': ' + reason if reason else ''}"
    assert primary.name == expected_language, (
        f"Primary language mismatch{': ' + reason if reason else ''}. "
        f"Expected {expected_language}, got {primary.name}"
    )


def assert_has_interface(facts: RepoFacts, interface_type: str, reason: str = ""):
    """
    Assert that project has specified interface type.

    Args:
        facts: RepoFacts object
        interface_type: Expected interface type ("CLI", "Web API", etc.)
        reason: Optional reason for the assertion
    """
    actual = facts.get_interface_type()
    assert actual is not None, f"No interface detected{': ' + reason if reason else ''}"
    assert actual == interface_type, (
        f"Interface type mismatch{': ' + reason if reason else ''}. "
        f"Expected {interface_type}, got {actual}"
    )


def assert_has_dependencies(facts: RepoFacts, dep_type: str = "runtime", min_count: int = 1):
    """
    Assert that project has dependencies.

    Args:
        facts: RepoFacts object
        dep_type: Dependency type (runtime, dev, etc.)
        min_count: Minimum number of dependencies expected
    """
    deps = facts.dependencies.get(dep_type, [])
    assert len(deps) >= min_count, (
        f"Expected at least {min_count} {dep_type} dependencies, "
        f"found {len(deps)}"
    )


def assert_has_entry_points(facts: RepoFacts, min_count: int = 1):
    """
    Assert that project has entry points.

    Args:
        facts: RepoFacts object
        min_count: Minimum number of entry points expected
    """
    assert len(facts.entry_points) >= min_count, (
        f"Expected at least {min_count} entry points, "
        f"found {len(facts.entry_points)}"
    )


# Export assertion helpers
pytest.assert_project_type = assert_project_type
pytest.assert_primary_language = assert_primary_language
pytest.assert_has_interface = assert_has_interface
pytest.assert_has_dependencies = assert_has_dependencies
pytest.assert_has_entry_points = assert_has_entry_points
