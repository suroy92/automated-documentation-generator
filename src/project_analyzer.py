# src/project_analyzer.py
"""
Comprehensive project analyzer that builds project-wide context.

Analyzes the entire project structure, relationships, dependencies, and
architecture patterns to provide rich context for README generation.
"""

from __future__ import annotations
import os
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


class ProjectAnalyzer:
    """
    Builds a comprehensive view of the entire project structure.
    
    Analyzes:
    - Project architecture patterns (MVC, layered, microservices, etc.)
    - Module hierarchy and organization
    - Dependencies (imports, libraries, internal relationships)
    - Entry points and configuration files
    - Testing structure
    - Data flow and relationships
    """

    def __init__(self, ladom_data: Dict[str, Any], project_path: str):
        """
        Initialize the project analyzer.
        
        Args:
            ladom_data: The aggregated LADOM data from file analysis
            project_path: Root path of the project
        """
        self.ladom_data = ladom_data
        self.project_path = Path(project_path)
        self.project_name = ladom_data.get("project_name", self.project_path.name)
        self.files = ladom_data.get("files", [])
        
        # Internal structures
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)
        self.module_map: Dict[str, Dict[str, Any]] = {}
        self.entry_points: List[Dict[str, str]] = []
        
    def analyze(self) -> Dict[str, Any]:
        """
        Perform comprehensive project analysis.
        
        Returns:
            Dict containing all project-level insights
        """
        logger.info(f"Starting comprehensive project analysis for: {self.project_name}")
        
        context = {
            "project_name": self.project_name,
            "project_path": str(self.project_path),
            "total_files": len(self.files),
            "architecture": self._detect_architecture_pattern(),
            "directory_structure": self._analyze_directory_structure(),
            "entry_points": self._find_entry_points(),
            "dependencies": self._analyze_dependencies(),
            "module_hierarchy": self._build_module_hierarchy(),
            "configuration_files": self._find_configuration_files(),
            "testing_structure": self._analyze_testing_structure(),
            "key_features": self._extract_key_features(),
            "technology_stack": self._detect_technology_stack(),
            "file_statistics": self._calculate_file_statistics(),
            "complexity_overview": self._analyze_complexity_overview(),
        }
        
        logger.info("Project analysis complete")
        return context

    def _detect_architecture_pattern(self) -> Dict[str, Any]:
        """
        Detect the architecture pattern used in the project.
        
        Returns:
            Dict with architecture type and description
        """
        patterns_found = []
        confidence = {}
        
        # Check for common directory patterns
        all_dirs = set()
        for file_data in self.files:
            file_path = Path(file_data.get("path", ""))
            all_dirs.update(file_path.parent.parts)
        
        # MVC pattern
        if any(d in ["models", "views", "controllers"] for d in all_dirs):
            patterns_found.append("MVC")
            confidence["MVC"] = 0.8
        
        # Layered architecture
        if any(d in ["services", "repositories", "controllers", "models"] for d in all_dirs):
            patterns_found.append("Layered")
            confidence["Layered"] = 0.7
        
        # Clean architecture
        if any(d in ["domain", "application", "infrastructure", "presentation"] for d in all_dirs):
            patterns_found.append("Clean Architecture")
            confidence["Clean Architecture"] = 0.8
        
        # Microservices indicators
        if any(d in ["services", "api"] for d in all_dirs) and len([f for f in self.files if "main" in f.get("path", "").lower()]) > 1:
            patterns_found.append("Microservices")
            confidence["Microservices"] = 0.6
        
        # Modular monolith
        if len(all_dirs) > 5 and any(d in ["modules", "components"] for d in all_dirs):
            patterns_found.append("Modular Monolith")
            confidence["Modular Monolith"] = 0.7
        
        # Simple structure
        if len(all_dirs) <= 3:
            patterns_found.append("Simple/Flat")
            confidence["Simple/Flat"] = 0.9
        
        # Determine primary pattern
        if patterns_found:
            primary = max(confidence.items(), key=lambda x: x[1])[0] if confidence else patterns_found[0]
        else:
            primary = "Custom"
            patterns_found = ["Custom"]
        
        return {
            "primary_pattern": primary,
            "detected_patterns": patterns_found,
            "confidence": confidence,
            "description": self._get_architecture_description(primary)
        }

    def _get_architecture_description(self, pattern: str) -> str:
        """Get description for detected architecture pattern."""
        descriptions = {
            "MVC": "Model-View-Controller pattern with clear separation of concerns",
            "Layered": "Layered architecture with distinct layers (presentation, business, data)",
            "Clean Architecture": "Clean architecture with dependency inversion and domain-centric design",
            "Microservices": "Microservices architecture with multiple independent services",
            "Modular Monolith": "Modular monolithic structure with well-defined module boundaries",
            "Simple/Flat": "Simple flat structure suitable for small projects",
            "Custom": "Custom architecture tailored to specific requirements"
        }
        return descriptions.get(pattern, "Custom architecture")

    def _analyze_directory_structure(self) -> Dict[str, Any]:
        """
        Analyze the project's directory structure.
        
        Returns:
            Dict with directory tree and descriptions
        """
        # Build directory tree
        dir_tree: Dict[str, Any] = {}
        dir_file_counts: Dict[str, int] = defaultdict(int)
        dir_purposes: Dict[str, str] = {}
        
        for file_data in self.files:
            file_path = Path(file_data.get("path", ""))
            relative_path = self._get_relative_path(file_path)
            
            parts = relative_path.parts[:-1]  # Exclude filename
            for i in range(len(parts)):
                dir_key = "/".join(parts[:i+1])
                dir_file_counts[dir_key] += 1
        
        # Infer directory purposes
        for dir_name, count in dir_file_counts.items():
            purpose = self._infer_directory_purpose(dir_name, count)
            if purpose:
                dir_purposes[dir_name] = purpose
        
        return {
            "directories": list(dir_file_counts.keys()),
            "directory_purposes": dir_purposes,
            "file_counts": dict(dir_file_counts),
            "depth": max(len(d.split("/")) for d in dir_file_counts.keys()) if dir_file_counts else 0
        }

    def _infer_directory_purpose(self, dir_name: str, file_count: int) -> str:
        """Infer the purpose of a directory based on its name."""
        purposes = {
            "src": "Source code - main application code",
            "tests": "Unit tests and test suites",
            "test": "Unit tests and test suites",
            "docs": "Documentation files",
            "documentation": "Documentation files",
            "config": "Configuration files",
            "utils": "Utility functions and helpers",
            "helpers": "Helper functions and utilities",
            "models": "Data models and schemas",
            "views": "View layer / UI components",
            "controllers": "Controller layer / request handlers",
            "services": "Business logic services",
            "api": "API endpoints and routes",
            "database": "Database schemas and migrations",
            "db": "Database related code",
            "migrations": "Database migration scripts",
            "middleware": "Middleware components",
            "routes": "Application routes",
            "schemas": "Data schemas and validation",
            "components": "Reusable components",
            "lib": "Library code",
            "core": "Core application functionality",
            "common": "Common/shared code",
            "shared": "Shared resources and code",
            "assets": "Static assets",
            "static": "Static files (CSS, JS, images)",
            "public": "Publicly accessible files",
            "build": "Build artifacts",
            "dist": "Distribution files",
            "scripts": "Utility scripts",
            "tools": "Development tools",
            "examples": "Example code and demos",
            "analyzers": "Code analyzers",
            "providers": "Service providers",
            "generators": "Code generators"
        }
        
        for key, purpose in purposes.items():
            if key in dir_name.lower():
                return purpose
        
        return f"Contains {file_count} file(s)"

    def _find_entry_points(self) -> List[Dict[str, str]]:
        """
        Find entry points (main files, CLI, API endpoints).
        
        Returns:
            List of entry point information
        """
        entry_points = []
        
        for file_data in self.files:
            file_path = file_data.get("path", "")
            filename = Path(file_path).name
            
            # Check for main files
            if filename in ["main.py", "app.py", "index.py", "run.py", "__main__.py"]:
                entry_points.append({
                    "type": "main",
                    "file": file_path,
                    "description": f"Main entry point: {filename}"
                })
            
            # Check for CLI entry points
            if filename in ["cli.py", "command.py", "console.py"]:
                entry_points.append({
                    "type": "cli",
                    "file": file_path,
                    "description": f"Command-line interface: {filename}"
                })
            
            # Check for API entry points
            if "api" in filename.lower() or "server" in filename.lower():
                entry_points.append({
                    "type": "api",
                    "file": file_path,
                    "description": f"API server: {filename}"
                })
            
            # Check for __main__ execution blocks
            summary = file_data.get("summary", "")
            if "if __name__ == \"__main__\"" in summary or "if __name__ == '__main__'" in summary:
                if not any(ep["file"] == file_path for ep in entry_points):
                    entry_points.append({
                        "type": "executable",
                        "file": file_path,
                        "description": f"Executable script: {filename}"
                    })
        
        return entry_points

    def _analyze_dependencies(self) -> Dict[str, Any]:
        """
        Analyze project dependencies.
        
        Returns:
            Dict with internal and external dependencies
        """
        external_deps: Set[str] = set()
        internal_deps: Dict[str, Set[str]] = defaultdict(set)
        stdlib_imports: Set[str] = set()
        
        # Python standard library modules (common ones)
        stdlib_modules = {
            "os", "sys", "json", "logging", "pathlib", "typing", "collections",
            "itertools", "functools", "re", "datetime", "time", "math", "random",
            "ast", "io", "pickle", "csv", "unittest", "argparse", "configparser",
            "subprocess", "threading", "multiprocessing", "asyncio", "concurrent",
            "copy", "enum", "abc", "dataclasses", "warnings", "traceback"
        }
        
        for file_data in self.files:
            file_path = file_data.get("path", "")
            imports = file_data.get("imports", [])
            
            for imp in imports:
                imp_str = str(imp)
                base_module = imp_str.split(".")[0] if "." in imp_str else imp_str
                
                # Categorize import
                if base_module in stdlib_modules:
                    stdlib_imports.add(base_module)
                elif imp_str.startswith(".") or imp_str.startswith("src."):
                    # Internal/relative import
                    internal_deps[file_path].add(imp_str)
                else:
                    # External third-party
                    external_deps.add(base_module)
        
        return {
            "external_packages": sorted(external_deps),
            "internal_modules": dict(internal_deps),
            "stdlib_imports": sorted(stdlib_imports),
            "total_external": len(external_deps),
            "total_internal": sum(len(deps) for deps in internal_deps.values()),
            "most_used_external": self._get_most_common(external_deps) if external_deps else None
        }

    def _build_module_hierarchy(self) -> Dict[str, Any]:
        """
        Build module hierarchy showing how modules are organized.
        
        Returns:
            Dict representing module structure
        """
        hierarchy: Dict[str, Any] = {}
        
        for file_data in self.files:
            file_path = Path(file_data.get("path", ""))
            relative_path = self._get_relative_path(file_path)
            
            # Build hierarchy
            current = hierarchy
            for part in relative_path.parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Add file info
            filename = relative_path.name
            current[filename] = {
                "functions": len(file_data.get("functions", [])),
                "classes": len(file_data.get("classes", [])),
                "imports": len(file_data.get("imports", []))
            }
        
        return hierarchy

    def _find_configuration_files(self) -> List[Dict[str, str]]:
        """
        Find configuration files in the project.
        
        Returns:
            List of configuration file information
        """
        config_files = []
        config_patterns = {
            "setup.py": "Python package setup",
            "requirements.txt": "Python dependencies",
            "pyproject.toml": "Python project configuration",
            "Pipfile": "Pipenv dependencies",
            "poetry.lock": "Poetry lock file",
            "package.json": "Node.js dependencies",
            "config.yaml": "YAML configuration",
            "config.yml": "YAML configuration",
            "config.json": "JSON configuration",
            ".env": "Environment variables",
            "docker-compose.yml": "Docker Compose configuration",
            "Dockerfile": "Docker container definition",
            "Makefile": "Build automation",
            ".gitignore": "Git ignore patterns",
            "README.md": "Project documentation"
        }
        
        # Search in project root
        for filename, description in config_patterns.items():
            file_path = self.project_path / filename
            if file_path.exists():
                config_files.append({
                    "file": filename,
                    "description": description,
                    "path": str(file_path)
                })
        
        return config_files

    def _analyze_testing_structure(self) -> Dict[str, Any]:
        """
        Analyze the testing structure.
        
        Returns:
            Dict with testing information
        """
        test_files = []
        test_frameworks = set()
        
        for file_data in self.files:
            file_path = file_data.get("path", "")
            filename = Path(file_path).name
            
            # Check if it's a test file
            if "test" in filename.lower() or filename.startswith("test_"):
                test_files.append(file_path)
                
                # Detect test framework from imports
                imports = file_data.get("imports", [])
                for imp in imports:
                    imp_str = str(imp).lower()
                    if "unittest" in imp_str:
                        test_frameworks.add("unittest")
                    elif "pytest" in imp_str:
                        test_frameworks.add("pytest")
                    elif "nose" in imp_str:
                        test_frameworks.add("nose")
                    elif "jest" in imp_str:
                        test_frameworks.add("jest")
                    elif "mocha" in imp_str:
                        test_frameworks.add("mocha")
        
        return {
            "test_files": test_files,
            "test_count": len(test_files),
            "frameworks": list(test_frameworks),
            "has_tests": len(test_files) > 0,
            "test_coverage": f"{len(test_files)}/{len(self.files)} files" if self.files else "0/0 files"
        }

    def _extract_key_features(self) -> List[str]:
        """
        Extract key features based on code analysis.
        
        Returns:
            List of detected features
        """
        features = []
        all_names = []
        
        for file_data in self.files:
            # Collect function and class names
            for func in file_data.get("functions", []):
                all_names.append(func.get("name", "").lower())
            for cls in file_data.get("classes", []):
                all_names.append(cls.get("name", "").lower())
        
        # Detect features based on naming patterns
        feature_keywords = {
            "API": ["api", "endpoint", "route", "request", "response"],
            "Database": ["database", "db", "model", "query", "migration", "schema"],
            "Authentication": ["auth", "login", "token", "jwt", "password", "user"],
            "Caching": ["cache", "redis", "memcache"],
            "Logging": ["log", "logger", "logging"],
            "Testing": ["test", "mock", "fixture"],
            "CLI": ["cli", "command", "console", "argparse"],
            "File Processing": ["file", "read", "write", "parse", "upload"],
            "Data Analysis": ["analyze", "process", "transform", "aggregate"],
            "Web Scraping": ["scrape", "crawl", "spider", "requests"],
            "Machine Learning": ["model", "train", "predict", "ml", "ai"],
            "Documentation": ["doc", "generate", "markdown", "readme"]
        }
        
        for feature, keywords in feature_keywords.items():
            if any(keyword in name for name in all_names for keyword in keywords):
                features.append(feature)
        
        return features

    def _detect_technology_stack(self) -> Dict[str, List[str]]:
        """
        Detect the technology stack used.
        
        Returns:
            Dict categorizing technologies
        """
        stack = {
            "languages": [],
            "frameworks": [],
            "libraries": [],
            "tools": []
        }
        
        # Detect languages from file extensions
        languages = set()
        for file_data in self.files:
            file_path = Path(file_data.get("path", ""))
            ext = file_path.suffix.lower()
            if ext == ".py":
                languages.add("Python")
            elif ext in [".js", ".jsx"]:
                languages.add("JavaScript")
            elif ext in [".ts", ".tsx"]:
                languages.add("TypeScript")
            elif ext == ".java":
                languages.add("Java")
        
        stack["languages"] = sorted(languages)
        
        # Detect frameworks and libraries from imports
        framework_map = {
            "flask": "Flask",
            "django": "Django",
            "fastapi": "FastAPI",
            "express": "Express.js",
            "react": "React",
            "vue": "Vue.js",
            "angular": "Angular",
            "pandas": "Pandas",
            "numpy": "NumPy",
            "tensorflow": "TensorFlow",
            "pytorch": "PyTorch"
        }
        
        detected_frameworks = set()
        for file_data in self.files:
            imports = file_data.get("imports", [])
            for imp in imports:
                imp_str = str(imp).lower()
                for key, framework in framework_map.items():
                    if key in imp_str:
                        detected_frameworks.add(framework)
        
        stack["frameworks"] = sorted(detected_frameworks)
        
        return stack

    def _calculate_file_statistics(self) -> Dict[str, Any]:
        """
        Calculate statistics about the codebase.
        
        Returns:
            Dict with various statistics
        """
        total_functions = 0
        total_classes = 0
        total_lines = 0
        
        for file_data in self.files:
            total_functions += len(file_data.get("functions", []))
            total_classes += len(file_data.get("classes", []))
            
            # Count lines from all functions and classes
            for func in file_data.get("functions", []):
                lines = func.get("lines", {})
                if lines.get("start") and lines.get("end"):
                    total_lines += lines["end"] - lines["start"]
            
            for cls in file_data.get("classes", []):
                lines = cls.get("lines", {})
                if lines.get("start") and lines.get("end"):
                    total_lines += lines["end"] - lines["start"]
        
        return {
            "total_files": len(self.files),
            "total_functions": total_functions,
            "total_classes": total_classes,
            "estimated_lines": total_lines,
            "avg_functions_per_file": round(total_functions / len(self.files), 2) if self.files else 0,
            "avg_classes_per_file": round(total_classes / len(self.files), 2) if self.files else 0
        }

    def _analyze_complexity_overview(self) -> Dict[str, Any]:
        """
        Analyze overall complexity of the project.
        
        Returns:
            Dict with complexity metrics
        """
        complexities = []
        
        for file_data in self.files:
            for func in file_data.get("functions", []):
                complexity = func.get("complexity", {})
                if complexity.get("cyclomatic"):
                    complexities.append(complexity["cyclomatic"])
        
        if complexities:
            avg_complexity = sum(complexities) / len(complexities)
            max_complexity = max(complexities)
            
            # Categorize complexity
            if avg_complexity < 5:
                level = "Low"
            elif avg_complexity < 10:
                level = "Moderate"
            else:
                level = "High"
        else:
            avg_complexity = 0
            max_complexity = 0
            level = "Unknown"
        
        return {
            "average_cyclomatic": round(avg_complexity, 2),
            "max_cyclomatic": max_complexity,
            "complexity_level": level,
            "total_functions_analyzed": len(complexities)
        }

    def _get_relative_path(self, file_path: Path) -> Path:
        """Get path relative to project root."""
        try:
            return file_path.relative_to(self.project_path)
        except ValueError:
            return file_path

    def _get_most_common(self, items: Set[str]) -> Optional[str]:
        """Get the most common item (simplified - returns first)."""
        return list(items)[0] if items else None
