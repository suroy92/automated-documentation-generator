"""Text processing utilities for documentation generation."""

from __future__ import annotations

import html
import json
import re
from typing import Any, Dict


class TextUtils:
    """Centralized text manipulation utilities."""

    # Compiled regex patterns for better performance
    _NEWLINE_PATTERN = re.compile(r"[\r\n\t]+")
    _WHITESPACE_PATTERN = re.compile(r"\s{2,}")
    _JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", flags=re.DOTALL)

    @staticmethod
    def escape_mermaid_label(text: str, max_len: int = 80) -> str:
        """
        Escape text for use in Mermaid diagram labels.
        
        Parameters
        ----------
        text : str
            Text to escape.
        max_len : int, optional
            Maximum label length, by default 80.
            
        Returns
        -------
        str
            Escaped and truncated text safe for Mermaid labels.
        """
        text = text or ""
        # Escape double quotes
        text = text.replace('"', '\\"')
        # Replace newlines, tabs with spaces
        text = TextUtils._NEWLINE_PATTERN.sub(" ", text)
        # Collapse multiple spaces
        text = TextUtils._WHITESPACE_PATTERN.sub(" ", text).strip()
        return text[:max_len]

    @staticmethod
    def escape_html(text: str) -> str:
        """
        Escape HTML special characters.
        
        Parameters
        ----------
        text : str
            Text to escape.
            
        Returns
        -------
        str
            HTML-safe text.
        """
        return html.escape(text or "", quote=True)

    @staticmethod
    def unescape_html(text: str) -> str:
        """
        Unescape HTML entities.
        
        Parameters
        ----------
        text : str
            HTML text to unescape.
            
        Returns
        -------
        str
            Unescaped text.
        """
        return html.unescape(text or "")

    @staticmethod
    def lenient_json_parse(text: str, default_schema: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Parse JSON with fallback strategies for malformed input.
        
        First attempts direct parsing, then extracts first {...} block,
        finally returns default schema if all else fails.
        
        Parameters
        ----------
        text : str
            Text that may contain JSON.
        default_schema : Dict[str, Any] | None, optional
            Default structure to return if parsing fails, by default None.
            
        Returns
        -------
        Dict[str, Any]
            Parsed JSON object or default schema.
        """
        # Try direct parse
        try:
            return json.loads(text)
        except Exception:
            pass

        # Try to extract first JSON block
        match = TextUtils._JSON_BLOCK_PATTERN.search(text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass

        # Return default schema or empty dict
        return default_schema if default_schema is not None else {}

    @staticmethod
    def truncate(text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to maximum length with suffix.
        
        Parameters
        ----------
        text : str
            Text to truncate.
        max_length : int
            Maximum length including suffix.
        suffix : str, optional
            Suffix to add when truncating, by default "...".
            
        Returns
        -------
        str
            Truncated text.
        """
        text = text or ""
        if len(text) <= max_length:
            return text
        return text[: max_length - len(suffix)] + suffix

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """
        Normalize whitespace in text (collapse multiple spaces, trim).
        
        Parameters
        ----------
        text : str
            Text to normalize.
            
        Returns
        -------
        str
            Normalized text.
        """
        text = text or ""
        text = TextUtils._NEWLINE_PATTERN.sub(" ", text)
        text = TextUtils._WHITESPACE_PATTERN.sub(" ", text)
        return text.strip()

    @staticmethod
    def indent_lines(text: str, spaces: int = 2) -> str:
        """
        Indent each line of text.
        
        Parameters
        ----------
        text : str
            Text to indent.
        spaces : int, optional
            Number of spaces to indent, by default 2.
            
        Returns
        -------
        str
            Indented text.
        """
        indent = " " * spaces
        lines = (text or "").splitlines()
        return "\n".join(indent + line if line.strip() else "" for line in lines)

    @staticmethod
    def strip_code_markers(text: str) -> str:
        """
        Remove code block markers (```, ~~~) from text.
        
        Parameters
        ----------
        text : str
            Text that may contain code markers.
            
        Returns
        -------
        str
            Text without code markers.
        """
        text = text or ""
        # Remove opening markers with optional language hint
        text = re.sub(r"^```\w*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"^~~~\w*\n?", "", text, flags=re.MULTILINE)
        # Remove closing markers
        text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n?~~~$", "", text, flags=re.MULTILINE)
        return text.strip()

    @staticmethod
    def sanitize_filename(text: str, replacement: str = "_") -> str:
        """
        Sanitize text for use as a filename.
        
        Parameters
        ----------
        text : str
            Text to sanitize.
        replacement : str, optional
            Character to replace invalid characters with, by default "_".
            
        Returns
        -------
        str
            Safe filename string.
        """
        text = text or "unnamed"
        # Replace invalid filename characters
        text = re.sub(r'[<>:"/\\|?*]', replacement, text)
        # Collapse multiple replacements
        text = re.sub(f"{re.escape(replacement)}+", replacement, text)
        return text.strip(replacement)

    @staticmethod
    def count_lines(text: str) -> int:
        """
        Count number of lines in text.
        
        Parameters
        ----------
        text : str
            Text to count.
            
        Returns
        -------
        int
            Number of lines.
        """
        return len((text or "").splitlines())

    @staticmethod
    def ensure_newline_ending(text: str) -> str:
        """
        Ensure text ends with a single newline.
        
        Parameters
        ----------
        text : str
            Text to process.
            
        Returns
        -------
        str
            Text with single newline at end.
        """
        text = (text or "").rstrip("\n")
        return text + "\n" if text else ""
