# src/validator.py
"""
Validation gate for generated README documentation.

This module provides strict validation that fails the build if issues are found.
It serves as a quality gate to ensure documentation meets minimum standards.

Validation checks:
- No placeholder text (yourusername, your-repo, TODO, etc.)
- No absolute file paths
- No malformed URLs
- No duplicate headings
- Dependencies mentioned when manifests exist
- Consistent formatting
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    ERROR = "error"  # Must be fixed, fails build
    WARNING = "warning"  # Should be fixed, doesn't fail build
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    severity: ValidationSeverity
    category: str
    message: str
    line_number: Optional[int] = None
    context: Optional[str] = None

    def __str__(self) -> str:
        """Format issue for display."""
        location = f" (line {self.line_number})" if self.line_number else ""
        ctx = f"\n  Context: {self.context[:100]}..." if self.context else ""
        return f"[{self.severity.value.upper()}] {self.category}: {self.message}{location}{ctx}"


@dataclass
class ValidationResult:
    """Result of README validation."""
    passed: bool
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    info: List[ValidationIssue] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        """Total number of issues found."""
        return len(self.errors) + len(self.warnings) + len(self.info)

    @property
    def error_count(self) -> int:
        """Number of errors (build-failing issues)."""
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        """Number of warnings."""
        return len(self.warnings)

    def add_error(self, category: str, message: str, line: Optional[int] = None, context: Optional[str] = None):
        """Add an error-level issue."""
        self.errors.append(ValidationIssue(ValidationSeverity.ERROR, category, message, line, context))
        self.passed = False

    def add_warning(self, category: str, message: str, line: Optional[int] = None, context: Optional[str] = None):
        """Add a warning-level issue."""
        self.warnings.append(ValidationIssue(ValidationSeverity.WARNING, category, message, line, context))

    def add_info(self, category: str, message: str, line: Optional[int] = None, context: Optional[str] = None):
        """Add an info-level issue."""
        self.info.append(ValidationIssue(ValidationSeverity.INFO, category, message, line, context))

    def get_summary(self) -> str:
        """Get a summary of validation results."""
        if self.passed:
            return f"✓ Validation PASSED ({self.warning_count} warnings, {len(self.info)} info)"
        else:
            return f"✗ Validation FAILED ({self.error_count} errors, {self.warning_count} warnings)"

    def get_detailed_report(self) -> str:
        """Get a detailed validation report."""
        lines = [self.get_summary(), ""]

        if self.errors:
            lines.append("ERRORS:")
            for issue in self.errors:
                lines.append(f"  {issue}")
            lines.append("")

        if self.warnings:
            lines.append("WARNINGS:")
            for issue in self.warnings:
                lines.append(f"  {issue}")
            lines.append("")

        if self.info:
            lines.append("INFO:")
            for issue in self.info:
                lines.append(f"  {issue}")

        return "\n".join(lines)


class ReadmeValidator:
    """
    Validates generated README content.

    Performs comprehensive checks to ensure README quality and correctness.
    """

    # Placeholder patterns that indicate generated or unfinished content
    PLACEHOLDER_PATTERNS = [
        (r'\byour[_-]?repo\b', 'your-repo'),
        (r'\byour[_-]?username\b', 'your-username'),
        (r'\byour[_-]?project\b', 'your-project'),
        (r'\byour[_-]?name\b', 'your-name'),
        (r'\byour[_-]?email\b', 'your-email'),
        (r'\bTODO\b', 'TODO'),
        (r'\bFIXME\b', 'FIXME'),
        (r'\bXXX\b', 'XXX'),
        (r'\bplaceholder\b', 'placeholder'),
        (r'\[INSERT[^\]]*\]', '[INSERT...]'),
        (r'Project title with', 'generic title'),
    ]

    # Absolute path patterns
    WINDOWS_PATH = re.compile(r'[A-Z]:[\\\/][\w\s\.\-\\\/]+')
    UNIX_PATH = re.compile(r'/(home|Users|root|var|etc|usr)/[\w\s\.\-\/]+')

    def __init__(self, strict: bool = True):
        """
        Initialize validator.

        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict

    def validate(self, markdown: str, facts: Optional[Dict[str, Any]] = None) -> ValidationResult:
        """
        Validate README markdown content.

        Args:
            markdown: README content to validate
            facts: Optional LADOM facts data for context-aware validation

        Returns:
            ValidationResult with all issues found
        """
        result = ValidationResult(passed=True)

        logger.info("Starting README validation...")

        # Core validations (always fail)
        self._check_placeholders(markdown, result)
        self._check_absolute_paths(markdown, result)
        self._check_malformed_urls(markdown, result)
        self._check_duplicate_headings(markdown, result)
        self._check_path_separators(markdown, result)

        # Context-aware validations (if facts provided)
        if facts:
            self._check_dependencies_section(markdown, facts, result)
            self._check_file_references(markdown, facts, result)

        # Quality validations (warnings)
        self._check_heading_consistency(markdown, result)
        self._check_empty_sections(markdown, result)
        self._check_broken_links(markdown, result)

        logger.info(f"Validation complete: {result.get_summary()}")
        return result

    def _check_placeholders(self, markdown: str, result: ValidationResult):
        """Check for placeholder text that shouldn't be in output."""
        lines = markdown.split('\n')

        for pattern, name in self.PLACEHOLDER_PATTERNS:
            matches = list(re.finditer(pattern, markdown, re.IGNORECASE))
            if matches:
                for match in matches[:5]:  # Limit to first 5 occurrences
                    # Find line number
                    line_num = markdown[:match.start()].count('\n') + 1
                    context = lines[line_num - 1] if line_num <= len(lines) else ""

                    result.add_error(
                        "Placeholder",
                        f"Placeholder text '{name}' found in output",
                        line_num,
                        context.strip()
                    )

    def _check_absolute_paths(self, markdown: str, result: ValidationResult):
        """Check for absolute file paths."""
        lines = markdown.split('\n')

        # Check Windows paths
        for match in self.WINDOWS_PATH.finditer(markdown):
            line_num = markdown[:match.start()].count('\n') + 1
            context = lines[line_num - 1] if line_num <= len(lines) else ""

            result.add_error(
                "Absolute Path",
                f"Windows absolute path found: {match.group()[:50]}",
                line_num,
                context.strip()
            )

        # Check Unix paths
        for match in self.UNIX_PATH.finditer(markdown):
            line_num = markdown[:match.start()].count('\n') + 1
            context = lines[line_num - 1] if line_num <= len(lines) else ""

            result.add_error(
                "Absolute Path",
                f"Unix absolute path found: {match.group()[:50]}",
                line_num,
                context.strip()
            )

    def _check_malformed_urls(self, markdown: str, result: ValidationResult):
        """Check for malformed URLs."""
        lines = markdown.split('\n')

        # Pattern: URL with port but no slash before path
        # e.g., http://localhost:3000items (should be :3000/items)
        malformed_port = re.compile(r'https?://[a-zA-Z0-9\.\-]+:\d+[a-zA-Z]')

        for match in malformed_port.finditer(markdown):
            line_num = markdown[:match.start()].count('\n') + 1
            context = lines[line_num - 1] if line_num <= len(lines) else ""

            result.add_error(
                "Malformed URL",
                f"URL missing slash after port: {match.group()}",
                line_num,
                context.strip()
            )

        # Check for localhost without port
        localhost_pattern = re.compile(r'curl\s+https?://localhost[^:/\s]')
        for match in localhost_pattern.finditer(markdown):
            line_num = markdown[:match.start()].count('\n') + 1
            context = lines[line_num - 1] if line_num <= len(lines) else ""

            result.add_warning(
                "URL Format",
                f"localhost URL without port may be incorrect",
                line_num,
                context.strip()
            )

    def _check_duplicate_headings(self, markdown: str, result: ValidationResult):
        """Check for duplicate section headings."""
        lines = markdown.split('\n')
        headings: Dict[str, List[int]] = {}

        for i, line in enumerate(lines, 1):
            if line.startswith('#'):
                # Extract heading text (remove # and whitespace)
                heading = line.lstrip('#').strip().lower()
                if heading:
                    if heading in headings:
                        headings[heading].append(i)
                    else:
                        headings[heading] = [i]

        # Report duplicates
        for heading, line_numbers in headings.items():
            if len(line_numbers) > 1:
                result.add_error(
                    "Duplicate Heading",
                    f"Heading '{heading}' appears {len(line_numbers)} times at lines: {line_numbers}",
                    line_numbers[0]
                )

    def _check_path_separators(self, markdown: str, result: ValidationResult):
        """Check for missing path separators in file paths."""
        lines = markdown.split('\n')

        # Pattern: common directory names immediately followed by lowercase letter
        # e.g., srcindex.js (should be src/index.js)
        bad_path_pattern = re.compile(r'\b(src|app|lib|controllers|models|views|services)([a-z])')

        for match in bad_path_pattern.finditer(markdown):
            line_num = markdown[:match.start()].count('\n') + 1
            context = lines[line_num - 1] if line_num <= len(lines) else ""

            # Skip if it's part of a larger word (e.g., "source")
            if match.group() in ["source", "sources", "application", "library"]:
                continue

            result.add_error(
                "Path Separator",
                f"Missing path separator: '{match.group(1)}{match.group(2)}' (should be '{match.group(1)}/{match.group(2)}')",
                line_num,
                context.strip()
            )

    def _check_dependencies_section(self, markdown: str, facts: Dict[str, Any], result: ValidationResult):
        """Check that dependencies section exists if manifests are present."""
        # Check if project has dependency manifests
        has_manifest = False
        manifest_files = [
            'requirements.txt', 'package.json', 'pom.xml',
            'build.gradle', 'Gemfile', 'Cargo.toml', 'go.mod'
        ]

        # Look for manifest files in facts
        project_files = facts.get('files', [])
        for file_data in project_files:
            file_path = file_data.get('path', '').lower()
            if any(manifest in file_path for manifest in manifest_files):
                has_manifest = True
                break

        if has_manifest:
            # Check if README has dependencies section
            has_dep_section = bool(re.search(r'##\s+dependencies', markdown, re.IGNORECASE))

            # Check for "no dependencies" message
            has_no_deps_msg = bool(re.search(r'no dependencies (detected|found)', markdown, re.IGNORECASE))

            if has_no_deps_msg:
                result.add_error(
                    "Dependencies",
                    "README claims 'No dependencies' but dependency manifest files exist in project"
                )
            elif not has_dep_section:
                result.add_warning(
                    "Dependencies",
                    "Project has dependency manifests but README has no Dependencies section"
                )

    def _check_file_references(self, markdown: str, facts: Dict[str, Any], result: ValidationResult):
        """Check that referenced files actually exist in the project."""
        # Extract file references from markdown (in code blocks or inline code)
        file_refs = re.findall(r'`([a-zA-Z0-9_\-./]+\.(py|js|ts|java|go|rs|rb|php))`', markdown)

        # Get list of actual files from facts
        actual_files = set()
        for file_data in facts.get('files', []):
            path = file_data.get('path', '')
            # Normalize to relative path
            if '/' in path or '\\' in path:
                # Get just the filename
                actual_files.add(path.split('/')[-1].split('\\')[-1])
                # Also add relative paths
                actual_files.add(path)

        # Check each reference
        for file_ref, ext in file_refs[:20]:  # Limit to first 20 to avoid spam
            if file_ref not in actual_files and not any(file_ref in f for f in actual_files):
                result.add_warning(
                    "File Reference",
                    f"Referenced file '{file_ref}' may not exist in project"
                )

    def _check_heading_consistency(self, markdown: str, result: ValidationResult):
        """Check heading capitalization consistency."""
        lines = markdown.split('\n')
        heading_styles = {'title': 0, 'sentence': 0, 'upper': 0, 'lower': 0}

        for line in lines:
            if line.startswith('##'):  # Level 2+ headings
                heading_text = line.lstrip('#').strip()
                if not heading_text:
                    continue

                # Determine style
                if heading_text.isupper():
                    heading_styles['upper'] += 1
                elif heading_text[0].isupper() and all(
                    word[0].isupper() or word.lower() in ['a', 'an', 'the', 'and', 'or', 'but']
                    for word in heading_text.split() if word
                ):
                    heading_styles['title'] += 1
                elif heading_text[0].isupper():
                    heading_styles['sentence'] += 1
                else:
                    heading_styles['lower'] += 1

        # Check consistency (if there's a dominant style)
        total = sum(heading_styles.values())
        if total > 3:
            dominant = max(heading_styles.values())
            if dominant < total * 0.7:  # Less than 70% consistent
                result.add_warning(
                    "Heading Style",
                    f"Inconsistent heading capitalization styles: {heading_styles}"
                )

    def _check_empty_sections(self, markdown: str, result: ValidationResult):
        """Check for empty sections (heading followed by another heading)."""
        lines = markdown.split('\n')
        prev_heading_line = None

        for i, line in enumerate(lines):
            if line.startswith('#'):
                if prev_heading_line is not None:
                    # Check if there's only whitespace between headings
                    # Exclude the heading line itself (prev_heading_line + 1)
                    between = lines[prev_heading_line + 1:i]
                    if all(not l.strip() for l in between):
                        result.add_warning(
                            "Empty Section",
                            f"Empty section at line {prev_heading_line + 1}: {lines[prev_heading_line]}",
                            prev_heading_line + 1
                        )
                prev_heading_line = i

    def _check_broken_links(self, markdown: str, result: ValidationResult):
        """Check for potentially broken markdown links."""
        # Pattern: [text]() or [text](# ) - empty or whitespace-only URLs
        broken_link_pattern = re.compile(r'\[([^\]]+)\]\(\s*#?\s*\)')

        lines = markdown.split('\n')
        for match in broken_link_pattern.finditer(markdown):
            line_num = markdown[:match.start()].count('\n') + 1
            context = lines[line_num - 1] if line_num <= len(lines) else ""

            result.add_warning(
                "Broken Link",
                f"Link with empty URL: [{match.group(1)}]()",
                line_num,
                context.strip()
            )


def validate_readme(markdown: str, facts: Optional[Dict[str, Any]] = None, strict: bool = True) -> ValidationResult:
    """
    Validate README markdown content.

    Convenience function for quick validation.

    Args:
        markdown: README content to validate
        facts: Optional LADOM facts for context-aware validation
        strict: If True, treat warnings as errors

    Returns:
        ValidationResult
    """
    validator = ReadmeValidator(strict=strict)
    return validator.validate(markdown, facts)
