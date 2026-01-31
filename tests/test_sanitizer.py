# tests/test_sanitizer.py
"""
Unit tests for the sanitizer module.

Tests all sanitization functions to ensure:
- Absolute paths are removed/normalized
- Placeholders are detected
- Secrets are redacted
- URLs are properly formatted
- Path separators are fixed
"""

import pytest
from src.sanitizer import (
    Sanitizer,
    PathSanitizer,
    PlaceholderDetector,
    SecretRedactor,
    URLNormalizer,
    PathFormatFixer,
    sanitize_markdown,
    sanitize_facts,
)


class TestPathSanitizer:
    """Tests for PathSanitizer class."""

    def test_normalize_path_basic(self):
        """Test basic path normalization."""
        # Windows style to POSIX
        result = PathSanitizer.normalize_path(r"src\main.py")
        assert result == "src/main.py"

        # Already POSIX
        result = PathSanitizer.normalize_path("src/utils/helper.py")
        assert result == "src/utils/helper.py"

    def test_normalize_path_with_project_root(self, tmp_path):
        """Test path normalization with project root."""
        # Create a test file structure
        project_root = tmp_path / "project"
        project_root.mkdir()
        src_dir = project_root / "src"
        src_dir.mkdir()
        test_file = src_dir / "main.py"
        test_file.write_text("# test")

        # Normalize absolute path to relative
        sanitizer = PathSanitizer()
        result = sanitizer.normalize_path(str(test_file), str(project_root))
        assert result == "src/main.py"

    def test_strip_absolute_paths_windows(self):
        """Test stripping Windows absolute paths."""
        text = "The file is located at D:\\Users\\john\\project\\src\\main.py"
        cleaned, removed = PathSanitizer.strip_absolute_paths(text)

        assert "D:\\Users" not in cleaned
        assert len(removed) > 0
        assert "The file is located at" in cleaned

    def test_strip_absolute_paths_unix(self):
        """Test stripping Unix absolute paths."""
        text = "The file is at /home/user/project/src/main.py and /Users/john/code/app.py"
        cleaned, removed = PathSanitizer.strip_absolute_paths(text)

        assert "/home/user" not in cleaned
        assert "/Users/john" not in cleaned
        assert len(removed) > 0

    def test_strip_absolute_paths_no_paths(self):
        """Test when there are no absolute paths."""
        text = "This is a normal sentence with src/main.py"
        cleaned, removed = PathSanitizer.strip_absolute_paths(text)

        assert cleaned == text
        assert len(removed) == 0


class TestPlaceholderDetector:
    """Tests for PlaceholderDetector class."""

    def test_detect_common_placeholders(self):
        """Test detection of common placeholder patterns."""
        text = "Clone from https://github.com/yourusername/your-repo"
        placeholders = PlaceholderDetector.detect_placeholders(text)

        assert len(placeholders) > 0
        assert any('your' in p.lower() for p in placeholders)

    def test_detect_todo_fixme(self):
        """Test detection of TODO and FIXME."""
        text = "# TODO: Implement this feature\n# FIXME: Bug here"
        placeholders = PlaceholderDetector.detect_placeholders(text)

        assert len(placeholders) >= 2
        assert any('TODO' in p for p in placeholders)
        assert any('FIXME' in p for p in placeholders)

    def test_detect_placeholder_keyword(self):
        """Test detection of 'placeholder' keyword."""
        text = "This is a placeholder for the real content"
        placeholders = PlaceholderDetector.detect_placeholders(text)

        assert len(placeholders) > 0
        assert any('placeholder' in p.lower() for p in placeholders)

    def test_no_false_positives(self):
        """Test that legitimate text doesn't trigger false positives."""
        text = "The repository contains source code for the project"
        placeholders = PlaceholderDetector.detect_placeholders(text)

        # Should not detect 'repo' in 'repository'
        assert len(placeholders) == 0


