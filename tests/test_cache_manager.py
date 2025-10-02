# tests/test_cache_manager.py

"""
Unit tests for cache manager.
"""

import pytest
import os
import tempfile
from src.cache_manager import DocstringCache


class TestDocstringCache:
    """Test cases for docstring caching."""
    
    @pytest.fixture
    def temp_cache_file(self):
        """Create a temporary cache file."""
        fd, path = tempfile.mkstemp(suffix='.json')
        os.close(fd)
        yield path
        # Cleanup
        if os.path.exists(path):
            os.remove(path)
    
    def test_cache_set_and_get(self, temp_cache_file):
        """Test setting and retrieving cached values."""
        cache = DocstringCache(cache_file=temp_cache_file, enabled=True)
        
        code = "def test(): pass"
        docstring = "Test function docstring"
        
        cache.set(code, docstring, 'python')
        retrieved = cache.get(code, 'python')
        
        assert retrieved == docstring
    
    def test_cache_miss(self, temp_cache_file):
        """Test cache miss returns None."""
        cache = DocstringCache(cache_file=temp_cache_file, enabled=True)
        
        result = cache.get("nonexistent code", 'python')
        
        assert result is None
    
    def test_cache_disabled(self, temp_cache_file):
        """Test cache operations when disabled."""
        cache = DocstringCache(cache_file=temp_cache_file, enabled=False)
        
        code = "def test(): pass"
        docstring = "Test docstring"
        
        cache.set(code, docstring, 'python')
        result = cache.get(code, 'python')
        
        assert result is None
    
    def test_cache_persistence(self, temp_cache_file):
        """Test cache persists across instances."""
        code = "def test(): pass"
        docstring = "Test docstring"
        
        # First cache instance
        cache1 = DocstringCache(cache_file=temp_cache_file, enabled=True)
        cache1.set(code, docstring, 'python')
        
        # Second cache instance
        cache2 = DocstringCache(cache_file=temp_cache_file, enabled=True)
        retrieved = cache2.get(code, 'python')
        
        assert retrieved == docstring
    
    def test_cache_clear(self, temp_cache_file):
        """Test cache clearing."""
        cache = DocstringCache(cache_file=temp_cache_file, enabled=True)
        
        cache.set("code1", "doc1", 'python')
        cache.set("code2", "doc2", 'python')
        
        cache.clear()
        
        assert cache.get("code1", 'python') is None
        assert cache.get("code2", 'python') is None
        assert not os.path.exists(temp_cache_file)
    
    def test_cache_stats(self, temp_cache_file):
        """Test cache statistics."""
        cache = DocstringCache(cache_file=temp_cache_file, enabled=True)
        
        cache.set("code1", "doc1", 'python')
        cache.set("code2", "doc2", 'javascript')
        
        stats = cache.get_stats()
        
        assert stats['enabled'] is True
        assert stats['total_entries'] == 2
        assert stats['cache_file'] == temp_cache_file
    
    def test_different_languages_same_code(self, temp_cache_file):
        """Test that same code in different languages is cached separately."""
        cache = DocstringCache(cache_file=temp_cache_file, enabled=True)
        
        code = "function test() {}"
        py_doc = "Python docstring"
        js_doc = "JavaScript docstring"
        
        cache.set(code, py_doc, 'python')
        cache.set(code, js_doc, 'javascript')
        
        assert cache.get(code, 'python') == py_doc
        assert cache.get(code, 'javascript') == js_doc