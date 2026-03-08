# src/analyzers/base_analyzer.py

"""
Abstract base for language analyzers.

Defines the minimal interface every analyzer must implement and wires up
the shared DocstringGenerator so subclasses can call self.generate_doc()
without knowing the LLM / caching details.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Tuple

from ..ladom_schema import LADOMValidator, normalize_ladom
from ..cache_manager import DocstringCache
from ..rate_limiter import RateLimiter
from ..utils.docstring_generator import DocstringGenerator

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Abstract base class for language-specific analyzers."""

    def __init__(
        self,
        client=None,
        cache: Optional[DocstringCache] = None,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        """
        Args:
            client: LLM client (must expose .generate(system=, prompt=, ...))
            cache: Cache manager for generated docs
            rate_limiter: Rate limiter for LLM calls
        """
        self.client = client
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.language = self._get_language_name()
        self.ladom_validator = LADOMValidator()
        self._doc_generator = DocstringGenerator(client, cache, rate_limiter, self.language)
        logger.info(f"Initialized {self.__class__.__name__}")

    # ------------------------------------------------------------------
    # Required API (subclasses must implement)
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_language_name(self) -> str:
        pass

    @abstractmethod
    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Return LADOM for the file, or None on failure."""
        pass

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def generate_doc(
        self,
        code_snippet: str,
        node_name: str = "unknown",
        *,
        context: str = "",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate structured LLM documentation for a code snippet.

        Delegates to DocstringGenerator, which handles caching, rate limiting,
        multi-pass quality refinement, and JSON normalization.

        Returns:
            (docstring_text, normalized_details_dict)
        """
        return self._doc_generator.generate_doc(code_snippet, node_name, context=context)

    def _validate_and_normalize(self, ladom: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.ladom_validator.validate_ladom(ladom):
            logger.error(f"LADOM validation failed for {self.language} analyzer")
            return None
        return normalize_ladom(ladom)

    def _safe_read_file(self, file_path: str, max_size_mb: int = 10) -> Optional[str]:
        """
        Read a file safely, enforcing a size limit to prevent memory exhaustion.

        Args:
            file_path: Path to the file to read
            max_size_mb: Maximum allowed file size in megabytes

        Returns:
            File contents as a string, or None if the file is too large or unreadable
        """
        try:
            file_size = os.path.getsize(file_path)
            max_size_bytes = max_size_mb * 1024 * 1024

            if file_size > max_size_bytes:
                logger.warning(
                    f"File {file_path} exceeds size limit ({max_size_mb}MB), skipping. "
                    f"Actual size: {file_size / (1024 * 1024):.2f}MB"
                )
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            logger.warning(f"Failed to read {file_path} with UTF-8, trying latin-1")
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except (OSError, IOError) as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return None
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return None
        except (OSError, IOError) as e:
            logger.error(f"Unexpected error while reading {file_path}: {e}")
            return None