class TestSecretRedactor:
    """Tests for SecretRedactor class."""

    def test_redact_jwt_tokens(self):
        """Test JWT token redaction."""
        text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.TJVA95OrM7E2cBab"
        redacted, types = SecretRedactor.redact_secrets(text)

        assert "eyJhbGciOiJ" not in redacted
        assert "[REDACTED_JWT]" in redacted
        assert 'jwt' in types

    def test_redact_api_keys(self):
        """Test API key redaction."""
        text = "API_KEY=abc123def456ghi789jkl012mno345pq"
        redacted, types = SecretRedactor.redact_secrets(text)

        assert "abc123def456" not in redacted
        assert "[REDACTED" in redacted

    def test_redact_private_keys(self):
        """Test private key redaction."""
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA..."
        redacted, types = SecretRedactor.redact_secrets(text)

        assert "BEGIN RSA PRIVATE KEY" not in redacted
        assert "[REDACTED_PRIVATE_KEY]" in redacted
        assert 'private_key' in types

    def test_redact_passwords(self):
        """Test password redaction."""
        text = 'password: "mySecretPass123"'
        redacted, types = SecretRedactor.redact_secrets(text)

        assert "mySecretPass123" not in redacted
        assert 'password' in types

    def test_no_secrets(self):
        """Test when there are no secrets."""
        text = "This is a normal piece of documentation"
        redacted, types = SecretRedactor.redact_secrets(text)

        assert redacted == text
        assert len(types) == 0


class TestURLNormalizer:
    """Tests for URLNormalizer class."""

    def test_fix_malformed_url_port_path(self):
        """Test fixing URLs with missing slash between port and path."""
        text = "curl http://localhost:3000items"
        fixed, count = URLNormalizer.fix_malformed_urls(text)

        assert fixed == "curl http://localhost:3000/items"
        assert count == 1

    def test_fix_malformed_url_domain_path(self):
        """Test fixing URLs with missing slash between domain and path."""
        # Note: Domain-path fixing is disabled due to false positive risk
        # We only fix port-path issues which are unambiguous
        text = "Visit http://example.comapi for docs"
        fixed, count = URLNormalizer.fix_malformed_urls(text)

        # Since domain-path fixing is disabled, this won't be fixed
        assert fixed == text
        assert count == 0

    def test_fix_multiple_malformed_urls(self):
        """Test fixing multiple malformed URLs - only port-based."""
        text = "http://localhost:3000items and http://api.example.com:8080users"
        fixed, count = URLNormalizer.fix_malformed_urls(text)

        assert "3000/items" in fixed
        assert "8080/users" in fixed
        assert count == 2

    def test_no_malformed_urls(self):
        """Test when URLs are already correct."""
        text = "http://localhost:3000/items and https://example.com/api"
        fixed, count = URLNormalizer.fix_malformed_urls(text)

        assert fixed == text
        assert count == 0

    def test_normalize_endpoint_express_style(self):
        """Test endpoint normalization to Express style."""
        # Spring to Express
        result = URLNormalizer.normalize_endpoint_format("/api/items/{id}", style="express")
        assert result == "/api/items/:id"

        # Already Express
        result = URLNormalizer.normalize_endpoint_format("/api/items/:id", style="express")
        assert result == "/api/items/:id"

    def test_normalize_endpoint_spring_style(self):
        """Test endpoint normalization to Spring style."""
        # Express to Spring
        result = URLNormalizer.normalize_endpoint_format("/api/items/:id", style="spring")
        assert result == "/api/items/{id}"

        # Already Spring
        result = URLNormalizer.normalize_endpoint_format("/api/items/{id}", style="spring")
        assert result == "/api/items/{id}"

    def test_normalize_endpoint_adds_leading_slash(self):
        """Test that endpoint normalization adds leading slash if missing."""
        result = URLNormalizer.normalize_endpoint_format("api/items", style="express")
        assert result == "/api/items"


class TestPathFormatFixer:
    """Tests for PathFormatFixer class."""

    def test_fix_missing_separators_src(self):
        """Test fixing missing separator after 'src'."""
        text = "The main file is srcindex.js which handles requests"
        fixed, count = PathFormatFixer.fix_missing_separators(text)

        assert fixed == "The main file is src/index.js which handles requests"
        assert count == 1

    def test_fix_missing_separators_multiple_dirs(self):
        """Test fixing multiple directories with missing separators."""
        text = "Files: srcmain.py, appserver.js, utilshelper.py"
        fixed, count = PathFormatFixer.fix_missing_separators(text)

        assert "src/main.py" in fixed
        assert "app/server.js" in fixed
        assert "utils/helper.py" in fixed
        assert count == 3

    def test_fix_controllers_models_views(self):
        """Test fixing common MVC directories."""
        text = "controllersuser.py, modelsitem.py, viewsindex.html"
        fixed, count = PathFormatFixer.fix_missing_separators(text)

        assert "controllers/user.py" in fixed
        assert "models/item.py" in fixed
        assert "views/index.html" in fixed

    def test_no_missing_separators(self):
        """Test when paths already have separators."""
        text = "The file src/index.js is the entry point"
        fixed, count = PathFormatFixer.fix_missing_separators(text)

        assert fixed == text
        assert count == 0


