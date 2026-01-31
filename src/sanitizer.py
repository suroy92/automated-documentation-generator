# src/sanitizer.py
"""
Sanitization layer for documentation generator output.

Ensures all generated documentation is safe, correct, and free from:
- Absolute OS paths
- Placeholder text
- Secret patterns
- Malformed URLs
- Inconsistent formatting

This layer operates BEFORE LLM generation to prevent issues at the source.
"""

import re
import logging
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SanitizationResult:
    """Result of sanitization operation."""
    sanitized_data: Any
    issues_found: List[str]
    fixes_applied: List[str]


class PathSanitizer:
    """Sanitizes and normalizes file paths."""

    # Patterns for absolute paths
    WINDOWS_ABS_PATH = re.compile(r'[A-Z]:[\\\/][\w\s\.\-\\\/]+')
    UNIX_ABS_PATH = re.compile(r'/(home|Users|root|var|etc|usr|opt|tmp)/[\w\s\.\-\/]+')

    @staticmethod
    def normalize_path(path: str, project_root: Optional[str] = None) -> str:
        """
        Normalize a file path to repo-relative POSIX style.

        Args:
            path: File path to normalize
            project_root: Project root directory (optional)

        Returns:
            Normalized path (e.g., 'src/main.py')
        """
        if not path:
            return ""

        # Convert to Path object
        p = Path(path)

        # If project_root provided, make relative to it
        if project_root:
            try:
                project_path = Path(project_root).resolve()
                absolute_path = p.resolve()
                p = absolute_path.relative_to(project_path)
            except (ValueError, OSError):
                # Path is not under project_root or doesn't exist
                # Use the path as-is
                pass

        # Convert to POSIX style (forward slashes)
        posix_path = p.as_posix()

        # Remove leading './'
        if posix_path.startswith('./'):
            posix_path = posix_path[2:]

        return posix_path

    @staticmethod
    def strip_absolute_paths(text: str) -> tuple[str, List[str]]:
        """
        Remove absolute paths from text.

        Args:
            text: Text containing potential absolute paths

        Returns:
            Tuple of (cleaned_text, list_of_removed_paths)
        """
        removed = []

        # Find and remove Windows absolute paths
        windows_matches = PathSanitizer.WINDOWS_ABS_PATH.findall(text)
        if windows_matches:
            removed.extend(windows_matches)
            text = PathSanitizer.WINDOWS_ABS_PATH.sub('', text)

        # Find and remove Unix absolute paths
        unix_matches = PathSanitizer.UNIX_ABS_PATH.findall(text)
        if unix_matches:
            removed.extend([match[0] for match in unix_matches])  # match is a tuple from group
            text = PathSanitizer.UNIX_ABS_PATH.sub('', text)

        # Clean up double spaces left by removal
        text = re.sub(r'\s{2,}', ' ', text)

        return text, removed


class PlaceholderDetector:
    """Detects and flags placeholder text."""

    PLACEHOLDER_PATTERNS = [
        r'\byour[_-]?repo\b',
        r'\byour[_-]?username\b',
        r'\byour[_-]?project\b',
        r'\byour[_-]?name\b',
        r'\byour[_-]?email\b',
        r'\byour[_-]?organization\b',
        r'\bTODO\b',
        r'\bFIXME\b',
        r'\bXXX\b',
        r'\bplaceholder\b',
        r'\bexample\.com\b',
        r'\bfoo\b',
        r'\bbar\b',
        r'\[INSERT.*?\]',
        r'\[REPLACE.*?\]',
    ]

    @staticmethod
    def detect_placeholders(text: str) -> List[str]:
        """
        Detect placeholder patterns in text.

        Args:
            text: Text to check

        Returns:
            List of detected placeholder patterns
        """
        detected = []

        for pattern in PlaceholderDetector.PLACEHOLDER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detected.extend(matches)

        return detected


class SecretRedactor:
    """Redacts secrets and sensitive information."""

    SECRET_PATTERNS = {
        'env_var': re.compile(r'[A-Z_]{3,}=[^\s\n]{10,}'),  # Environment variables
        'jwt': re.compile(r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}'),
        'api_key': re.compile(r'\b[A-Za-z0-9]{32,}\b'),  # Generic API keys
        'private_key': re.compile(r'-----BEGIN (?:RSA )?PRIVATE KEY-----'),
        'aws_key': re.compile(r'AKIA[0-9A-Z]{16}'),
        'password': re.compile(r'(?:password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{6,})["\']?', re.IGNORECASE),
    }

    @staticmethod
    def redact_secrets(text: str) -> tuple[str, List[str]]:
        """
        Redact secrets from text.

        Args:
            text: Text potentially containing secrets

        Returns:
            Tuple of (redacted_text, list_of_secret_types_found)
        """
        found_types = []

        for secret_type, pattern in SecretRedactor.SECRET_PATTERNS.items():
            if pattern.search(text):
                found_types.append(secret_type)
                text = pattern.sub(f'[REDACTED_{secret_type.upper()}]', text)

        return text, found_types


