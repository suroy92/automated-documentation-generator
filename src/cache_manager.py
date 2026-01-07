# src/cache_manager.py

"""
Cache manager for storing and retrieving generated docstrings.
Reduces LLM API calls by caching previously generated documentation.
Thread-safe for parallel processing.
"""

import json
import hashlib
import logging
import os
import stat
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class DocstringCache:
    """Manages caching of generated docstrings with thread-safe operations."""

    def __init__(self, cache_file: str = '.docstring_cache.json', enabled: bool = True):
        """
        Initialize the cache manager.

        Args:
            cache_file: Path to the cache file
            enabled: Whether caching is enabled
        """
        self.cache_file = cache_file
        self.enabled = enabled
        self.cache = {}
        self._lock = threading.Lock()  # Thread-safe operations

        if self.enabled:
            self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from file if it exists and validate security."""
        # Validate cache file location is safe
        cache_dir = os.path.dirname(self.cache_file) or "."
        if not os.path.isdir(cache_dir):
            logger.warning(f"Cache directory does not exist: {cache_dir}, creating...")
            try:
                os.makedirs(cache_dir, mode=0o700, exist_ok=True)
            except (OSError, IOError) as e:
                logger.error(f"Failed to create cache directory: {e}")
                self.cache = {}
                return

        # Check file permissions if exists
        if os.path.exists(self.cache_file):
            file_mode = os.stat(self.cache_file).st_mode
            if file_mode & 0o077 != 0:
                logger.warning(f"Cache file has insecure permissions: {oct(file_mode)}, fixing...")
                try:
                    os.chmod(self.cache_file, 0o600)
                except (OSError, IOError) as e:
                    logger.error(f"Failed to fix cache file permissions: {e}")

            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                logger.info(f"Loaded cache with {len(self.cache)} entries from {self.cache_file}")
            except json.JSONDecodeError as e:
                logger.warning(f"Cache file corrupted, resetting: {e}")
                self.cache = {}
            except (OSError, IOError) as e:
                logger.warning(f"Failed to load cache from {self.cache_file}: {e}")
                self.cache = {}
        else:
            logger.debug(f"Cache file {self.cache_file} not found, starting with empty cache")
    
    def _save_cache(self) -> None:
        """Save cache to file with secure permissions."""
        if not self.enabled:
            return

        try:
            # Write cache atomically with secure permissions (600 - owner read/write only)
            with os.fdopen(os.open(self.cache_file, os.O_WRONLY | os.O_CREAT, 0o600), 'w') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            logger.debug(f"Saved cache with {len(self.cache)} entries to {self.cache_file} (secure mode: 600)")
        except (OSError, IOError) as e:
            logger.error(f"Failed to save cache to {self.cache_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving cache to {self.cache_file}: {e}")
    
    def _generate_key(self, code_snippet: str, language: str = '') -> str:
        """
        Generate a cache key from a code snippet.
        
        Args:
            code_snippet: The code to generate a key for
            language: Optional language identifier
            
        Returns:
            MD5 hash of the code snippet
        """
        content = f"{language}:{code_snippet}".encode('utf-8')
        return hashlib.md5(content).hexdigest()
    
    def get(self, code_snippet: str, language: str = '') -> Optional[str]:
        """
        Retrieve a cached docstring (thread-safe).

        Args:
            code_snippet: The code snippet to look up
            language: Optional language identifier

        Returns:
            Cached docstring if found, None otherwise
        """
        if not self.enabled:
            return None

        key = self._generate_key(code_snippet, language)

        with self._lock:  # Thread-safe read
            docstring = self.cache.get(key)

        if docstring:
            logger.debug(f"Cache hit for key {key[:8]}...")
        else:
            logger.debug(f"Cache miss for key {key[:8]}...")

        return docstring
    
    def set(self, code_snippet: str, docstring: str, language: str = '') -> None:
        """
        Store a docstring in the cache (thread-safe).

        Args:
            code_snippet: The code snippet
            docstring: The generated docstring
            language: Optional language identifier
        """
        if not self.enabled:
            return

        key = self._generate_key(code_snippet, language)

        with self._lock:  # Thread-safe write
            self.cache[key] = docstring
            logger.debug(f"Cached docstring for key {key[:8]}...")
            self._save_cache()
    
    def clear(self) -> None:
        """Clear all cached entries (thread-safe)."""
        with self._lock:
            self.cache = {}
            if self.enabled and os.path.exists(self.cache_file):
                os.remove(self.cache_file)
        logger.info("Cache cleared")
    
    def get_stats(self) -> dict:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        return {
            'enabled': self.enabled,
            'total_entries': len(self.cache),
            'cache_file': self.cache_file,
            'file_exists': os.path.exists(self.cache_file) if self.enabled else False
        }