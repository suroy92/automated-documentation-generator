# src/fact_normalizer.py
"""
FactNormalizer - Normalizes and cleans RepoFacts.

This module ensures that extracted facts are consistent, clean, and ready for
rendering. It applies business rules and data transformations.

Pipeline: RepoFacts (raw) → FactNormalizer → RepoFacts (normalized)
"""

from __future__ import annotations
import logging
from typing import Optional
from pathlib import Path, PurePosixPath

from .repo_facts import (
    RepoFacts,
    Language,
    EntryPoint,
    Dependency,
    ProjectType,
)

logger = logging.getLogger(__name__)


class FactNormalizer:
    """
    Normalizes extracted facts to ensure consistency.

    Normalization rules:
    - Remove duplicate entries
    - Sort lists for deterministic output
    - Normalize file paths to POSIX style
    - Remove invalid/empty entries
    - Apply business rules (e.g., stdlib filtering)
    """

    # Python standard library modules (to filter from dependencies)
    PYTHON_STDLIB = {
        "os", "sys", "json", "logging", "pathlib", "typing", "collections",
        "itertools", "functools", "re", "datetime", "time", "math", "random",
        "ast", "io", "pickle", "csv", "unittest", "argparse", "configparser",
        "subprocess", "threading", "multiprocessing", "asyncio", "concurrent",
        "copy", "enum", "abc", "dataclasses", "warnings", "traceback", "inspect",
        "string", "operator", "types", "weakref", "heapq", "bisect", "array",
        "struct", "codecs", "textwrap", "unicodedata", "difflib", "hashlib",
        "hmac", "secrets", "uuid", "html", "xml", "email", "http", "urllib",
        "socket", "ssl", "importlib", "pkgutil",
    }

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize fact normalizer.

        Args:
            project_root: Project root for path normalization
        """
        self.project_root = Path(project_root) if project_root else None

    def normalize(self, facts: RepoFacts) -> RepoFacts:
        """
        Normalize repo facts.

        Args:
            facts: Raw extracted facts

        Returns:
            Normalized facts
        """
        logger.info("Normalizing extracted facts...")

        # Normalize each component
        self._normalize_languages(facts)
        self._normalize_entry_points(facts)
        self._normalize_dependencies(facts)
        self._normalize_paths(facts)
        self._sort_lists(facts)
        self._apply_business_rules(facts)

        logger.info("Fact normalization complete")

        return facts

    def _normalize_languages(self, facts: RepoFacts):
        """Normalize language data."""
        # Remove duplicates by name
        seen = set()
        unique_languages = []

        for lang in facts.languages:
            if lang.name not in seen:
                seen.add(lang.name)
                unique_languages.append(lang)
            else:
                # Merge with existing (add file counts)
                existing = next(l for l in unique_languages if l.name == lang.name)
                existing.file_count += lang.file_count

        # Ensure at least one primary language
        if unique_languages and not any(l.primary for l in unique_languages):
            # Mark the one with most files as primary
            max_lang = max(unique_languages, key=lambda l: l.file_count)
            max_lang.primary = True

        facts.languages = unique_languages

    def _normalize_entry_points(self, facts: RepoFacts):
        """Normalize entry points."""
        # Remove duplicates
        seen = set()
        unique_entries = []

        for entry in facts.entry_points:
            key = (entry.file, entry.type)
            if key not in seen:
                seen.add(key)
                # Normalize path
                entry.file = self._normalize_path(entry.file)
                unique_entries.append(entry)

        facts.entry_points = unique_entries

    def _normalize_dependencies(self, facts: RepoFacts):
        """Normalize dependencies."""
        for dep_type, deps in facts.dependencies.items():
            # Remove duplicates
            seen = set()
            unique_deps = []

            for dep in deps:
                if dep.name not in seen:
                    # Filter stdlib for Python dependencies
                    if dep.source and "requirements.txt" in dep.source:
                        if dep.name.lower() in self.PYTHON_STDLIB:
                            logger.debug(f"Filtering stdlib module: {dep.name}")
                            continue

                    seen.add(dep.name)
                    unique_deps.append(dep)

            facts.dependencies[dep_type] = unique_deps

    def _normalize_paths(self, facts: RepoFacts):
        """Normalize all file paths to POSIX relative paths."""
        # Normalize entry points
        for entry in facts.entry_points:
            entry.file = self._normalize_path(entry.file)

        # Normalize config files
        for config in facts.config_files:
            config.file = self._normalize_path(config.file)

        # Normalize directory structure
        for dir_summary in facts.directory_structure:
            dir_summary.path = self._normalize_path(dir_summary.path)

        # Normalize interface paths
        if facts.interface.web_api:
            for endpoint in facts.interface.web_api.endpoints:
                if endpoint.file:
                    endpoint.file = self._normalize_path(endpoint.file)

        if facts.interface.grpc:
            facts.interface.grpc.proto_files = [
                self._normalize_path(f) for f in facts.interface.grpc.proto_files
            ]

    def _normalize_path(self, path: str) -> str:
        """Normalize a single path to POSIX relative style."""
        if not path:
            return path

        try:
            p = Path(path)

            # If project_root provided, make relative to it
            if self.project_root:
                try:
                    p = p.resolve().relative_to(self.project_root.resolve())
                except (ValueError, OSError):
                    # Path not under project root, use as-is
                    pass

            # Convert to POSIX style
            posix_path = p.as_posix()

            # Remove leading './'
            if posix_path.startswith('./'):
                posix_path = posix_path[2:]

            return posix_path
        except Exception as e:
            logger.warning(f"Error normalizing path '{path}': {e}")
            return path

    def _sort_lists(self, facts: RepoFacts):
        """Sort lists for deterministic output."""
        # Sort languages by file count (descending)
        facts.languages.sort(key=lambda l: l.file_count, reverse=True)

        # Sort entry points by type
        type_order = {"main": 0, "cli": 1, "api": 2, "script": 3, "test": 4}
        facts.entry_points.sort(key=lambda e: (type_order.get(e.type, 5), e.file))

        # Sort dependencies alphabetically
        for dep_type in facts.dependencies:
            facts.dependencies[dep_type].sort(key=lambda d: d.name.lower())

        # Sort config files
        facts.config_files.sort(key=lambda c: c.file)

        # Sort directory structure
        facts.directory_structure.sort(key=lambda d: d.path)

    def _apply_business_rules(self, facts: RepoFacts):
        """Apply business rules and data enrichment."""
        # Rule: If no interface detected but we have a project type, infer interface
        if not facts.has_interface():
            if facts.project.type == ProjectType.CLI:
                # Create basic CLI interface
                from .repo_facts import CLIInterface
                facts.interface.cli = CLIInterface()
            elif facts.project.type == ProjectType.WEB_API:
                # Create basic Web API interface
                from .repo_facts import WebAPIInterface
                facts.interface.web_api = WebAPIInterface()

        # Rule: Ensure project name doesn't have special characters
        facts.project.name = self._clean_project_name(facts.project.name)

        # Rule: Cap statistics at reasonable limits (prevent outliers)
        facts.total_files = min(facts.total_files, 10000)
        facts.total_functions = min(facts.total_functions, 100000)
        facts.total_classes = min(facts.total_classes, 10000)

        # Rule: Remove test files from entry points if too many
        if len(facts.entry_points) > 10:
            facts.entry_points = [
                ep for ep in facts.entry_points
                if ep.type != "test"
            ][:10]  # Limit to 10

    def _clean_project_name(self, name: str) -> str:
        """Clean project name by removing special characters."""
        import re

        # Remove path separators
        name = name.replace("\\", "-").replace("/", "-")

        # Remove multiple dashes/underscores
        name = re.sub(r'[-_]+', '-', name)

        # Remove leading/trailing dashes
        name = name.strip('-_')

        return name if name else "project"


def normalize_facts(facts: RepoFacts, project_root: Optional[str] = None) -> RepoFacts:
    """
    Normalize repo facts (convenience function).

    Args:
        facts: Facts to normalize
        project_root: Project root for path normalization

    Returns:
        Normalized facts
    """
    normalizer = FactNormalizer(project_root)
    return normalizer.normalize(facts)