class URLNormalizer:
    """Normalizes and validates URLs."""

    @staticmethod
    def fix_malformed_urls(text: str) -> tuple[str, int]:
        """
        Fix common malformed URL patterns.

        Fixes:
        - http://localhost:3000items -> http://localhost:3000/items
        - http://example.comapi -> http://example.com/api

        Args:
            text: Text containing URLs

        Returns:
            Tuple of (fixed_text, count_of_fixes)
        """
        fixes = 0

        # Fix missing slash between port and path
        def fix_port_path(match):
            nonlocal fixes
            fixes += 1
            return f"{match.group(1)}/{match.group(2)}"

        text = re.sub(
            r'(https?://[a-zA-Z0-9\.\-]+:\d+)([a-zA-Z])',
            fix_port_path,
            text
        )

        # Fix missing slash between domain and path
        # Match when TLD is directly followed by a word (indicating missing slash)
        # DO NOT use this fix - it's too prone to false positives
        # Instead, we'll be more conservative and only fix the most common case: port+path
        # Commented out to avoid breaking valid URLs

        # def fix_domain_path(match):
        #     nonlocal fixes
        #     fixes += 1
        #     return f"{match.group(1)}/{match.group(2)}"
        #
        # text = re.sub(
        #     r'(https?://[a-zA-Z0-9\.\-]+\.(?:com|org|net))([a-z]+)',
        #     fix_domain_path,
        #     text
        # )

        return text, fixes

    @staticmethod
    def normalize_endpoint_format(endpoint: str, style: str = 'express') -> str:
        """
        Normalize API endpoint format.

        Args:
            endpoint: Endpoint path (e.g., '/api/items/:id')
            style: Format style ('express' for :id, 'spring' for {id})

        Returns:
            Normalized endpoint
        """
        # Ensure leading slash
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint

        # Normalize parameter style
        if style == 'express':
            # Convert {id} to :id
            endpoint = re.sub(r'\{(\w+)\}', r':\1', endpoint)
        elif style == 'spring':
            # Convert :id to {id}
            endpoint = re.sub(r':(\w+)', r'{\1}', endpoint)

        return endpoint


class PathFormatFixer:
    """Fixes common path formatting issues."""

    @staticmethod
    def fix_missing_separators(text: str) -> tuple[str, int]:
        """
        Fix paths with missing separators (e.g., srcindex.js -> src/index.js).

        Args:
            text: Text containing file paths

        Returns:
            Tuple of (fixed_text, count_of_fixes)
        """
        fixes = 0

        # Common directory names that should have separators after them
        dir_names = [
            'src', 'app', 'lib', 'dist', 'build', 'public', 'static',
            'controllers', 'models', 'views', 'routes', 'services',
            'components', 'utils', 'helpers', 'middleware', 'config',
            'tests', 'test', 'docs', 'assets', 'styles', 'images'
        ]

        for dir_name in dir_names:
            # Match directory name immediately followed by lowercase letter (no separator)
            pattern = rf'\b({dir_name})([a-z])'
            matches = len(re.findall(pattern, text, re.IGNORECASE))
            if matches > 0:
                fixes += matches
                text = re.sub(pattern, rf'\1/\2', text, flags=re.IGNORECASE)

        return text, fixes


