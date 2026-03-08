"""
Integration tests for Python projects.

Tests the documentation generator against 4 Python sample projects:
- python-cli-typer: CLI tool with Typer framework
- python-library: Reusable Python package
- grpc-python: gRPC service
- sample-python-app: FastAPI web application
"""

import pytest
from pathlib import Path
from src.repo_facts import ProjectType


class TestPythonCLITyper:
    """Tests for python-cli-typer project (CLI tool with Typer)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to python-cli-typer project."""
        return samples_dir / "python-cli-typer"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from python-cli-typer project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"
        assert project_path.is_dir(), f"Project path is not a directory: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as CLI."""
        pytest.assert_project_type(
            facts,
            ProjectType.CLI,
            "python-cli-typer should be detected as CLI project"
        )

    def test_primary_language(self, facts):
        """Test that Python is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "Python",
            "python-cli-typer is a Python project"
        )

    def test_has_cli_interface(self, facts):
        """Test that CLI interface is detected."""
        pytest.assert_has_interface(
            facts,
            "CLI",
            "python-cli-typer should have CLI interface"
        )

    def test_cli_framework_detection(self, facts):
        """Test that Typer framework is detected."""
        assert facts.interface.cli is not None, "CLI interface should be present"
        assert facts.interface.cli.framework == "Typer", (
            f"Expected Typer framework, got {facts.interface.cli.framework}"
        )

    def test_has_dependencies(self, facts):
        """Test that dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        # Check for Typer specifically
        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]
        assert "typer" in dep_names, "Typer should be in runtime dependencies"

    def test_has_entry_points(self, facts):
        """Test that entry points are detected."""
        pytest.assert_has_entry_points(facts, min_count=1)

    def test_has_config_files(self, facts):
        """Test that config files are detected."""
        assert len(facts.config_files) > 0, "Should have config files"

        # Should have pyproject.toml
        config_names = [cf.file for cf in facts.config_files]
        assert any("pyproject.toml" in name for name in config_names), (
            "Should detect pyproject.toml"
        )


class TestPythonLibrary:
    """Tests for python-library project (reusable package)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to python-library project."""
        return samples_dir / "python-library"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from python-library project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Library."""
        pytest.assert_project_type(
            facts,
            ProjectType.LIBRARY,
            "python-library should be detected as Library project"
        )

    def test_primary_language(self, facts):
        """Test that Python is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "Python",
            "python-library is a Python project"
        )

    def test_no_interface(self, facts):
        """Test that library has no interface (it's imported, not run)."""
        # Libraries typically don't have user-facing interfaces
        interface_type = facts.get_interface_type()
        # May be None or undetected - both are acceptable for a library
        # We just verify it's not CLI or Web API
        if interface_type is not None:
            assert interface_type not in ["CLI", "Web API"], (
                "Library should not have CLI or Web API interface"
            )

    def test_has_dependencies(self, facts):
        """Test that dev dependencies are detected (pytest)."""
        # Libraries often have dev dependencies for testing
        dev_deps = facts.dependencies.get("dev", [])
        assert len(dev_deps) > 0, "Should have dev dependencies"

        dep_names = [dep.name.lower() for dep in dev_deps]
        assert "pytest" in dep_names, "Should have pytest in dev dependencies"

    def test_has_test_info(self, facts):
        """Test that testing info is detected."""
        assert facts.testing.framework is not None, "Should detect test framework"
        assert facts.testing.framework.lower() == "pytest", (
            f"Expected pytest, got {facts.testing.framework}"
        )


class TestGRPCPython:
    """Tests for grpc-python project (gRPC service)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to grpc-python project."""
        return samples_dir / "grpc-python"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from grpc-python project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as gRPC Service."""
        pytest.assert_project_type(
            facts,
            ProjectType.GRPC_SERVICE,
            "grpc-python should be detected as gRPC Service"
        )

    def test_primary_language(self, facts):
        """Test that Python is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "Python",
            "grpc-python is a Python project"
        )

    def test_has_grpc_dependencies(self, facts):
        """Test that gRPC dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have grpc-related dependencies
        grpc_deps = [d for d in dep_names if "grpc" in d]
        assert len(grpc_deps) > 0, "Should have gRPC dependencies"

    def test_has_entry_points(self, facts):
        """Test that server/client entry points are detected."""
        pytest.assert_has_entry_points(facts, min_count=1)


class TestSamplePythonApp:
    """Tests for sample-python-app project (FastAPI web application)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to sample-python-app project."""
        return samples_dir / "sample-python-app"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from sample-python-app project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Web API."""
        pytest.assert_project_type(
            facts,
            ProjectType.WEB_API,
            "sample-python-app should be detected as Web API"
        )

    def test_primary_language(self, facts):
        """Test that Python is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "Python",
            "sample-python-app is a Python project"
        )

    def test_has_web_api_interface(self, facts):
        """Test that Web API interface is detected."""
        pytest.assert_has_interface(
            facts,
            "Web API",
            "sample-python-app should have Web API interface"
        )

    def test_fastapi_framework_detection(self, facts):
        """Test that FastAPI framework is detected."""
        assert facts.interface.web_api is not None, "Web API interface should be present"
        assert facts.interface.web_api.framework == "FastAPI", (
            f"Expected FastAPI framework, got {facts.interface.web_api.framework}"
        )

    def test_has_dependencies(self, facts):
        """Test that FastAPI dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have FastAPI
        assert "fastapi" in dep_names, "Should have FastAPI in dependencies"

    def test_has_entry_points(self, facts):
        """Test that API entry points are detected."""
        pytest.assert_has_entry_points(facts, min_count=1)

    def test_architecture_detection(self, facts):
        """Test that architecture is detected (likely layered with services/repos)."""
        assert facts.architecture is not None, "Should detect architecture"
        # FastAPI projects often use layered architecture
        assert facts.architecture.pattern is not None, "Should detect architecture pattern"
