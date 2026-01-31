# tests/test_validator.py
"""
Unit tests for the validator module.

Tests validation of README content including:
- Placeholder detection
- Absolute path detection
- Malformed URL detection
- Duplicate heading detection
- Dependency validation
- File reference validation
"""

import pytest
import textwrap
from src.validator import (
    ReadmeValidator,
    ValidationResult,
    ValidationSeverity,
    validate_readme,
)


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_validation_result_initialization(self):
        """Test ValidationResult initialization."""
        result = ValidationResult(passed=True)
        assert result.passed is True
        assert result.error_count == 0
        assert result.warning_count == 0
        assert result.total_issues == 0

    def test_add_error_marks_failed(self):
        """Test that adding an error marks validation as failed."""
        result = ValidationResult(passed=True)
        result.add_error("Test", "Test error")

        assert result.passed is False
        assert result.error_count == 1

    def test_add_warning_keeps_passed(self):
        """Test that adding a warning doesn't change passed status."""
        result = ValidationResult(passed=True)
        result.add_warning("Test", "Test warning")

        assert result.passed is True  # Warnings don't fail
        assert result.warning_count == 1

    def test_get_summary_passed(self):
        """Test summary for passed validation."""
        result = ValidationResult(passed=True)
        summary = result.get_summary()

        assert "PASSED" in summary

    def test_get_summary_failed(self):
        """Test summary for failed validation."""
        result = ValidationResult(passed=True)
        result.add_error("Test", "Error")
        summary = result.get_summary()

        assert "FAILED" in summary
        assert "1 error" in summary


class TestPlaceholderDetection:
    """Tests for placeholder detection."""

    def test_detects_your_repo_placeholder(self):
        """Test detection of 'your-repo' placeholder."""
        markdown = """
        # My Project

        Clone from https://github.com/yourusername/your-repo
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert not result.passed
        assert result.error_count >= 1
        assert any('placeholder' in issue.category.lower() for issue in result.errors)

    def test_detects_todo_placeholder(self):
        """Test detection of TODO placeholder."""
        markdown = """
        # Project

        ## Features

        TODO: Add features here
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert not result.passed
        assert any('TODO' in str(issue) for issue in result.errors)

    def test_detects_multiple_placeholders(self):
        """Test detection of multiple placeholder types."""
        markdown = """
        # your-project

        TODO: Update this
        Email: your-email@example.com
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert result.error_count >= 2  # At least 2 placeholders

    def test_no_false_positives_for_valid_content(self):
        """Test that valid content doesn't trigger placeholder detection."""
        markdown = """
        # Real Project Name

        This is a repository for managing user accounts.
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have placeholder errors
        placeholder_errors = [e for e in result.errors if 'placeholder' in e.category.lower()]
        assert len(placeholder_errors) == 0


class TestAbsolutePathDetection:
    """Tests for absolute path detection."""

    def test_detects_windows_absolute_path(self):
        """Test detection of Windows absolute paths."""
        markdown = """
        # Project

        The main file is located at D:\\Users\\john\\project\\src\\main.py
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert not result.passed
        assert any('absolute path' in issue.category.lower() for issue in result.errors)

    def test_detects_unix_absolute_path(self):
        """Test detection of Unix absolute paths."""
        markdown = """
        # Project

        Configuration: /home/user/project/config.yaml
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert not result.passed
        assert any('absolute path' in issue.category.lower() for issue in result.errors)

    def test_allows_relative_paths(self):
        """Test that relative paths are allowed."""
        markdown = """
        # Project

        Main file: `src/main.py`
        Config: `config/settings.yaml`
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have absolute path errors
        path_errors = [e for e in result.errors if 'absolute path' in e.category.lower()]
        assert len(path_errors) == 0


class TestMalformedURLDetection:
    """Tests for malformed URL detection."""

    def test_detects_missing_slash_after_port(self):
        """Test detection of URLs with missing slash after port."""
        markdown = """
        # API Documentation

        ```bash
        curl http://localhost:3000items
        ```
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert not result.passed
        assert any('malformed url' in issue.category.lower() for issue in result.errors)

    def test_allows_valid_urls(self):
        """Test that valid URLs pass validation."""
        markdown = """
        # API Documentation

        ```bash
        curl http://localhost:3000/items
        curl https://api.example.com/users
        ```
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have malformed URL errors
        url_errors = [e for e in result.errors if 'malformed url' in e.category.lower()]
        assert len(url_errors) == 0


