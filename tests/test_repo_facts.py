# tests/test_repo_facts.py
"""
Tests for RepoFacts schema.

Tests the structured fact model to ensure:
- Proper dataclass structure
- Utility methods work correctly
- Type safety
- Serialization
"""

import pytest
from src.repo_facts import (
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
    ProjectInterface,
    ConfigFile,
    create_empty_facts,
)


class TestProjectMetadata:
    """Tests for ProjectMetadata."""

    def test_basic_metadata(self):
        """Test basic project metadata creation."""
        metadata = ProjectMetadata(
            name="test-project",
            type=ProjectType.CLI,
            description="A test project",
            version="1.0.0"
        )

        assert metadata.name == "test-project"
        assert metadata.type == ProjectType.CLI
        assert metadata.description == "A test project"
        assert metadata.version == "1.0.0"

    def test_optional_fields(self):
        """Test that optional fields default to None."""
        metadata = ProjectMetadata(name="minimal")

        assert metadata.name == "minimal"
        assert metadata.type == ProjectType.UNKNOWN
        assert metadata.description is None
        assert metadata.license is None


class TestLanguage:
    """Tests for Language."""

    def test_language_creation(self):
        """Test language creation."""
        lang = Language(
            name="Python",
            file_count=50,
            primary=True,
            version="3.11"
        )

        assert lang.name == "Python"
        assert lang.file_count == 50
        assert lang.primary is True
        assert lang.version == "3.11"

    def test_non_primary_language(self):
        """Test non-primary language defaults."""
        lang = Language(name="JavaScript", file_count=10)

        assert lang.primary is False
        assert lang.version is None


class TestEntryPoint:
    """Tests for EntryPoint."""

    def test_main_entry_point(self):
        """Test main entry point."""
        entry = EntryPoint(
            file="src/main.py",
            type="main",
            description="Application entry point",
            command="python -m src.main"
        )

        assert entry.file == "src/main.py"
        assert entry.type == "main"
        assert entry.command == "python -m src.main"

    def test_cli_entry_point(self):
        """Test CLI entry point."""
        entry = EntryPoint(
            file="src/cli.py",
            type="cli",
            description="CLI interface"
        )

        assert entry.type == "cli"
        assert entry.command is None


class TestDependency:
    """Tests for Dependency."""

    def test_runtime_dependency(self):
        """Test runtime dependency."""
        dep = Dependency(
            name="requests",
            version="2.31.0",
            type="runtime",
            source="requirements.txt"
        )

        assert dep.name == "requests"
        assert dep.version == "2.31.0"
        assert dep.type == "runtime"

    def test_dev_dependency(self):
        """Test dev dependency."""
        dep = Dependency(
            name="pytest",
            version="7.4.0",
            type="dev"
        )

        assert dep.type == "dev"
        assert dep.source is None


class TestCLIInterface:
    """Tests for CLI interface."""

    def test_cli_with_commands(self):
        """Test CLI interface with commands."""
        cmd = CLICommand(
            name="generate",
            description="Generate documentation",
            arguments=["path"],
            options=[{"name": "--output", "description": "Output directory"}],
            example="docgen generate ./project --output ./docs"
        )

        cli = CLIInterface(
            framework="typer",
            commands=[cmd],
            entry_point="src/cli.py"
        )

        assert cli.framework == "typer"
        assert len(cli.commands) == 1
        assert cli.commands[0].name == "generate"

    def test_empty_cli(self):
        """Test empty CLI interface."""
        cli = CLIInterface()

        assert cli.framework is None
        assert len(cli.commands) == 0


class TestWebAPIInterface:
    """Tests for Web API interface."""

    def test_api_with_endpoints(self):
        """Test API with endpoints."""
        endpoint = APIEndpoint(
            method="GET",
            path="/api/items",
            description="Get all items",
            file="src/routes/items.py"
        )

        api = WebAPIInterface(
            framework="FastAPI",
            base_path="/api",
            endpoints=[endpoint],
            authentication="JWT"
        )

        assert api.framework == "FastAPI"
        assert api.base_path == "/api"
        assert len(api.endpoints) == 1
        assert api.endpoints[0].method == "GET"
        assert api.authentication == "JWT"

    def test_api_defaults(self):
        """Test API default values."""
        api = WebAPIInterface()

        assert api.base_path == "/"
        assert len(api.endpoints) == 0


