import unittest
from unittest.mock import Mock, patch
from src.analyzers.py_analyzer import PythonAnalyzer
from src.analyzers.js_analyzer import JavaScriptAnalyzer
import os

# Create a mock client for the JavaScriptAnalyzer's LLM calls
class MockGoogleClient:
    """A mock client to simulate the Google GenAI API."""
    def __init__(self):
        self.models = Mock()
        self.models.generate_content = Mock(return_value=Mock(text="""
/**
 * A mock JSDoc comment for testing purposes.
 * @param {string} param A test parameter.
 * @returns {boolean} True if successful.
 */"""))

class TestAnalyzers(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        """Define paths to the edge case test files."""
        cls.py_file_path = os.path.join(os.path.dirname(__file__), 'test_python_edge_cases.py')
        cls.js_file_path = os.path.join(os.path.dirname(__file__), 'test_js_edge_cases.js')

    # --- Python Analyzer Tests ---

    def test_python_analyzer_docstring_parsing(self):
        analyzer = PythonAnalyzer()
        doc_data = analyzer.analyze(self.py_file_path)
        self.assertIsNotNone(doc_data)
        
        # Test 'process_data' function with explicit parameters
        process_data_func = next(f for f in doc_data['functions'] if f['name'] == 'process_data')
        self.assertIsNotNone(process_data_func)
        self.assertEqual(process_data_func['name'], 'process_data')
        self.assertIn('Filters a list of integers', process_data_func['docstring'])
        self.assertIn('data', process_data_func['parsed_args'])
        self.assertEqual(process_data_func['parsed_args']['data']['type'], 'list of int')
        self.assertEqual(process_data_func['parsed_returns']['type'], 'list of int')

    def test_python_analyzer_complex_parameters(self):
        analyzer = PythonAnalyzer()
        doc_data = analyzer.analyze(self.py_file_path)

        # Test 'configure_system' with *args and **kwargs
        configure_system_func = next(f for f in doc_data['functions'] if f['name'] == 'configure_system')
        self.assertIsNotNone(configure_system_func)
        self.assertIn('configure_system', configure_system_func['name'])
        self.assertIn('args', configure_system_func['parsed_args'])
        self.assertIn('kwargs', configure_system_func['parsed_args'])
        self.assertEqual(configure_system_func['parsed_args']['args']['type'], 'str')
        self.assertIn('detailing the number of arguments', configure_system_func['parsed_returns']['desc'])

    def test_python_analyzer_class_and_inheritance(self):
        analyzer = PythonAnalyzer()
        doc_data = analyzer.analyze(self.py_file_path)
        self.assertEqual(len(doc_data['classes']), 2)

        data_processor_class = next(c for c in doc_data['classes'] if c['name'] == 'DataProcessor')
        self.assertIsNotNone(data_processor_class)
        self.assertIn('A concrete component for processing', data_processor_class['docstring'])
        
        # Test a method within the class
        process_method = next(m for m in data_processor_class['methods'] if m['name'] == 'process')
        self.assertIsNotNone(process_method)
        self.assertEqual(process_method['parsed_returns']['type'], 'Optional[list]')
    
    def test_python_analyzer_multi_line_returns(self):
        analyzer = PythonAnalyzer()
        doc_data = analyzer.analyze(self.py_file_path)
        
        # Test 'configure_system' for its multi-line return description
        configure_system_func = next(f for f in doc_data['functions'] if f['name'] == 'configure_system')
        self.assertIn('The description is quite long and spans multiple lines', configure_system_func['parsed_returns']['desc'])

    # --- JavaScript Analyzer Tests ---

    def test_javascript_analyzer_docstring_parsing(self):
        mock_client = MockGoogleClient()
        analyzer = JavaScriptAnalyzer(mock_client)
        doc_data = analyzer.analyze(self.js_file_path)
        self.assertIsNotNone(doc_data)

        # Test 'UserProfile' class and its constructor
        user_profile_class = next(c for c in doc_data['classes'] if c['name'] == 'UserProfile')
        self.assertIsNotNone(user_profile_class)
        self.assertIn('Creates an instance of UserProfile', user_profile_class['methods'][0]['description'])
        self.assertIn('userName', user_profile_class['methods'][0]['parsed_args'])
        self.assertEqual(user_profile_class['methods'][0]['parsed_args']['userName']['type'], 'string')

    def test_javascript_analyzer_arrow_function(self):
        mock_client = MockGoogleClient()
        analyzer = JavaScriptAnalyzer(mock_client)
        doc_data = analyzer.analyze(self.js_file_path)
        
        # Test 'createConnectionString' which is an arrow function
        conn_string_func = next(f for f in doc_data['functions'] if f['name'] == 'createConnectionString')
        self.assertIsNotNone(conn_string_func)
        self.assertEqual(conn_string_func['name'], 'createConnectionString')
        self.assertIn('settings', conn_string_func['parsed_args'])
        self.assertIn('host', conn_string_func['parsed_args']['settings']['desc'])
        self.assertEqual(conn_string_func['parsed_returns']['type'], 'string')

    @patch('src.analyzers.js_analyzer.genai')
    def test_javascript_analyzer_no_docstring_llm_generation(self, mock_genai):
        # Configure the mock to return a predictable response
        mock_genai.GenerativeModel.return_value.generate_content.return_value = Mock(text="""
/**
 * A mock JSDoc comment for testing.
 */""")

        analyzer = JavaScriptAnalyzer(mock_genai.GenerativeModel())
        doc_data = analyzer.analyze(self.js_file_path)
        
        # Test 'performSimpleOperation' which has no JSDoc
        no_doc_func = next(f for f in doc_data['functions'] if f['name'] == 'performSimpleOperation')
        self.assertIn('A mock JSDoc comment for testing', no_doc_func['description'])
        mock_genai.GenerativeModel.return_value.generate_content.assert_called_once()
        self.assertIn('valueA', no_doc_func['params'])

if __name__ == '__main__':
    unittest.main()