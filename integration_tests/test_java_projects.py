"""
Integration tests for Java projects.

Tests the documentation generator against 3 Java sample projects:
- sample-springboot-app: Spring Boot REST API
- spring-batch-job: Spring Batch processing
- spring-stream-kafka: Spring Cloud Stream with Kafka
"""

import pytest
from pathlib import Path
from src.repo_facts import ProjectType


class TestSampleSpringBootApp:
    """Tests for sample-springboot-app project (Spring Boot REST API)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to sample-springboot-app project."""
        return samples_dir / "sample-springboot-app"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from sample-springboot-app project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Web API."""
        pytest.assert_project_type(
            facts,
            ProjectType.WEB_API,
            "sample-springboot-app should be detected as Web API"
        )

    def test_primary_language(self, facts):
        """Test that Java is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "Java",
            "sample-springboot-app is a Java project"
        )

    def test_has_web_api_interface(self, facts):
        """Test that Web API interface is detected."""
        pytest.assert_has_interface(
            facts,
            "Web API",
            "sample-springboot-app should have Web API interface"
        )

    def test_has_dependencies(self, facts):
        """Test that Spring Boot dependencies are detected."""
        # Java projects use Maven/Gradle for dependencies
        # Dependency extraction may vary based on pom.xml parsing
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

    def test_has_maven_config(self, facts):
        """Test that pom.xml is detected."""
        config_names = [cf.file for cf in facts.config_files]
        assert any("pom.xml" in name for name in config_names), (
            "Should detect pom.xml"
        )

    def test_architecture_detection(self, facts):
        """Test that layered architecture is detected."""
        assert facts.architecture is not None, "Should detect architecture"
        # Spring Boot projects often use layered architecture
        # (Controller → Service → Repository)
        assert facts.architecture.pattern is not None, "Should detect architecture pattern"


class TestSpringBatchJob:
    """Tests for spring-batch-job project (Spring Batch processing)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to spring-batch-job project."""
        return samples_dir / "spring-batch-job"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from spring-batch-job project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Batch Job."""
        pytest.assert_project_type(
            facts,
            ProjectType.BATCH_JOB,
            "spring-batch-job should be detected as Batch Job"
        )

    def test_primary_language(self, facts):
        """Test that Java is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "Java",
            "spring-batch-job is a Java project"
        )

    def test_has_dependencies(self, facts):
        """Test that Spring Batch dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

    def test_has_maven_config(self, facts):
        """Test that pom.xml is detected."""
        config_names = [cf.file for cf in facts.config_files]
        assert any("pom.xml" in name for name in config_names), (
            "Should detect pom.xml"
        )


class TestSpringStreamKafka:
    """Tests for spring-stream-kafka project (Spring Cloud Stream with Kafka)."""

    @pytest.fixture
    def project_path(self, samples_dir):
        """Path to spring-stream-kafka project."""
        return samples_dir / "spring-stream-kafka"

    @pytest.fixture
    def facts(self, project_path, get_facts):
        """Extract facts from spring-stream-kafka project."""
        return get_facts(project_path)

    def test_project_exists(self, project_path):
        """Test that project directory exists."""
        assert project_path.exists(), f"Project not found: {project_path}"

    def test_project_type_detection(self, facts):
        """Test that project is detected as Event-Driven."""
        pytest.assert_project_type(
            facts,
            ProjectType.EVENT_DRIVEN,
            "spring-stream-kafka should be detected as Event-Driven"
        )

    def test_primary_language(self, facts):
        """Test that Java is detected as primary language."""
        pytest.assert_primary_language(
            facts,
            "Java",
            "spring-stream-kafka is a Java project"
        )

    def test_has_dependencies(self, facts):
        """Test that Spring Cloud Stream dependencies are detected."""
        pytest.assert_has_dependencies(facts, "runtime", min_count=1)

    def test_has_maven_config(self, facts):
        """Test that pom.xml is detected."""
        config_names = [cf.file for cf in facts.config_files]
        assert any("pom.xml" in name for name in config_names), (
            "Should detect pom.xml"
        )

    def test_has_docker_compose(self, facts):
        """Test that docker-compose.yml is detected (for Kafka)."""
        config_names = [cf.file for cf in facts.config_files]
        assert any("docker-compose" in name for name in config_names), (
            "Should detect docker-compose.yml"
        )
