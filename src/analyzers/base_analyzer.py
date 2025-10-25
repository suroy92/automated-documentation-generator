# src/analyzers/base_analyzer.py

"""
Base analyzer class for language-specific parsers.
Provides common functionality and enforces interface consistency.
"""

from abc import ABC, abstractmethod
import logging
import time
from typing import Optional, Dict, Any
from ..ladom_schema import LADOMValidator, normalize_ladom
from ..cache_manager import DocstringCache
from ..rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Abstract base class for language-specific analyzers."""
    
    def __init__(self, client=None, cache: Optional[DocstringCache] = None,
                 rate_limiter: Optional[RateLimiter] = None):
        """
        Initialize the analyzer.
        
        Args:
            client: LLM client for docstring generation (must expose .generate(...))
            cache: Cache manager for storing generated docstrings
            rate_limiter: Rate limiter for API calls
        """
        self.client = client
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.language = self._get_language_name()
        self.ladom_validator = LADOMValidator()
        
        logger.info(f"Initialized {self.__class__.__name__}")
    
    @abstractmethod
    def _get_language_name(self) -> str:
        """
        Get the language name for this analyzer.
        
        Returns:
            Language name (e.g., 'python', 'javascript')
        """
        pass
    
    @abstractmethod
    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a source file and return LADOM structure.
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            LADOM-compliant dictionary structure or None if analysis fails
        """
        pass
    
    def _validate_and_normalize(self, ladom: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Validate and normalize a LADOM structure.
        
        Args:
            ladom: LADOM structure to validate
            
        Returns:
            Normalized LADOM or None if validation fails
        """
        if not self.ladom_validator.validate_ladom(ladom):
            logger.error(f"LADOM validation failed for {self.language} analyzer")
            return None
        
        return normalize_ladom(ladom)

    def _generate_docstring_with_llm(self, code_snippet: str, 
                                     node_name: str = "unknown") -> str:
        """
        Generate a docstring using the configured LLM with caching and rate limiting.
        
        Args:
            code_snippet: The code to document
            node_name: Name of the code element being documented
            
        Returns:
            Generated docstring or fallback message
        """
        if not self.client:
            logger.warning(f"No LLM client available for {node_name}")
            return self._get_fallback_docstring()

        # Check cache first
        if self.cache:
            cached = self.cache.get(code_snippet, self.language)
            if cached:
                logger.debug(f"Using cached docstring for {node_name}")
                return cached

        # Apply rate limiting
        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()

        # Generate docstring
        logger.info(f"Generating docstring for `{node_name}` using local LLM")
        try:
            prompt = self._create_docstring_prompt(code_snippet)
            # Local provider contract: client.generate(system=..., prompt=..., temperature=...)
            docstring = self.client.generate(
                system="", prompt=prompt, temperature=0.2
            ).strip()

            # Cache the result
            if self.cache and docstring:
                self.cache.set(code_snippet, docstring, self.language)
            return self._clean_llm_response(docstring) if docstring else self._get_fallback_docstring()

        except Exception as e:
            logger.error(f"Failed to generate docstring for {node_name} using LLM: {e}")
            return self._get_fallback_docstring()

    @abstractmethod
    def _create_docstring_prompt(self, code_snippet: str) -> str:
        """
        Create the specific prompt string for the LLM based on language.
        
        Args:
            code_snippet: The code snippet to document
            
        Returns:
            Prompt string for the LLM
        """
        pass
    
    @abstractmethod
    def _clean_llm_response(self, response: str) -> str:
        """
        Clean and format the LLM response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Cleaned docstring
        """
        pass

    def _get_fallback_docstring(self) -> str:
        """
        Get a fallback docstring when generation fails.
        
        Returns:
            Generic fallback docstring
        """
        return "No documentation available."
    
    def _safe_read_file(self, file_path: str) -> Optional[str]:
        """
        Safely read a file with error handling.
        
        Args:
            file_path: Path to file
            
        Returns:
            File contents or None on error
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            logger.warning(f"Failed to read {file_path} with UTF-8, trying latin-1")
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return None
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while reading {file_path}: {e}")
            return None
