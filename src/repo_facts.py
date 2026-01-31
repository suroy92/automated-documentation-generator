# src/repo_facts.py
"""
RepoFacts - Structured fact model for repository analysis.

This module defines the canonical data model for representing extracted facts
about a repository. All README generation should be driven from RepoFacts,
not from raw file parsing or guesswork.

Design principles:
- Evidence-based: Every field must be derived from actual code/config
- Typed: Strong typing prevents errors and documents structure
- Optional: Missing data is represented as None/empty, not placeholders
- Normalized: Data is cleaned and standardized during extraction
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Literal
from enum import Enum


class ProjectType(Enum):
    """Types of projects we can detect."""
    CLI = "cli"
    LIBRARY = "library"
    WEB_API = "web_api"
    GRAPHQL_API = "graphql_api"
    GRPC_SERVICE = "grpc_service"
    BATCH_JOB = "batch_job"
    EVENT_DRIVEN = "event_driven"
    FRONTEND = "frontend"
    DESKTOP = "desktop"
    EXTENSION = "extension"
    IAC = "iac"
    UNKNOWN = "unknown"


class ArchitecturePattern(Enum):
    """Detected architecture patterns."""
    MVC = "mvc"
    LAYERED = "layered"
    CLEAN = "clean"
    MICROSERVICES = "microservices"
    MODULAR_MONOLITH = "modular_monolith"
    SIMPLE = "simple"
    CUSTOM = "custom"


@dataclass
class ProjectMetadata:
    """Core project metadata."""
    name: str
    type: ProjectType = ProjectType.UNKNOWN
    description: Optional[str] = None
    version: Optional[str] = None
    license: Optional[str] = None
    homepage: Optional[str] = None
    repository: Optional[str] = None


@dataclass
class Language:
    """Programming language detected in project."""
    name: str
    file_count: int
    primary: bool = False  # Is this the primary language?
    version: Optional[str] = None  # e.g., "3.11" for Python


@dataclass
class EntryPoint:
    """Application entry point."""
    file: str  # Relative path to file
    type: Literal["main", "cli", "api", "script", "test"]
    description: Optional[str] = None
    command: Optional[str] = None  # How to run it


@dataclass
class Script:
    """Build/run script from package manager."""
    name: str
    command: str
    description: Optional[str] = None


@dataclass
class Dependency:
    """External dependency."""
    name: str
    version: Optional[str] = None
    type: Literal["runtime", "dev", "peer", "optional"] = "runtime"
    source: Optional[str] = None  # File it was found in


@dataclass
class CLICommand:
    """CLI command definition."""
    name: str
    description: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    options: List[Dict[str, str]] = field(default_factory=list)
    example: Optional[str] = None


@dataclass
class APIEndpoint:
    """REST/HTTP API endpoint."""
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
    path: str
    description: Optional[str] = None
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    request_body: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None
    file: Optional[str] = None  # Where it's defined


@dataclass
class GraphQLType:
    """GraphQL type definition."""
    name: str
    kind: Literal["type", "query", "mutation", "subscription", "input"]
    fields: List[Dict[str, str]] = field(default_factory=list)
    description: Optional[str] = None


@dataclass
class GRPCService:
    """gRPC service definition."""
    name: str
    rpcs: List[Dict[str, Any]] = field(default_factory=list)
    file: Optional[str] = None  # .proto file


@dataclass
class EventTopic:
    """Event-driven topic/channel."""
    name: str
    direction: Literal["producer", "consumer", "both"]
    message_type: Optional[str] = None
    description: Optional[str] = None


@dataclass
class CLIInterface:
    """CLI application interface."""
    framework: Optional[str] = None  # typer, click, argparse, etc.
    commands: List[CLICommand] = field(default_factory=list)
    entry_point: Optional[str] = None


@dataclass
class WebAPIInterface:
    """Web/REST API interface."""
    framework: Optional[str] = None  # FastAPI, Flask, Express, etc.
    base_path: str = "/"
    endpoints: List[APIEndpoint] = field(default_factory=list)
    authentication: Optional[str] = None


@dataclass
class GraphQLInterface:
    """GraphQL API interface."""
    framework: Optional[str] = None  # Apollo, etc.
    types: List[GraphQLType] = field(default_factory=list)
    schema_file: Optional[str] = None


@dataclass
class GRPCInterface:
    """gRPC interface."""
    services: List[GRPCService] = field(default_factory=list)
    proto_files: List[str] = field(default_factory=list)


@dataclass
class EventInterface:
    """Event-driven interface."""
    framework: Optional[str] = None  # Kafka, RabbitMQ, etc.
    topics: List[EventTopic] = field(default_factory=list)


@dataclass
class IaCInterface:
    """Infrastructure as Code interface."""
    tool: Optional[str] = None  # Terraform, CloudFormation, etc.
    variables: List[Dict[str, Any]] = field(default_factory=list)
    outputs: List[Dict[str, Any]] = field(default_factory=list)
    resources: List[str] = field(default_factory=list)


@dataclass
class ProjectInterface:
    """Project's primary interface (one of these will be populated)."""
    cli: Optional[CLIInterface] = None
    web_api: Optional[WebAPIInterface] = None
    graphql: Optional[GraphQLInterface] = None
    grpc: Optional[GRPCInterface] = None
    event_driven: Optional[EventInterface] = None
    iac: Optional[IaCInterface] = None