class TestRepoFacts:
    """Tests for main RepoFacts class."""

    def test_empty_repo_facts(self):
        """Test creating empty repo facts."""
        facts = create_empty_facts("test-project")

        assert facts.project.name == "test-project"
        assert len(facts.languages) == 0
        assert len(facts.entry_points) == 0
        assert facts.total_files == 0

    def test_repo_facts_with_data(self):
        """Test repo facts with actual data."""
        facts = RepoFacts(
            project=ProjectMetadata(
                name="my-app",
                type=ProjectType.CLI
            ),
            languages=[
                Language(name="Python", file_count=50, primary=True, version="3.11")
            ],
            entry_points=[
                EntryPoint(file="src/main.py", type="main", command="python -m src.main")
            ],
            total_files=50
        )

        assert facts.project.name == "my-app"
        assert facts.project.type == ProjectType.CLI
        assert len(facts.languages) == 1
        assert facts.total_files == 50

    def test_get_primary_language_explicit(self):
        """Test getting explicitly marked primary language."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            languages=[
                Language(name="JavaScript", file_count=20, primary=False),
                Language(name="Python", file_count=50, primary=True),
            ]
        )

        primary = facts.get_primary_language()
        assert primary is not None
        assert primary.name == "Python"

    def test_get_primary_language_by_count(self):
        """Test getting primary language by file count when none marked."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            languages=[
                Language(name="JavaScript", file_count=20),
                Language(name="Python", file_count=50),
            ]
        )

        primary = facts.get_primary_language()
        assert primary is not None
        assert primary.name == "Python"  # Has most files

    def test_get_primary_language_none(self):
        """Test getting primary language when no languages."""
        facts = create_empty_facts("test")

        primary = facts.get_primary_language()
        assert primary is None

    def test_has_interface_true(self):
        """Test has_interface when CLI interface exists."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            interface=ProjectInterface(
                cli=CLIInterface(framework="typer")
            )
        )

        assert facts.has_interface() is True

    def test_has_interface_false(self):
        """Test has_interface when no interface."""
        facts = create_empty_facts("test")

        assert facts.has_interface() is False

    def test_get_interface_type_cli(self):
        """Test getting interface type for CLI."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            interface=ProjectInterface(
                cli=CLIInterface(framework="typer")
            )
        )

        assert facts.get_interface_type() == "CLI"

    def test_get_interface_type_web_api(self):
        """Test getting interface type for Web API."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            interface=ProjectInterface(
                web_api=WebAPIInterface(framework="FastAPI")
            )
        )

        assert facts.get_interface_type() == "Web API"

    def test_get_interface_type_none(self):
        """Test getting interface type when none."""
        facts = create_empty_facts("test")

        assert facts.get_interface_type() is None

    def test_get_install_command_npm(self):
        """Test getting install command for Node.js project."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            languages=[Language(name="JavaScript", file_count=50, primary=True)],
            config_files=[ConfigFile(file="package.json", type="json")]
        )

        assert facts.get_install_command() == "npm install"

    def test_get_install_command_pip(self):
        """Test getting install command for Python project."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            languages=[Language(name="Python", file_count=50, primary=True)],
            config_files=[ConfigFile(file="requirements.txt", type="text")]
        )

        assert facts.get_install_command() == "pip install -r requirements.txt"

    def test_get_install_command_maven(self):
        """Test getting install command for Maven project."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            languages=[Language(name="Java", file_count=50, primary=True)],
            config_files=[ConfigFile(file="pom.xml", type="xml")]
        )

        assert facts.get_install_command() == "mvn install"

    def test_get_install_command_none(self):
        """Test getting install command when can't determine."""
        facts = create_empty_facts("test")

        assert facts.get_install_command() is None

    def test_get_run_command_from_script(self):
        """Test getting run command from npm script."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            languages=[Language(name="JavaScript", file_count=50, primary=True)],
            scripts={
                "start": Script(name="start", command="node index.js")
            }
        )

        assert facts.get_run_command() == "npm run start"

    def test_get_run_command_from_entry_point(self):
        """Test getting run command from entry point."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test"),
            entry_points=[
                EntryPoint(
                    file="src/main.py",
                    type="main",
                    command="python -m src.main"
                )
            ]
        )

        assert facts.get_run_command() == "python -m src.main"

    def test_get_run_command_none(self):
        """Test getting run command when can't determine."""
        facts = create_empty_facts("test")

        assert facts.get_run_command() is None

    def test_to_dict(self):
        """Test converting RepoFacts to dictionary."""
        facts = RepoFacts(
            project=ProjectMetadata(name="test", type=ProjectType.CLI),
            languages=[Language(name="Python", file_count=10, primary=True)],
            total_files=10
        )

        result = facts.to_dict()

        assert isinstance(result, dict)
        assert result["project"]["name"] == "test"
        assert len(result["languages"]) == 1
        assert result["total_files"] == 10


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
