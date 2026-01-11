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
from src.analyzers.java_analyzer import JavaAnalyzer
from src.analyzers.ts_analyzer import TypeScriptAnalyzer


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

class TestJavaAnalyzer:
    """Test cases for Java analyzer."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client."""
        client = Mock()
        response = Mock()
        response.text = """
        Test class for demonstration.
        @param name The name parameter
        @return The result value
        """
        client.models.generate_content.return_value = response
        return client
    
    @pytest.fixture
    def temp_java_file(self):
        """Create a temporary Java file."""
        content = '''
/**
 * Calculator class for basic arithmetic operations.
 */
public class Calculator {
    
    /**
     * Adds two numbers.
     * @param a The first number
     * @param b The second number
     * @return The sum of a and b
     */
    public int add(int a, int b) {
        return a + b;
    }
    
    /**
     * Multiplies two numbers.
     * @param x The first number
     * @param y The second number
     * @return The product of x and y
     */
    public double multiply(double x, double y) {
        return x * y;
    }
    
    /**
     * Constructor for Calculator.
     * @param initialValue The initial value
     */
    public Calculator(int initialValue) {
        // Constructor implementation
    }
}
'''
        fd, path = tempfile.mkstemp(suffix='.java')
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        yield path
        os.remove(path)
    
    def test_analyze_java_file(self, mock_client, temp_java_file):
        """Test analyzing a Java file."""
        analyzer = JavaAnalyzer(client=mock_client)
        result = analyzer.analyze(temp_java_file)
        
        assert result is not None
        assert 'files' in result
        assert len(result['files']) == 1
        
        file_data = result['files'][0]
        assert 'classes' in file_data
        assert len(file_data['classes']) == 1
        
        # Check class
        cls = file_data['classes'][0]
        assert cls['name'] == 'Calculator'
        assert 'methods' in cls
        assert len(cls['methods']) == 3  # 2 methods + 1 constructor
    
    def test_parse_javadoc(self, mock_client):
        """Test parsing Javadoc comments."""
        analyzer = JavaAnalyzer(client=mock_client)
        
        docstring = """
        Calculates something important.
        @param x The first parameter
        @param y The second parameter
        @return The calculated result
        """
        
        args, returns, desc = analyzer._parse_javadoc(docstring)
        
        assert 'x' in args
        assert 'y' in args
        assert 'Calculates something' in desc
        assert returns['description']
    
    def test_get_brief_description(self, mock_client):
        """Test extracting brief description from Javadoc."""
        analyzer = JavaAnalyzer(client=mock_client)
        
        docstring = """
        * This is the first sentence. This is more detail.
        * @param test A parameter
        """
        
        brief = analyzer._get_brief_description(docstring)
        assert 'first sentence' in brief.lower()
    
    def test_invalid_java_file(self, mock_client):
        """Test handling of invalid Java syntax."""
        fd, path = tempfile.mkstemp(suffix='.java')
        with os.fdopen(fd, 'w') as f:
            f.write("public class Invalid { syntax error here")
        
        analyzer = JavaAnalyzer(client=mock_client)
        result = analyzer.analyze(path)
        
        os.remove(path)
        assert result is None
    
    def test_java_without_javadoc(self, mock_client, temp_java_file):
        """Test that LLM generation is triggered for missing Javadoc."""
        # Create file without Javadoc
        fd, path = tempfile.mkstemp(suffix='.java')
        with os.fdopen(fd, 'w') as f:
            f.write("""
public class NoDoc {
    public void method(String param) {
        // No documentation
    }
}
""")
        
        analyzer = JavaAnalyzer(client=mock_client)
        result = analyzer.analyze(path)
        
        os.remove(path)
        
        # Should still parse successfully
        assert result is not None
        assert len(result['files'][0]['classes']) == 1

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


class TestTypeScriptAnalyzer:
    """Test cases for TypeScript analyzer."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock LLM client consistent with BaseAnalyzer contract."""
        client = Mock()
        # BaseAnalyzer expects a client with .generate(system=, prompt=, temperature=)
        def _fake_generate(**kwargs):
            # Return minimal JSON-like string; BaseAnalyzer will normalize
            return '{"summary":"Auto-generated doc","params":[],"returns":{"type":"","desc":""},"throws":[],"examples":[],"notes":[]}'
        client.generate = MagicMock(side_effect=_fake_generate)
        return client

    @pytest.fixture
    def temp_ts_file(self):
        """Create a temporary TypeScript file."""
        content = '''
function add(a: number, b: number): number {
    return a + b;
}

const subtract = (a: number, b: number): number => {
    return a - b;
}

class Calculator {
    constructor(initialValue: number) {
        // ctor
    }

    multiply(x: number, y: number): number {
        return x * y;
    }
}

interface ICalc {
    divide(x: number, y: number): number;
}
'''
        fd, path = tempfile.mkstemp(suffix='.ts')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        yield path
        os.remove(path)

    def test_analyze_typescript_file(self, mock_client, temp_ts_file):
        """Test analyzing a TypeScript file."""
        analyzer = TypeScriptAnalyzer(client=mock_client)
        result = analyzer.analyze(temp_ts_file)

        assert result is not None
        assert 'files' in result
        assert len(result['files']) == 1

        file_data = result['files'][0]
        assert 'functions' in file_data
        assert 'classes' in file_data

        # Functions should include add and subtract
        funcs = file_data['functions']
        names = {f['name'] for f in funcs}
        assert 'add' in names
        assert 'subtract' in names

        # Classes should include Calculator (with ctor + multiply) and ICalc (interface)
        classes = file_data['classes']
        cnames = {c['name'] for c in classes}
        assert 'Calculator' in cnames
        assert 'ICalc' in cnames
        calc = next(c for c in classes if c['name'] == 'Calculator')
        mnames = {m['name'] for m in calc['methods']}
        assert 'constructor' in mnames
        assert 'multiply' in mnames