@dataclass
class RuntimeInfo:
    """Runtime configuration."""
    ports: List[int] = field(default_factory=list)
    host: Optional[str] = None
    environment: Optional[str] = None  # production, development, etc.


@dataclass
class ConfigFile:
    """Configuration file."""
    file: str  # Relative path
    type: str  # yaml, json, env, ini, etc.
    description: Optional[str] = None
    env_vars: List[str] = field(default_factory=list)  # Required env vars


@dataclass
class DirectorySummary:
    """Summary of a directory's purpose."""
    path: str
    purpose: str
    file_count: int
    primary_languages: List[str] = field(default_factory=list)


@dataclass
class TestingInfo:
    """Testing configuration."""
    framework: Optional[str] = None  # pytest, jest, etc.
    test_count: int = 0
    coverage_tool: Optional[str] = None
    test_command: Optional[str] = None


@dataclass
class Architecture:
    """Architecture information."""
    pattern: ArchitecturePattern = ArchitecturePattern.CUSTOM
    description: Optional[str] = None
    layers: List[str] = field(default_factory=list)
    components: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class RepoFacts:
    """
    Complete fact model for a repository.

    This is the canonical data structure that drives README generation.
    Every field is evidence-based - derived from actual code/config files.
    """

    # Core metadata
    project: ProjectMetadata

    # Languages and entry points
    languages: List[Language] = field(default_factory=list)
    entry_points: List[EntryPoint] = field(default_factory=list)

    # Build and dependencies
    scripts: Dict[str, Script] = field(default_factory=dict)  # Key: script name
    dependencies: Dict[str, List[Dependency]] = field(default_factory=dict)  # runtime, dev, etc.

    # Primary interface (one will be populated based on project type)
    interface: ProjectInterface = field(default_factory=ProjectInterface)

    # Runtime and configuration
    runtime: RuntimeInfo = field(default_factory=RuntimeInfo)
    config_files: List[ConfigFile] = field(default_factory=list)

    # Architecture and structure
    architecture: Architecture = field(default_factory=Architecture)
    directory_structure: List[DirectorySummary] = field(default_factory=list)

    # Testing
    testing: TestingInfo = field(default_factory=TestingInfo)

    # Statistics
    total_files: int = 0
    total_lines: int = 0
    total_functions: int = 0
    total_classes: int = 0

    def get_primary_language(self) -> Optional[Language]:
        """Get the primary programming language."""
        for lang in self.languages:
            if lang.primary:
                return lang
        # If no primary set, return the one with most files
        if self.languages:
            return max(self.languages, key=lambda l: l.file_count)
        return None

    def has_interface(self) -> bool:
        """Check if any interface is defined."""
        return any([
            self.interface.cli,
            self.interface.web_api,
            self.interface.graphql,
            self.interface.grpc,
            self.interface.event_driven,
            self.interface.iac,
        ])

    def get_interface_type(self) -> Optional[str]:
        """Get the type of interface this project exposes."""
        if self.interface.cli:
            return "CLI"
        elif self.interface.web_api:
            return "Web API"
        elif self.interface.graphql:
            return "GraphQL"
        elif self.interface.grpc:
            return "gRPC"
        elif self.interface.event_driven:
            return "Event-Driven"
        elif self.interface.iac:
            return "Infrastructure as Code"
        return None

    def get_install_command(self) -> Optional[str]:
        """Get the install command based on detected package manager."""
        # Check for Node.js
        if any(lang.name.lower() in ["javascript", "typescript"] for lang in self.languages):
            if any(cf.file == "package.json" for cf in self.config_files):
                return "npm install"

        # Check for Python
        if any(lang.name.lower() == "python" for lang in self.languages):
            if any(cf.file == "requirements.txt" for cf in self.config_files):
                return "pip install -r requirements.txt"
            elif any(cf.file == "pyproject.toml" for cf in self.config_files):
                return "pip install ."

        # Check for Java
        if any(lang.name.lower() == "java" for lang in self.languages):
            if any(cf.file == "pom.xml" for cf in self.config_files):
                return "mvn install"
            elif any(cf.file in ["build.gradle", "build.gradle.kts"] for cf in self.config_files):
                return "gradle build"

        return None

    def get_run_command(self) -> Optional[str]:
        """Get the primary run command."""
        # Check scripts first
        for script_name in ["start", "dev", "run", "serve"]:
            if script_name in self.scripts:
                # Infer package manager from primary language
                if any(lang.name.lower() in ["javascript", "typescript"] for lang in self.languages):
                    return f"npm run {script_name}"
                elif any(lang.name.lower() == "python" for lang in self.languages):
                    return self.scripts[script_name].command

        # Check entry points
        if self.entry_points:
            main_entry = next((ep for ep in self.entry_points if ep.type == "main"), None)
            if main_entry and main_entry.command:
                return main_entry.command

        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        from dataclasses import asdict
        return asdict(self)


def create_empty_facts(project_name: str) -> RepoFacts:
    """Create an empty RepoFacts with just project name."""
    return RepoFacts(
        project=ProjectMetadata(name=project_name)
    )