class TestDuplicateHeadingDetection:
    """Tests for duplicate heading detection."""

    def test_detects_duplicate_headings(self):
        """Test detection of duplicate section headings."""
        markdown = textwrap.dedent("""
        # Project

        ## Installation

        Install with npm.

        ## Usage

        Run the app.

        ## Installation

        Or install with yarn.
        """).strip()

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert not result.passed
        assert any('duplicate heading' in issue.category.lower() for issue in result.errors)

    def test_allows_unique_headings(self):
        """Test that unique headings pass validation."""
        markdown = """
        # Project

        ## Installation

        Install instructions here.

        ## Usage

        Usage instructions here.

        ## Development

        Development guide here.
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have duplicate heading errors
        dup_errors = [e for e in result.errors if 'duplicate' in e.category.lower()]
        assert len(dup_errors) == 0


class TestPathSeparatorDetection:
    """Tests for missing path separator detection."""

    def test_detects_missing_path_separator(self):
        """Test detection of missing path separators."""
        markdown = """
        # Project

        Main file: srcmain.py
        Controllers: controllersuser.py
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        assert not result.passed
        assert any('path separator' in issue.category.lower() for issue in result.errors)

    def test_allows_proper_path_separators(self):
        """Test that proper path separators pass validation."""
        markdown = """
        # Project

        Main file: `src/main.py`
        Controllers: `controllers/user.py`
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have path separator errors
        sep_errors = [e for e in result.errors if 'path separator' in e.category.lower()]
        assert len(sep_errors) == 0


class TestDependencyValidation:
    """Tests for dependency section validation."""

    def test_error_when_no_deps_claimed_but_manifest_exists(self):
        """Test error when README claims no deps but manifest exists."""
        markdown = """
        # Project

        ## Dependencies

        No dependencies detected.
        """

        facts = {
            'files': [
                {'path': 'requirements.txt', 'summary': 'Python dependencies'}
            ]
        }

        validator = ReadmeValidator()
        result = validator.validate(markdown, facts)

        assert not result.passed
        assert any('dependencies' in issue.category.lower() for issue in result.errors)

    def test_warning_when_no_dep_section_but_manifest_exists(self):
        """Test warning when no Dependencies section but manifest exists."""
        markdown = """
        # Project

        ## Installation

        Run `npm install`
        """

        facts = {
            'files': [
                {'path': 'package.json', 'summary': 'Node.js dependencies'}
            ]
        }

        validator = ReadmeValidator()
        result = validator.validate(markdown, facts)

        # Should have warning (not error)
        assert any('dependencies' in issue.category.lower() for issue in result.warnings)

    def test_passes_when_deps_section_exists_with_manifest(self):
        """Test validation passes when Dependencies section exists with manifest."""
        markdown = """
        # Project

        ## Dependencies

        - express: ^4.18.0
        - mongoose: ^7.0.0
        """

        facts = {
            'files': [
                {'path': 'package.json', 'summary': 'Node.js dependencies'}
            ]
        }

        validator = ReadmeValidator()
        result = validator.validate(markdown, facts)

        # Should not have dependency errors
        dep_errors = [e for e in result.errors if 'dependencies' in e.category.lower()]
        assert len(dep_errors) == 0


class TestHeadingConsistency:
    """Tests for heading style consistency."""

    def test_warns_on_inconsistent_heading_styles(self):
        """Test warning for inconsistent heading capitalization."""
        markdown = textwrap.dedent("""
        # Project

        ## INSTALLATION

        ## Usage

        ## testing

        ## DEVELOPMENT
        """).strip()

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should have warning about inconsistent styles
        assert any('heading style' in issue.category.lower() for issue in result.warnings)

    def test_no_warning_for_consistent_headings(self):
        """Test no warning when headings are consistent."""
        markdown = """
        # Project

        ## Installation

        ## Usage

        ## Testing

        ## Development
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have heading style warnings
        style_warnings = [w for w in result.warnings if 'heading style' in w.category.lower()]
        assert len(style_warnings) == 0


class TestEmptySectionDetection:
    """Tests for empty section detection."""

    def test_warns_on_empty_sections(self):
        """Test warning for empty sections."""
        markdown = textwrap.dedent("""
        # Project

        ## Installation

        ## Usage

        Run the application with `npm start`
        """).strip()

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should have warning about empty section
        assert any('empty section' in issue.category.lower() for issue in result.warnings)

    def test_no_warning_for_filled_sections(self):
        """Test no warning when sections have content."""
        markdown = """
        # Project

        ## Installation

        Run `npm install` to install dependencies.

        ## Usage

        Run `npm start` to start the application.
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have empty section warnings
        empty_warnings = [w for w in result.warnings if 'empty section' in w.category.lower()]
        assert len(empty_warnings) == 0


class TestBrokenLinkDetection:
    """Tests for broken link detection."""

    def test_warns_on_empty_links(self):
        """Test warning for links with empty URLs."""
        markdown = """
        # Project

        See the [documentation]() for more info.
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should have warning about broken link
        assert any('broken link' in issue.category.lower() for issue in result.warnings)

    def test_no_warning_for_valid_links(self):
        """Test no warning for valid links."""
        markdown = """
        # Project

        See the [documentation](https://example.com/docs) for more info.
        Also check [GitHub](https://github.com/user/repo).
        """

        validator = ReadmeValidator()
        result = validator.validate(markdown)

        # Should not have broken link warnings
        link_warnings = [w for w in result.warnings if 'broken link' in w.category.lower()]
        assert len(link_warnings) == 0


class TestConvenienceFunction:
    """Tests for validate_readme convenience function."""

    def test_validate_readme_function(self):
        """Test validate_readme convenience function."""
        markdown = """
        # Valid Project

        ## Installation

        Install with `pip install -r requirements.txt`
        """

        result = validate_readme(markdown)

        assert isinstance(result, ValidationResult)
        assert result.passed is True


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
