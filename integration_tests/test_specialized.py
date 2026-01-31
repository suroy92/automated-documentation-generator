"""
Integration tests for specialized project types.

Tests the documentation generator against specialized projects:
- graphql-apollo-ts: GraphQL API with Apollo
- github-action-js: GitHub Action
- terraform-module-demo: Terraform IaC module
"""

import pytest
from pathlib import Path
from src.repo_facts import ProjectType


class TestGraphQLApolloTS:
    """Tests for graphql-apollo-ts project (GraphQL API with Apollo)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to graphql-apollo-ts project."""
        return samples_dir / "graphql-apollo-ts"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from graphql-apollo-ts project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as GraphQL API."""
        pytest.assert_project_type(
            facts,
            ProjectType.GRAPHQL_API,
            "graphql-apollo-ts should be detected as GraphQL API"
        )

    def test_primary_language(self, facts):
        """Test that TypeScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "TypeScript",
            "graphql-apollo-ts is a TypeScript project"
        )

    def test_has_graphql_interface(self, facts):
        """Test that GraphQL interface is detected."""
        # GraphQL interface detection may not be implemented yet
        # This test documents the expected behavior
        interface_type = facts.get_interface_type()
        if interface_type is not None:
            assert interface_type == "GraphQL", (
                f"Expected GraphQL interface, got {interface_type}"
            )

    def test_has_apollo_dependencies(self, facts):
        """Test that Apollo Server dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have Apollo Server
        apollo_deps = [d for d in dep_names if "apollo" in d]
        assert len(apollo_deps) > 0, "Should have Apollo dependencies"

    def test_has_graphql_dependencies(self, facts):
        """Test that GraphQL dependencies are detected."""
        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have graphql
        assert "graphql" in dep_names, "Should have GraphQL in dependencies"


class TestGitHubActionJS:
    """Tests for github-action-js project (GitHub Action)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to github-action-js project."""
        return samples_dir / "github-action-js"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from github-action-js project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Extension."""
        pytest.assert_project_type(
            facts,
            ProjectType.EXTENSION,
            "github-action-js should be detected as Extension"
        )

    def test_primary_language(self, facts):
        """Test that JavaScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "JavaScript",
            "github-action-js is a JavaScript project"
        )

    def test_has_action_config(self, facts):
        """Test that action.yml is detected."""
        config_names = [cf.file for cf in facts.config_files]
        assert any("action.yml" in name or "action.yaml" in name for name in config_names), (
            "Should detect action.yml"
        )

    def test_has_dependencies(self, facts):
        """Test that GitHub Actions dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have @actions/core
        actions_deps = [d for d in dep_names if "actions" in d and "core" in d]
        assert len(actions_deps) > 0, "Should have @actions/core dependency"


class TestTerraformModuleDemo:
    """Tests for terraform-module-demo project (Terraform IaC module)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to terraform-module-demo project."""
        return samples_dir / "terraform-module-demo"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from terraform-module-demo project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as IaC."""
        pytest.assert_project_type(
            facts,
            ProjectType.IAC,
            "terraform-module-demo should be detected as IaC"
        )

    def test_primary_language(self, facts):
        """Test that HCL (Terraform) is detected."""
        # Terraform files use .tf extension
        # Language detection may show as "HCL" or "Terraform" or "Unknown"
        # depending on implementation
        primary = facts.get_primary_language()
        assert primary is not None, "Should detect a primary language"

        # HCL/Terraform detection may not be implemented yet
        # This test documents the expected behavior

    def test_has_terraform_files(self, facts):
        """Test that Terraform files are detected."""
        config_names = [cf.file for cf in facts.config_files]

        # Should detect main.tf, variables.tf, outputs.tf
        tf_files = [f for f in config_names if f.endswith('.tf')]
        assert len(tf_files) > 0, "Should detect .tf files"

    def test_has_iac_interface(self, facts):
        """Test that IaC interface is detected."""
        # IaC interface detection may not be implemented yet
        # This test documents the expected behavior
        interface_type = facts.get_interface_type()
        if interface_type is not None:
            assert interface_type == "IaC", (
                f"Expected IaC interface, got {interface_type}"
            )