class TestSanitizer:
    """Tests for main Sanitizer class."""

    def test_sanitize_facts_normalizes_paths(self, tmp_path):
        """Test that sanitize_facts normalizes file paths."""
        facts = {
            "project_name": "test-project",
            "files": [
                {
                    "path": r"D:\workspace\project\src\main.py",
                    "summary": "Main entry point"
                }
            ]
        }

        sanitizer = Sanitizer(project_root=str(tmp_path))
        result = sanitizer.sanitize_facts(facts)

        # Path should be normalized (absolute path removed or converted to relative)
        normalized_path = result.sanitized_data["files"][0]["path"]
        assert "D:\\" not in normalized_path or "/" in normalized_path

    def test_sanitize_facts_strips_absolute_paths_from_summaries(self):
        """Test that absolute paths are stripped from summaries."""
        facts = {
            "files": [
                {
                    "path": "src/main.py",
                    "summary": "Located at D:\\workspace\\project\\src\\main.py",
                    "functions": []
                }
            ]
        }

        sanitizer = Sanitizer()
        result = sanitizer.sanitize_facts(facts)

        summary = result.sanitized_data["files"][0]["summary"]
        assert "D:\\workspace" not in summary

    def test_sanitize_facts_detects_placeholders(self):
        """Test that placeholders in facts are detected."""
        facts = {
            "files": [
                {
                    "path": "README.md",
                    "summary": "TODO: Add description for your-project",
                    "functions": []
                }
            ]
        }

        sanitizer = Sanitizer()
        result = sanitizer.sanitize_facts(facts)

        # Should detect placeholder issues
        assert len(result.issues_found) > 0
        assert any('placeholder' in issue.lower() or 'TODO' in issue for issue in result.issues_found)

    def test_sanitize_markdown_removes_absolute_paths(self):
        """Test markdown sanitization removes absolute paths."""
        markdown = """
        # Project

        The main file is located at D:\\Users\\john\\project\\src\\main.py
        """

        sanitizer = Sanitizer()
        result = sanitizer.sanitize_markdown(markdown)

        assert "D:\\Users\\john" not in result.sanitized_data

    def test_sanitize_markdown_fixes_urls(self):
        """Test markdown sanitization fixes malformed URLs."""
        markdown = """
        ## API Endpoints

        - `GET http://localhost:3000items` - Get all items
        """

        sanitizer = Sanitizer()
        result = sanitizer.sanitize_markdown(markdown)

        assert "3000/items" in result.sanitized_data
        assert len(result.fixes_applied) > 0

    def test_sanitize_markdown_detects_placeholders(self):
        """Test markdown sanitization detects placeholders."""
        markdown = """
        # your-project

        Clone from https://github.com/yourusername/your-repo
        """

        sanitizer = Sanitizer()
        result = sanitizer.sanitize_markdown(markdown)

        # Should detect placeholder issues
        assert len(result.issues_found) > 0
        assert any('placeholder' in issue.lower() for issue in result.issues_found)

    def test_sanitize_markdown_redacts_secrets(self):
        """Test markdown sanitization redacts secrets."""
        markdown = """
        ## Configuration

        Set your API key: API_KEY=abc123def456ghi789jkl012mno345pq
        """

        sanitizer = Sanitizer()
        result = sanitizer.sanitize_markdown(markdown)

        assert "abc123def456" not in result.sanitized_data
        assert "[REDACTED" in result.sanitized_data
        assert len(result.fixes_applied) > 0

    def test_sanitize_markdown_fixes_path_separators(self):
        """Test markdown sanitization fixes missing path separators."""
        markdown = """
        ## Structure

        - srcmain.py - Entry point
        - appserver.js - Server
        """

        sanitizer = Sanitizer()
        result = sanitizer.sanitize_markdown(markdown)

        assert "src/main.py" in result.sanitized_data
        assert "app/server.js" in result.sanitized_data


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_sanitize_markdown_function(self):
        """Test sanitize_markdown convenience function."""
        markdown = "File at D:\\workspace\\src\\main.py"
        result = sanitize_markdown(markdown)

        assert "D:\\workspace" not in result

    def test_sanitize_facts_function(self):
        """Test sanitize_facts convenience function."""
        facts = {
            "files": [
                {"path": "src/main.py", "summary": "Main file"}
            ]
        }
        result = sanitize_facts(facts)

        assert "files" in result
        assert len(result["files"]) == 1


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
