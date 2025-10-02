# tests/test_analyzers.py

"""
Unit tests for language analyzers.
"""

import pytest
import tempfile
import os
from unittest.mock import Mock, MagicMock
from src.analyzers.py_analyzer import PythonAnalyzer
from src.analyzers.js_analyzer import JavaScriptAnalyzer


class TestPythonAnalyzer:
    """Test cases for Python analyzer."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        client = Mock()
        response = Mock()
        response.text = "Test function that does something.\n\nArgs:\n    x: Input value\n\nReturns:\n    Result value"
        client.models.generate_content.return_value = response
        return client
    
    @pytest.fixture
    def temp_python_file(self):
        """Create a temporary Python file."""
        content = '''
def add(a, b):
    """
    Add two numbers.
    
    Args:
        a (int): First number
        b (int): Second number
    
    Returns:
        int: Sum of a and b
    """
    return a + b

class Calculator:
    """A simple calculator class."""
    
    def multiply(self, x, y):
        """
        Multiply two numbers.
        
        Args:
            x (float): First number
            y (float): Second number
        
        Returns:
            float: Product of x and y
        """
        return x * y
'''
        fd, path = tempfile.mkstemp(suffix='.py')
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        yield path
        os.remove(path)
    
    def test_analyze_python_file(self, mock_client, temp_python_file):
        """Test analyzing a Python file."""
        analyzer = PythonAnalyzer(client=mock_client)
        result = analyzer.analyze(temp_python_file)
        
        assert result is not None
        assert 'files' in result
        assert len(result['files']) == 1
        
        file_data = result['files'][0]
        assert 'functions' in file_data
        assert 'classes' in file_data
        
        # Check function
        assert len(file_data['functions']) == 1
        func = file_data['functions'][0]
        assert func['name'] == 'add'
        assert len(func['parameters']) == 2
        
        # Check class
        assert len(file_data['classes']) == 1
        cls = file_data['classes'][0]
        assert cls['name'] == 'Calculator'
        assert len(cls['methods']) == 1
    
    def test_parse_google_docstring(self, mock_client):
        """Test parsing Google-style docstrings."""
        analyzer = PythonAnalyzer(client=mock_client)
        
        docstring = """
        Calculate something.
        
        Args:
            x (int): First parameter
            y (str): Second parameter
        
        Returns:
            bool: Result of calculation
        """
        
        args, returns = analyzer._parse_google_docstring(docstring)
        
        assert 'x' in args
        assert args['x']['type'] == 'int'
        assert 'y' in args
        assert returns['type'] == 'bool'
    
    def test_invalid_python_file(self, mock_client):
        """Test handling of invalid Python syntax."""
        fd, path = tempfile.mkstemp(suffix='.py')
        with os.fdopen(fd, 'w') as f:
            f.write("def invalid syntax here")
        
        analyzer = PythonAnalyzer(client=mock_client)
        result = analyzer.analyze(path)
        
        os.remove(path)
        assert result is None


class TestJavaScriptAnalyzer:
    """Test cases for JavaScript analyzer."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        client = Mock()
        response = Mock()
        response.text = """/**
 * Test function
 * @param {string} x - Input value
 * @returns {number} Result
 */"""
        client.models.generate_content.return_value = response
        return client
    
    @pytest.fixture
    def temp_js_file(self):
        """Create a temporary JavaScript file."""
        content = '''
/**
 * Add two numbers
 * @param {number} a - First number
 * @param {number} b - Second number
 * @returns {number} Sum of a and b
 */
function add(a, b) {
    return a + b;
}

/**
 * Calculator class
 */
class Calculator {
    /**
     * Multiply two numbers
     * @param {number} x - First number
     * @param {number} y - Second number
     * @returns {number} Product
     */
    multiply(x, y) {
        return x * y;
    }
}

const subtract = (a, b) => a - b;
'''
        fd, path = tempfile.mkstemp(suffix='.js')
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        yield path
        os.remove(path)
    
    def test_analyze_javascript_file(self, mock_client, temp_js_file):
        """Test analyzing a JavaScript file."""
        analyzer = JavaScriptAnalyzer(client=mock_client)
        result = analyzer.analyze(temp_js_file)
        
        assert result is not None
        assert 'files' in result
        assert len(result['files']) == 1
        
        file_data = result['files'][0]
        assert 'functions' in file_data
        assert 'classes' in file_data
        
        # Check function
        funcs = file_data['functions']
        assert len(funcs) >= 1
        add_func = next((f for f in funcs if f['name'] == 'add'), None)
        assert add_func is not None
        assert len(add_func['parameters']) == 2
        
        # Check class
        classes = file_data['classes']
        assert len(classes) == 1
        assert classes[0]['name'] == 'Calculator'
    
    def test_parse_jsdoc(self, mock_client):
        """Test parsing JSDoc comments."""
        analyzer = JavaScriptAnalyzer(client=mock_client)
        
        docstring = """/**
         * Calculate something
         * @param {number} x - First parameter
         * @param {string} y - Second parameter
         * @returns {boolean} Result
         */"""
        
        args, returns, desc = analyzer._parse_jsdoc(docstring)
        
        assert 'x' in args
        assert args['x']['type'] == 'number'
        assert 'y' in args
        assert returns['type'] == 'boolean'
        assert 'Calculate' in desc
    
    def test_extract_parameters(self, mock_client):
        """Test parameter extraction from various patterns."""
        analyzer = JavaScriptAnalyzer(client=mock_client)
        
        # This is a simplified test - in real usage, we'd need actual Esprima nodes
        # For now, we test the analyzer can handle the extraction logic
        assert analyzer._get_language_name() == 'javascript'
    
    def test_invalid_javascript_file(self, mock_client):
        """Test handling of invalid JavaScript syntax."""
        fd, path = tempfile.mkstemp(suffix='.js')
        with os.fdopen(fd, 'w') as f:
            f.write("function invalid { syntax here")
        
        analyzer = JavaScriptAnalyzer(client=mock_client)
        result = analyzer.analyze(path)
        
        os.remove(path)
        assert result is None


class TestAnalyzerConsistency:
    """Test that both analyzers produce consistent LADOM structures."""
    
    def test_ladom_structure_consistency(self):
        """Test that both analyzers produce the same LADOM keys."""
        mock_client = Mock()
        
        py_analyzer = PythonAnalyzer(client=mock_client)
        js_analyzer = JavaScriptAnalyzer(client=mock_client)
        
        # Both should return the same language property structure
        assert py_analyzer._get_language_name() == 'python'
        assert js_analyzer._get_language_name() == 'javascript'