# src/analyzers/py_analyzer.py

"""
Python-specific analyzer for extracting documentation from Python source files.
"""

import ast
import os
import re
import logging
from typing import Optional, Dict, Any, List
from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class PythonAnalyzer(BaseAnalyzer):
    """Analyzer for Python source files."""
    
    def _get_language_name(self) -> str:
        return "python"

    def _create_docstring_prompt(self, code_snippet: str) -> str:
        """Create prompt for Python docstring generation."""
        return (
            f"Generate a concise Google-style Python docstring for this code. "
            f"Include Args, Returns, and a brief description. "
            f"Return ONLY the docstring content without triple quotes.\n\n"
            f"Code:\n```python\n{code_snippet}\n```"
        )
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean LLM response for Python docstring."""
        # Remove markdown code blocks if present
        response = re.sub(r'```[\s\S]*?```', '', response).strip()
        # Remove leading/trailing quotes if present
        response = response.strip('"').strip("'").strip()
        return response

    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a Python file and return LADOM structure.
        
        Args:
            file_path: Path to the Python file
            
        Returns:
            LADOM structure or None on error
        """
        source_code = self._safe_read_file(file_path)
        if not source_code:
            return None
        
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            logger.error(f"Syntax error parsing {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return None
        
        functions = []
        classes = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Only process top-level functions
                if not self._is_method(node):
                    functions.append(self._process_function(node, source_code))
            elif isinstance(node, ast.ClassDef):
                classes.append(self._process_class(node, source_code))
        
        ladom = {
            "project_name": os.path.basename(os.path.dirname(os.path.abspath(file_path))) or "Python Project",
            "files": [
                {
                    "path": os.path.abspath(file_path),
                    "functions": functions,
                    "classes": classes
                }
            ]
        }
        
        return self._validate_and_normalize(ladom)
    
    def _is_method(self, node: ast.FunctionDef) -> bool:
        """Check if a function node is a method inside a class."""
        # Walk up the AST to check if this function is inside a class
        # This is a simple check; in practice, we process classes separately
        return False
    
    def _process_function(self, node: ast.FunctionDef, source_code: str) -> Dict[str, Any]:
        """
        Process a function node into LADOM format.
        
        Args:
            node: AST function node
            source_code: Full source code for context
            
        Returns:
            Function dictionary in LADOM format
        """
        docstring = self._find_docstring(node, source_code)
        parsed_args, parsed_returns = self._parse_google_docstring(docstring)
        
        parameters = []
        for arg in node.args.args:
            arg_name = arg.arg
            if arg_name in ('self', 'cls'):
                continue
            
            param_info = parsed_args.get(arg_name, {})
            param_type = param_info.get('type')
            
            # Try to get type from annotation if not in docstring
            if not param_type and arg.annotation:
                try:
                    param_type = ast.unparse(arg.annotation)
                except:
                    param_type = 'any'
            
            parameters.append({
                "name": arg_name,
                "type": param_type or 'any',
                "description": param_info.get('desc', 'No description available.')
            })
        
        # Get return type from annotation if not in docstring
        return_type = parsed_returns.get('type', 'void')
        if return_type == 'void' and node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except:
                pass
        
        return {
            'name': node.name,
            'description': self._get_brief_description(docstring),
            'parameters': parameters,
            'returns': {
                'type': return_type,
                'description': parsed_returns.get('description', 'No return description.')
            }
        }
    
    def _process_class(self, node: ast.ClassDef, source_code: str) -> Dict[str, Any]:
        """
        Process a class node into LADOM format.
        
        Args:
            node: AST class node
            source_code: Full source code for context
            
        Returns:
            Class dictionary in LADOM format
        """
        docstring = self._find_docstring(node, source_code)
        methods = []
        
        for sub_node in node.body:
            if isinstance(sub_node, ast.FunctionDef):
                method_data = self._process_function(sub_node, source_code)
                methods.append(method_data)
        
        return {
            'name': node.name,
            'description': self._get_brief_description(docstring),
            'methods': methods
        }
    
    def _find_docstring(self, node: ast.AST, source_code: str) -> str:
        """
        Find or generate a docstring for a Python AST node.
        
        Args:
            node: AST node
            source_code: Full source code for context
            
        Returns:
            Docstring text
        """
        docstring = ast.get_docstring(node)
        if not docstring:
            # Generate docstring using LLM
            node_name = getattr(node, 'name', 'unknown')
            try:
                code_snippet = ast.unparse(node)
                docstring = self._generate_docstring_with_llm(code_snippet, node_name)
            except Exception as e:
                logger.warning(f"Failed to generate docstring for {node_name}: {e}")
                docstring = self._get_fallback_docstring()
        return docstring

    def _get_brief_description(self, docstring: str) -> str:
        """
        Extract brief description from a docstring.
        
        Args:
            docstring: The full docstring
            
        Returns:
            Brief description or fallback message
        """
        if not docstring:
            return self._get_fallback_docstring()
        
        # Split docstring into lines, find the first non-empty line
        lines = docstring.strip().split('\n')
        first_line = next((line.strip() for line in lines if line.strip()), self._get_fallback_docstring())
        
        # Clean up the line
        first_line = re.sub(r'\s*`.*?`\s*', '', first_line).strip()
        first_line = re.sub(r'^\s*\"\"\"', '', first_line).strip()
        
        return first_line

    def _parse_google_docstring(self, docstring: str) -> (Dict, Dict):
        """
        Parse Google-style docstring sections.
        
        Args:
            docstring: Full docstring text
            
        Returns:
            (args_dict, returns_dict)
        """
        docstring = docstring.strip()
        args = {}
        returns = {'type': 'void', 'description': 'No return description.'}
        
        # Parse Args section
        args_match = re.search(
            r'Args?:\\s*?\\n(.*?)(?:\\n\\s*(?:Returns?|Raises?|Examples?|Note):|$)',
            docstring,
            re.DOTALL | re.IGNORECASE
        )
        if args_match:
            args_text = args_match.group(1).strip()
            param_pattern = r'^\\s*([^\\s]+)\\s*\\(([^)]+)\\):\\s*(.*?)(?=\\n\\s*[^\\s()]+\\s*\\(|\\n$)'
            
            for match in re.finditer(param_pattern, args_text, re.MULTILINE | re.DOTALL):
                param_name = match.group(1)
                param_type = match.group(2)
                param_desc = match.group(3).strip() if match.group(3) else ""
                
                # Clean up multi-line descriptions
                param_desc = ' '.join(param_desc.split())
                
                args[param_name] = {
                    'type': param_type.strip() if param_type else None,
                    'desc': param_desc
                }
        
        # Parse Returns section
        returns_match = re.search(
            r'Returns?:\\s*?\\n(.*?)(?:\\n\\s*(?:Raises?|Examples?|Note|Yields?):|$)',
            docstring,
            re.DOTALL | re.IGNORECASE
        )
        
        if returns_match:
            returns_text = returns_match.group(1).strip()
            
            # Try to parse type and description
            type_match = re.match(r'^\\s*([^:]+?):\\s*(.+)', returns_text, re.DOTALL)
            if type_match:
                return_type = type_match.group(1).strip()
                return_desc = ' '.join(type_match.group(2).split())
                returns = {'type': return_type, 'description': return_desc}
            else:
                # No type specified, just description
                returns = {'type': 'void', 'description': ' '.join(returns_text.split())}
        
        return args, returns