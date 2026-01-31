# src/fact_extractor.py
"""
FactExtractor - Converts LADOM data to RepoFacts.

This module extracts structured facts from raw LADOM analysis data.
It bridges the gap between low-level AST parsing and high-level fact representation.

Pipeline: LADOM (raw) → FactExtractor → RepoFacts (structured)
"""

from __future__ import annotations
import logging
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict, Counter

from .repo_facts import (
    RepoFacts,
    ProjectMetadata,
    ProjectType,
    Language,
    EntryPoint,
    Script,
    Dependency,
    CLIInterface,
    CLICommand,
    WebAPIInterface,
    APIEndpoint,
    GraphQLInterface,
    GRPCInterface,
    EventInterface,
    IaCInterface,
    ProjectInterface,
    RuntimeInfo,
    ConfigFile,
    DirectorySummary,
    TestingInfo,
    Architecture,
    ArchitecturePattern,
)
from .parsers import parse_pom_xml, parse_pyproject_toml

logger = logging.getLogger(__name__)


class FactExtractor:
    """
    Extracts structured facts from LADOM data.

    The extractor is responsible for converting low-level parsing results
    into high-level semantic facts about the repository.
    """

    def __init__(self, project_path: str):
        """
        Initialize fact extractor.

        Args:
            project_path: Root path of the project
        """
        self.project_path = Path(project_path)

    def extract(self, ladom_data: Dict[str, Any]) -> RepoFacts:
        """
        Extract RepoFacts from LADOM data.

        Args:
            ladom_data: Aggregated LADOM data from analyzers

        Returns:
            RepoFacts with extracted information
        """
        logger.info("Extracting facts from LADOM data...")

        project_name = ladom_data.get("project_name", self.project_path.name)
        files = ladom_data.get("files", [])

        # Extract each component
        project = self._extract_project_metadata(project_name, files)
        languages = self._extract_languages(files)
        entry_points = self._extract_entry_points(files)
        scripts = self._extract_scripts()
        dependencies = self._extract_dependencies()
        interface = self._extract_interface(files, languages)
        runtime = self._extract_runtime_info(files)
        config_files = self._extract_config_files()
        architecture = self._extract_architecture(files)
        directory_structure = self._extract_directory_structure(files)
        testing = self._extract_testing_info(files)

        # Calculate statistics
        stats = self._calculate_statistics(files)

        facts = RepoFacts(
            project=project,
            languages=languages,
            entry_points=entry_points,
            scripts=scripts,
            dependencies=dependencies,
            interface=interface,
            runtime=runtime,
            config_files=config_files,
            architecture=architecture,
            directory_structure=directory_structure,
            testing=testing,
            **stats
        )

        logger.info(f"Extracted facts: {facts.total_files} files, "
                   f"{len(languages)} languages, "
                   f"{facts.total_functions} functions")

        return facts

    def _extract_project_metadata(self, project_name: str, files: List[Dict]) -> ProjectMetadata:
        """Extract project metadata."""
        # Try to detect project type
        project_type = self._detect_project_type(files)

        # Try to read version from package.json or setup.py
        version = self._find_version()

        # Try to read license
        license_type = self._find_license()

        return ProjectMetadata(
            name=project_name,
            type=project_type,
            version=version,
            license=license_type
        )

    def _detect_project_type(self, files: List[Dict]) -> ProjectType:
        """Detect project type from files and imports."""
        # Count indicators for each type
        indicators = defaultdict(int)

        for file_data in files:
            imports = file_data.get("imports", [])
            functions = file_data.get("functions", [])
            file_path = file_data.get("path", "").lower()
            imports_str = str(imports).lower()

            # Batch Job indicators (Spring Batch, etc.)
            if any(imp in imports_str for imp in ["spring.batch", "batch.core", "batchjob"]):
                indicators[ProjectType.BATCH_JOB] += 4

            # Event-driven indicators (Kafka, RabbitMQ, Spring Cloud Stream)
            if any(imp in imports_str for imp in ["kafka", "spring.cloud.stream", "spring.kafka", "rabbitmq", "celery", "bull"]):
                indicators[ProjectType.EVENT_DRIVEN] += 3

            # GraphQL indicators (higher priority than Web API)
            if any(imp in imports_str for imp in ["graphql", "apollo", "@apollo/server"]):
                indicators[ProjectType.GRAPHQL_API] += 4

            # CLI indicators
            if any(imp in imports_str for imp in ["typer", "click", "argparse", "commander", "yargs"]):
                indicators[ProjectType.CLI] += 3
            if "cli" in file_path or "command" in file_path:
                indicators[ProjectType.CLI] += 1

            # Web API indicators
            if any(imp in imports_str for imp in ["fastapi", "flask", "express", "nest", "spring.web"]):
                indicators[ProjectType.WEB_API] += 3
            if any(word in file_path for word in ["route", "endpoint", "controller", "api"]):
                indicators[ProjectType.WEB_API] += 1

            # gRPC indicators
            if ".proto" in file_path or "grpc" in imports_str:
                indicators[ProjectType.GRPC_SERVICE] += 3

            # Frontend indicators
            if any(imp in imports_str for imp in ["react", "vue", "angular"]):
                indicators[ProjectType.FRONTEND] += 3
            if file_path.endswith((".jsx", ".tsx", ".vue")):
                indicators[ProjectType.FRONTEND] += 1

            # Desktop indicators (Electron)
            if "electron" in imports_str:
                indicators[ProjectType.DESKTOP] += 4

            # Extension indicators (VSCode, GitHub Actions)
            if "vscode" in imports_str or "extension" in file_path:
                indicators[ProjectType.EXTENSION] += 2

            # IaC indicators (Terraform)
            if file_path.endswith(".tf") or "terraform" in file_path:
                indicators[ProjectType.IAC] += 4

        # Check dependencies for additional indicators (helps with Java projects where imports aren't extracted)
        dependencies = self._extract_dependencies()
        all_deps = dependencies.get("runtime", []) + dependencies.get("dev", [])
        dep_names_lower = [dep.name.lower() for dep in all_deps]

        for dep_name in dep_names_lower:
            # Spring Batch dependencies
            if "spring-boot-starter-batch" in dep_name or "spring-batch-core" in dep_name:
                indicators[ProjectType.BATCH_JOB] += 5

            # Kafka/Event-driven dependencies
            if any(kw in dep_name for kw in ["spring-cloud-stream", "spring-kafka", "kafka-clients"]):
                indicators[ProjectType.EVENT_DRIVEN] += 5

            # GraphQL dependencies
            if any(kw in dep_name for kw in ["graphql-java", "apollo-server", "@apollo/server"]):
                indicators[ProjectType.GRAPHQL_API] += 5

            # Electron dependencies
            if dep_name == "electron":
                indicators[ProjectType.DESKTOP] += 5

        # Check for GitHub Action configuration
        action_yml = self.project_path / "action.yml"
        action_yaml = self.project_path / "action.yaml"
        if action_yml.exists() or action_yaml.exists():
            indicators[ProjectType.EXTENSION] += 3  # GitHub Actions are a type of extension

        # Return type with highest score
        if indicators:
            return max(indicators, key=indicators.get)

        # Default to library if no clear indicators
        return ProjectType.LIBRARY

    def _find_version(self) -> Optional[str]:
        """Find project version from package.json or setup.py."""
        # Check package.json
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    return data.get("version")
            except Exception:
                pass

        # Check setup.py (basic regex extraction)
        setup_py = self.project_path / "setup.py"
        if setup_py.exists():
            try:
                with open(setup_py) as f:
                    content = f.read()
                    match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                    if match:
                        return match.group(1)
            except Exception:
                pass

        return None

    def _find_license(self) -> Optional[str]:
        """Find license type."""
        license_file = self.project_path / "LICENSE"
        if license_file.exists():
            try:
                with open(license_file) as f:
                    content = f.read(500)  # Read first 500 chars
                    if "MIT" in content:
                        return "MIT"
                    elif "Apache" in content:
                        return "Apache-2.0"
                    elif "GPL" in content:
                        return "GPL"
                    elif "BSD" in content:
                        return "BSD"
            except Exception:
                pass

        return None

    def _extract_languages(self, files: List[Dict]) -> List[Language]:
        """Extract programming languages from files."""
        language_counts = Counter()

        for file_data in files:
            file_path = Path(file_data.get("path", ""))
            ext = file_path.suffix.lower()

            if ext == ".py":
                language_counts["Python"] += 1
            elif ext in [".js", ".jsx"]:
                language_counts["JavaScript"] += 1
            elif ext in [".ts", ".tsx"]:
                language_counts["TypeScript"] += 1
            elif ext == ".java":
                language_counts["Java"] += 1
            elif ext in [".go"]:
                language_counts["Go"] += 1
            elif ext in [".rs"]:
                language_counts["Rust"] += 1
            elif ext in [".rb"]:
                language_counts["Ruby"] += 1
            elif ext in [".php"]:
                language_counts["PHP"] += 1

        languages = []
        if language_counts:
            # Primary language is the one with most files
            primary_lang = language_counts.most_common(1)[0][0]

            for lang_name, count in language_counts.items():
                languages.append(Language(
                    name=lang_name,
                    file_count=count,
                    primary=(lang_name == primary_lang)
                ))

        return languages

    def _extract_entry_points(self, files: List[Dict]) -> List[EntryPoint]:
        """Extract entry points from files."""
        entry_points = []

        for file_data in files:
            file_path = file_data.get("path", "")
            filename = Path(file_path).name.lower()

            # Main entry points
            if filename in ["main.py", "app.py", "index.js", "index.ts", "server.js", "server.ts"]:
                entry_points.append(EntryPoint(
                    file=file_path,
                    type="main",
                    description=f"Main entry point: {filename}"
                ))

            # CLI entry points
            elif filename in ["cli.py", "cli.js", "__main__.py"]:
                entry_points.append(EntryPoint(
                    file=file_path,
                    type="cli",
                    description=f"CLI entry point: {filename}"
                ))

            # API entry points
            elif "api" in filename or "routes" in filename:
                entry_points.append(EntryPoint(
                    file=file_path,
                    type="api",
                    description=f"API entry point: {filename}"
                ))

        return entry_points

    def _extract_scripts(self) -> Dict[str, Script]:
        """Extract build/run scripts from package.json."""
        scripts = {}

        # Check package.json
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    package_scripts = data.get("scripts", {})

                    for name, command in package_scripts.items():
                        scripts[name] = Script(
                            name=name,
                            command=command
                        )
            except Exception as e:
                logger.warning(f"Error reading package.json scripts: {e}")

        return scripts

    def _extract_dependencies(self) -> Dict[str, List[Dependency]]:
        """Extract dependencies from manifest files."""
        dependencies = defaultdict(list)

        # Python dependencies from requirements.txt
        requirements_txt = self.project_path / "requirements.txt"
        if requirements_txt.exists():
            try:
                with open(requirements_txt) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            # Parse package==version or package>=version
                            match = re.match(r'([a-zA-Z0-9\-_]+)([><=!]+.+)?', line)
                            if match:
                                name = match.group(1)
                                version = match.group(2).lstrip(">=<! ") if match.group(2) else None
                                dependencies["runtime"].append(Dependency(
                                    name=name,
                                    version=version,
                                    type="runtime",
                                    source="requirements.txt"
                                ))
            except Exception as e:
                logger.warning(f"Error reading requirements.txt: {e}")

        # Python dependencies from pyproject.toml (modern Python projects)
        pyproject_toml = self.project_path / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                pyproject_data = parse_pyproject_toml(str(pyproject_toml))

                # Runtime dependencies
                for dep_info in pyproject_data.get('dependencies', []):
                    dependencies["runtime"].append(Dependency(
                        name=dep_info['name'],
                        version=dep_info.get('version'),
                        type="runtime",
                        source="pyproject.toml"
                    ))

                # Dev dependencies
                for dep_info in pyproject_data.get('dev_dependencies', []):
                    dependencies["dev"].append(Dependency(
                        name=dep_info['name'],
                        version=dep_info.get('version'),
                        type="dev",
                        source="pyproject.toml"
                    ))
            except Exception as e:
                logger.warning(f"Error reading pyproject.toml dependencies: {e}")

        # Node.js dependencies from package.json
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)

                    # Runtime dependencies
                    for name, version in data.get("dependencies", {}).items():
                        dependencies["runtime"].append(Dependency(
                            name=name,
                            version=version,
                            type="runtime",
                            source="package.json"
                        ))

                    # Dev dependencies
                    for name, version in data.get("devDependencies", {}).items():
                        dependencies["dev"].append(Dependency(
                            name=name,
                            version=version,
                            type="dev",
                            source="package.json"
                        ))
            except Exception as e:
                logger.warning(f"Error reading package.json dependencies: {e}")

        # Java dependencies from pom.xml (Maven)
        pom_xml = self.project_path / "pom.xml"
        if pom_xml.exists():
            try:
                pom_data = parse_pom_xml(str(pom_xml))

                # Categorize dependencies based on scope
                from .parsers.pom_parser import categorize_maven_dependency

                for dep_info in pom_data.get('dependencies', []):
                    scope = dep_info.get('scope', 'compile')
                    dep_type = categorize_maven_dependency(scope)

                    dependencies[dep_type].append(Dependency(
                        name=dep_info['artifact_id'],  # Use artifactId as main name
                        version=dep_info.get('version'),
                        type=dep_type,
                        source="pom.xml"
                    ))
            except Exception as e:
                logger.warning(f"Error reading pom.xml dependencies: {e}")

        return dict(dependencies)

    def _extract_interface(self, files: List[Dict], languages: List[Language]) -> ProjectInterface:
        """Extract project interface based on detected type."""
        interface = ProjectInterface()

        # Extract dependencies first (needed for smarter framework detection)
        dependencies = self._extract_dependencies()

        # Detect CLI interface
        cli = self._detect_cli_interface(files, dependencies)
        if cli:
            interface.cli = cli

        # Detect Web API interface
        web_api = self._detect_web_api_interface(files, languages, dependencies)
        if web_api:
            interface.web_api = web_api

        return interface

    def _detect_cli_interface(self, files: List[Dict], dependencies: Dict[str, List[Dependency]]) -> Optional[CLIInterface]:
        """Detect CLI interface from imports, code, and dependencies."""
        framework = None
        commands = []

        # Check imports from files
        for file_data in files:
            imports = str(file_data.get("imports", [])).lower()

            # Detect framework from imports
            if "typer" in imports and not framework:
                framework = "Typer"
            elif "click" in imports and not framework:
                framework = "Click"
            elif "argparse" in imports and not framework:
                framework = "argparse"

            # TODO: Extract actual commands from functions/decorators
            # This would require more sophisticated AST analysis

        # If framework not detected from imports, check dependencies
        if not framework:
            runtime_deps = dependencies.get("runtime", [])
            dep_names = [dep.name.lower() for dep in runtime_deps]

            if "typer" in dep_names:
                framework = "Typer"
            elif "click" in dep_names:
                framework = "Click"

        if framework:
            return CLIInterface(framework=framework, commands=commands)

        return None

    def _detect_web_api_interface(self, files: List[Dict], languages: List[Language], dependencies: Dict[str, List[Dependency]]) -> Optional[WebAPIInterface]:
        """Detect Web API interface from imports, code, and dependencies."""
        framework = None
        endpoints = []

        # Check imports from files
        for file_data in files:
            imports = str(file_data.get("imports", [])).lower()

            # Detect framework from imports
            if "fastapi" in imports and not framework:
                framework = "FastAPI"
            elif "flask" in imports and not framework:
                framework = "Flask"
            elif "express" in imports and not framework:
                framework = "Express"

            # TODO: Extract actual endpoints from route decorators
            # This would require more sophisticated AST analysis

        # If framework not detected from imports, check dependencies
        if not framework:
            runtime_deps = dependencies.get("runtime", [])
            dep_names = [dep.name.lower() for dep in runtime_deps]

            if "fastapi" in dep_names:
                framework = "FastAPI"
            elif "flask" in dep_names:
                framework = "Flask"
            elif "express" in dep_names:
                framework = "Express"

        if framework:
            return WebAPIInterface(framework=framework, endpoints=endpoints)

        return None

    def _extract_runtime_info(self, files: List[Dict]) -> RuntimeInfo:
        """Extract runtime information."""
        ports = []

        # Look for common port patterns in code
        for file_data in files:
            # Check for port assignments in code
            # This is a simplified heuristic
            summary = file_data.get("summary", "")
            if summary:
                # Look for patterns like "port=3000" or "PORT=8080"
                port_matches = re.findall(r'port[=\s:]+(\d{4,5})', summary, re.IGNORECASE)
                ports.extend(int(p) for p in port_matches)

        # Remove duplicates and common dev ports
        unique_ports = list(set(ports))

        return RuntimeInfo(ports=unique_ports[:5])  # Limit to 5 ports

    def _extract_config_files(self) -> List[ConfigFile]:
        """Extract configuration files."""
        config_files = []

        # Common config file patterns
        config_patterns = {
            "package.json": ("json", "Node.js package configuration"),
            "requirements.txt": ("text", "Python dependencies"),
            "setup.py": ("python", "Python package setup"),
            "pyproject.toml": ("toml", "Python project configuration"),
            "pom.xml": ("xml", "Maven project configuration"),
            "tsconfig.json": ("json", "TypeScript configuration"),
            "vite.config.ts": ("typescript", "Vite build configuration"),
            "vite.config.js": ("javascript", "Vite build configuration"),
            "action.yml": ("yaml", "GitHub Action configuration"),
            "action.yaml": ("yaml", "GitHub Action configuration"),
            "config.yaml": ("yaml", "YAML configuration"),
            "config.yml": ("yaml", "YAML configuration"),
            ".env": ("env", "Environment variables"),
            "docker-compose.yml": ("yaml", "Docker Compose configuration"),
            "Dockerfile": ("docker", "Docker container definition"),
        }

        for filename, (file_type, description) in config_patterns.items():
            config_file = self.project_path / filename
            if config_file.exists():
                config_files.append(ConfigFile(
                    file=filename,
                    type=file_type,
                    description=description
                ))

        # Check for Terraform files (.tf)
        for tf_file in self.project_path.glob("*.tf"):
            config_files.append(ConfigFile(
                file=tf_file.name,
                type="terraform",
                description="Terraform infrastructure configuration"
            ))

        return config_files

    def _extract_architecture(self, files: List[Dict]) -> Architecture:
        """Extract architecture pattern."""
        # Detect architecture based on directory structure
        all_dirs = set()
        for file_data in files:
            file_path = Path(file_data.get("path", ""))
            all_dirs.update(file_path.parent.parts)

        # MVC pattern
        if {"models", "views", "controllers"}.issubset(all_dirs):
            return Architecture(
                pattern=ArchitecturePattern.MVC,
                description="Model-View-Controller pattern",
                layers=["Models", "Views", "Controllers"]
            )

        # Layered architecture
        if {"services", "repositories", "controllers"}.intersection(all_dirs):
            return Architecture(
                pattern=ArchitecturePattern.LAYERED,
                description="Layered architecture",
                layers=["Controllers", "Services", "Repositories"]
            )

        # Simple structure
        if len(all_dirs) <= 3:
            return Architecture(
                pattern=ArchitecturePattern.SIMPLE,
                description="Simple flat structure"
            )

        return Architecture(
            pattern=ArchitecturePattern.CUSTOM,
            description="Custom architecture"
        )

    def _extract_directory_structure(self, files: List[Dict]) -> List[DirectorySummary]:
        """Extract directory structure summary."""
        dir_info = defaultdict(lambda: {"count": 0, "languages": set()})

        for file_data in files:
            file_path = Path(file_data.get("path", ""))
            if file_path.parent != Path("."):
                dir_key = str(file_path.parent)
                dir_info[dir_key]["count"] += 1

                ext = file_path.suffix
                if ext == ".py":
                    dir_info[dir_key]["languages"].add("Python")
                elif ext in [".js", ".jsx"]:
                    dir_info[dir_key]["languages"].add("JavaScript")
                elif ext in [".ts", ".tsx"]:
                    dir_info[dir_key]["languages"].add("TypeScript")

        summaries = []
        for dir_path, info in dir_info.items():
            summaries.append(DirectorySummary(
                path=dir_path,
                purpose=self._infer_directory_purpose(dir_path),
                file_count=info["count"],
                primary_languages=list(info["languages"])
            ))

        return summaries

    def _infer_directory_purpose(self, dir_path: str) -> str:
        """Infer directory purpose from name."""
        dir_name = Path(dir_path).name.lower()

        purposes = {
            "src": "Source code",
            "tests": "Unit tests",
            "docs": "Documentation",
            "utils": "Utility functions",
            "models": "Data models",
            "views": "View layer",
            "controllers": "Controllers",
            "services": "Business logic",
            "api": "API routes",
            "config": "Configuration",
        }

        return purposes.get(dir_name, "Project files")

    def _extract_testing_info(self, files: List[Dict]) -> TestingInfo:
        """Extract testing information."""
        test_count = 0
        framework = None

        for file_data in files:
            file_path = file_data.get("path", "").lower()
            if "test" in file_path:
                test_count += 1

                # Detect framework from imports
                if not framework:
                    imports = str(file_data.get("imports", [])).lower()
                    if "pytest" in imports:
                        framework = "pytest"
                    elif "jest" in imports:
                        framework = "Jest"
                    elif "unittest" in imports:
                        framework = "unittest"

        # If framework not detected from imports, check dependencies
        if not framework:
            dependencies = self._extract_dependencies()
            all_deps = dependencies.get("dev", []) + dependencies.get("runtime", [])
            dep_names = [dep.name.lower() for dep in all_deps]

            if "pytest" in dep_names:
                framework = "pytest"
            elif "jest" in dep_names:
                framework = "Jest"
            elif "mocha" in dep_names:
                framework = "Mocha"
            elif "unittest" in dep_names:
                framework = "unittest"

        return TestingInfo(
            framework=framework,
            test_count=test_count
        )

    def _calculate_statistics(self, files: List[Dict]) -> Dict[str, int]:
        """Calculate code statistics."""
        total_functions = 0
        total_classes = 0
        total_lines = 0

        for file_data in files:
            total_functions += len(file_data.get("functions", []))
            total_classes += len(file_data.get("classes", []))

            # Estimate lines from functions and classes
            for func in file_data.get("functions", []):
                lines = func.get("lines", {})
                if lines.get("start") and lines.get("end"):
                    total_lines += lines["end"] - lines["start"]

            for cls in file_data.get("classes", []):
                lines = cls.get("lines", {})
                if lines.get("start") and lines.get("end"):
                    total_lines += lines["end"] - lines["start"]

        return {
            "total_files": len(files),
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_lines": total_lines
        }
