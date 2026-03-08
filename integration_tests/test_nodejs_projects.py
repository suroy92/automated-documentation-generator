"""
Integration tests for Node.js and TypeScript projects.

Tests the documentation generator against 6 Node.js/TypeScript sample projects:
- node-cli-commander: CLI tool with Commander.js
- sample-nodejs-ts-app: Express API (TypeScript)
- sample-nodejs-js-app: Express API (JavaScript)
- frontend-vite-react-ts: React frontend with Vite
- electron-desktop-ts: Electron desktop app
- vscode-extension-ts: VSCode extension
"""

import pytest
from pathlib import Path
from src.repo_facts import ProjectType


class TestNodeCLICommander:
    """Tests for node-cli-commander project (CLI tool with Commander.js)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to node-cli-commander project."""
        return samples_dir / "node-cli-commander"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from node-cli-commander project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as CLI."""
        pytest.assert_project_type(
            facts,
            ProjectType.CLI,
            "node-cli-commander should be detected as CLI project"
        )

    def test_primary_language(self, facts):
        """Test that JavaScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "JavaScript",
            "node-cli-commander is a JavaScript project"
        )

    def test_has_cli_interface(self, facts):
        """Test that CLI interface is detected."""
        pytest.assert_has_interface(
            facts,
            "CLI",
            "node-cli-commander should have CLI interface"
        )

    def test_has_dependencies(self, facts):
        """Test that dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have commander
        assert "commander" in dep_names, "Should have Commander in dependencies"

    def test_has_package_json(self, facts):
        """Test that package.json is detected."""
        config_names = [cf.file for cf in facts.config_files]
        assert any("package.json" in name for name in config_names), (
            "Should detect package.json"
        )


class TestSampleNodejsTSApp:
    """Tests for sample-nodejs-ts-app project (Express API with TypeScript)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to sample-nodejs-ts-app project."""
        return samples_dir / "sample-nodejs-ts-app"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from sample-nodejs-ts-app project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Web API."""
        pytest.assert_project_type(
            facts,
            ProjectType.WEB_API,
            "sample-nodejs-ts-app should be detected as Web API"
        )

    def test_primary_language(self, facts):
        """Test that TypeScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "TypeScript",
            "sample-nodejs-ts-app is a TypeScript project"
        )

    def test_has_web_api_interface(self, facts):
        """Test that Web API interface is detected."""
        pytest.assert_has_interface(
            facts,
            "Web API",
            "sample-nodejs-ts-app should have Web API interface"
        )

    def test_express_framework_detection(self, facts):
        """Test that Express framework is detected."""
        assert facts.interface.web_api is not None, "Web API interface should be present"
        assert facts.interface.web_api.framework == "Express", (
            f"Expected Express framework, got {facts.interface.web_api.framework}"
        )

    def test_has_dependencies(self, facts):
        """Test that Express dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have express
        assert "express" in dep_names, "Should have Express in dependencies"

    def test_has_typescript_config(self, facts):
        """Test that tsconfig.json is detected."""
        config_names = [cf.file for cf in facts.config_files]
        assert any("tsconfig.json" in name for name in config_names), (
            "Should detect tsconfig.json"
        )


class TestSampleNodejsJSApp:
    """Tests for sample-nodejs-js-app project (Express API with JavaScript)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to sample-nodejs-js-app project."""
        return samples_dir / "sample-nodejs-js-app"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from sample-nodejs-js-app project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Web API."""
        pytest.assert_project_type(
            facts,
            ProjectType.WEB_API,
            "sample-nodejs-js-app should be detected as Web API"
        )

    def test_primary_language(self, facts):
        """Test that JavaScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "JavaScript",
            "sample-nodejs-js-app is a JavaScript project"
        )

    def test_has_web_api_interface(self, facts):
        """Test that Web API interface is detected."""
        pytest.assert_has_interface(
            facts,
            "Web API",
            "sample-nodejs-js-app should have Web API interface"
        )


class TestFrontendViteReactTS:
    """Tests for frontend-vite-react-ts project (React frontend with Vite)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to frontend-vite-react-ts project."""
        return samples_dir / "frontend-vite-react-ts"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from frontend-vite-react-ts project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Frontend."""
        pytest.assert_project_type(
            facts,
            ProjectType.FRONTEND,
            "frontend-vite-react-ts should be detected as Frontend project"
        )

    def test_primary_language(self, facts):
        """Test that TypeScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "TypeScript",
            "frontend-vite-react-ts is a TypeScript project"
        )

    def test_has_dependencies(self, facts):
        """Test that React dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have React
        assert "react" in dep_names, "Should have React in dependencies"

    def test_has_vite_config(self, facts):
        """Test that vite config is detected."""
        config_names = [cf.file for cf in facts.config_files]
        # May be vite.config.ts or vite.config.js
        assert any("vite.config" in name for name in config_names), (
            "Should detect vite.config"
        )


class TestElectronDesktopTS:
    """Tests for electron-desktop-ts project (Electron desktop app)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to electron-desktop-ts project."""
        return samples_dir / "electron-desktop-ts"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from electron-desktop-ts project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Desktop."""
        pytest.assert_project_type(
            facts,
            ProjectType.DESKTOP,
            "electron-desktop-ts should be detected as Desktop project"
        )

    def test_primary_language(self, facts):
        """Test that TypeScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "TypeScript",
            "electron-desktop-ts is a TypeScript project"
        )

    def test_has_electron_dependencies(self, facts):
        """Test that Electron dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

        runtime_deps = facts.dependencies.get("runtime", [])
        dep_names = [dep.name.lower() for dep in runtime_deps]

        # Should have electron
        assert "electron" in dep_names, "Should have Electron in dependencies"


class TestVSCodeExtensionTS:
    """Tests for vscode-extension-ts project (VSCode extension)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to vscode-extension-ts project."""
        return samples_dir / "vscode-extension-ts"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from vscode-extension-ts project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Extension."""
        pytest.assert_project_type(
            facts,
            ProjectType.EXTENSION,
            "vscode-extension-ts should be detected as Extension project"
        )

    def test_primary_language(self, facts):
        """Test that TypeScript is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "TypeScript",
            "vscode-extension-ts is a TypeScript project"
        )

    def test_has_dependencies(self, facts):
        """Test that VSCode dependencies are detected."""
        # VSCode extensions typically only have devDependencies
        # (@types/vscode, typescript, etc.) since the VSCode API is provided by the engine
        pytest.assert_has_dependencies(facts, "dev", min_count=1)

        dev_deps = facts.dependencies.get("dev", [])
        dep_names = [dep.name.lower() for dep in dev_deps]

        # Should have @types/vscode as a dev dependency
        vscode_deps = [d for d in dep_names if "vscode" in d]
        assert len(vscode_deps) > 0, "Should have VSCode-related dependencies"