class Sanitizer:
    """
    Main sanitizer class for documentation generator.

    Provides two main sanitization modes:
    1. Sanitize facts (LADOM data) before LLM generation
    2. Sanitize markdown output after LLM generation
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize sanitizer.

        Args:
            project_root: Project root directory for path normalization
        """
        self.project_root = project_root

    def sanitize_facts(self, facts: Dict[str, Any]) -> SanitizationResult:
        """
        Sanitize LADOM facts data before LLM generation.

        This is the PRIMARY sanitization layer - cleans data at source.

        Args:
            facts: LADOM data dictionary

        Returns:
            SanitizationResult with sanitized data
        """
        issues = []
        fixes = []
        sanitized = self._deep_copy_dict(facts)

        # Sanitize all file paths in the data
        if 'files' in sanitized:
            for file_data in sanitized['files']:
                # Normalize file path
                if 'path' in file_data:
                    original = file_data['path']
                    normalized = PathSanitizer.normalize_path(original, self.project_root)
                    if original != normalized:
                        file_data['path'] = normalized
                        fixes.append(f"Normalized path: {original[:50]}... -> {normalized}")

                # Sanitize content fields
                for field in ['summary', 'docstring']:
                    if field in file_data and file_data[field]:
                        cleaned, removed = PathSanitizer.strip_absolute_paths(file_data[field])
                        if removed:
                            file_data[field] = cleaned
                            issues.append(f"Removed absolute path from {field}")

                        # Check for placeholders
                        placeholders = PlaceholderDetector.detect_placeholders(file_data[field])
                        if placeholders:
                            issues.append(f"Placeholder detected in {field}: {placeholders[0]}")

                # Sanitize functions
                for func in file_data.get('functions', []):
                    self._sanitize_code_element(func, issues, fixes)

                # Sanitize classes
                for cls in file_data.get('classes', []):
                    self._sanitize_code_element(cls, issues, fixes)

                    # Sanitize methods within classes
                    for method in cls.get('methods', []):
                        self._sanitize_code_element(method, issues, fixes)

        logger.info(f"Fact sanitization complete: {len(fixes)} fixes, {len(issues)} issues")

        return SanitizationResult(
            sanitized_data=sanitized,
            issues_found=issues,
            fixes_applied=fixes
        )

    def sanitize_markdown(self, markdown: str) -> SanitizationResult:
        """
        Sanitize generated markdown output.

        This is the SECONDARY sanitization layer - final cleanup.

        Args:
            markdown: Generated markdown content

        Returns:
            SanitizationResult with sanitized markdown
        """
        issues = []
        fixes = []
        sanitized = markdown

        # 1. Strip absolute paths
        sanitized, removed_paths = PathSanitizer.strip_absolute_paths(sanitized)
        if removed_paths:
            fixes.append(f"Removed {len(removed_paths)} absolute paths")
            logger.warning(f"Absolute paths found in markdown: {removed_paths[:3]}")

        # 2. Fix malformed URLs
        sanitized, url_fixes = URLNormalizer.fix_malformed_urls(sanitized)
        if url_fixes > 0:
            fixes.append(f"Fixed {url_fixes} malformed URLs")

        # 3. Fix missing path separators
        sanitized, separator_fixes = PathFormatFixer.fix_missing_separators(sanitized)
        if separator_fixes > 0:
            fixes.append(f"Fixed {separator_fixes} path separators")

        # 4. Detect placeholders (fail if found)
        placeholders = PlaceholderDetector.detect_placeholders(sanitized)
        if placeholders:
            issues.append(f"Placeholders detected: {set(placeholders)}")
            logger.error(f"Placeholder text found in output: {placeholders[:5]}")

        # 5. Redact secrets
        sanitized, secret_types = SecretRedactor.redact_secrets(sanitized)
        if secret_types:
            fixes.append(f"Redacted secrets: {', '.join(secret_types)}")
            logger.warning(f"Secrets redacted from markdown: {secret_types}")

        # 6. Clean up whitespace
        # Remove multiple blank lines (max 2 consecutive)
        sanitized = re.sub(r'\n{4,}', '\n\n\n', sanitized)

        # Remove trailing whitespace from lines
        sanitized = re.sub(r'[ \t]+$', '', sanitized, flags=re.MULTILINE)

        logger.info(f"Markdown sanitization complete: {len(fixes)} fixes, {len(issues)} issues")

        return SanitizationResult(
            sanitized_data=sanitized,
            issues_found=issues,
            fixes_applied=fixes
        )

    def _sanitize_code_element(self, element: Dict[str, Any], issues: List[str], fixes: List[str]) -> None:
        """Sanitize a code element (function, class, method)."""
        # Check description/docstring
        for field in ['description', 'docstring', 'summary']:
            if field in element and element[field]:
                # Strip absolute paths
                cleaned, removed = PathSanitizer.strip_absolute_paths(element[field])
                if removed:
                    element[field] = cleaned
                    fixes.append(f"Removed path from {element.get('name', 'element')} {field}")

                # Check for placeholders
                placeholders = PlaceholderDetector.detect_placeholders(element[field])
                if placeholders:
                    issues.append(f"Placeholder in {element.get('name', 'element')}: {placeholders[0]}")

    def _deep_copy_dict(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy a dictionary (simplified version)."""
        import copy
        return copy.deepcopy(d)


# Convenience functions for easy import

def sanitize_markdown(markdown: str, project_root: Optional[str] = None) -> str:
    """
    Sanitize markdown content.

    Args:
        markdown: Markdown content
        project_root: Project root for path normalization

    Returns:
        Sanitized markdown
    """
    sanitizer = Sanitizer(project_root)
    result = sanitizer.sanitize_markdown(markdown)

    if result.issues_found:
        logger.warning(f"Sanitization found {len(result.issues_found)} issues")

    return result.sanitized_data


def sanitize_facts(facts: Dict[str, Any], project_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Sanitize LADOM facts data.

    Args:
        facts: LADOM data
        project_root: Project root for path normalization

    Returns:
        Sanitized facts
    """
    sanitizer = Sanitizer(project_root)
    result = sanitizer.sanitize_facts(facts)

    if result.issues_found:
        logger.warning(f"Fact sanitization found {len(result.issues_found)} issues")

    return result.sanitized_data
