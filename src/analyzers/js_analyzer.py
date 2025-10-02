# src/analyzers/js_analyzer.py

"""
JavaScript-specific analyzer for extracting documentation from JS source files.
"""

import esprima
import re
import os
import logging
from typing import Optional, Dict, Any, List
from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class JavaScriptAnalyzer(BaseAnalyzer):
    """Analyzer for JavaScript source files."""
    
    def _get_language_name(self) -> str:
        return "javascript"

    def _create_docstring_prompt(self, code_snippet: str) -> str:
        """Create prompt for JavaScript docstring generation."""
        return (
            f"Generate a concise JSDoc-style documentation comment for this JavaScript code. "
            f"Include a brief description, @param tags for all parameters, and an @returns tag for the return value. "
            f"Return ONLY the comment content without the `/** ... */` block.\n\n"
            f"Code:\n```javascript\n{code_snippet}\n```"
        )
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean LLM response for JavaScript docstring."""
        # Remove markdown code blocks if present
        response = re.sub(r'```[\s\S]*?```', '', response).strip()
        # Remove leading/trailing `/**` and `*/`
        response = response.strip().strip('/').strip('*').strip()
        return response
    
    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a JavaScript file and return LADOM structure.
        
        Args:
            file_path: Path to the JavaScript file
            
        Returns:
            LADOM structure or None on error
        """
        source_code = self._safe_read_file(file_path)
        if not source_code:
            return None
        
        try:
            tree = esprima.parse(source_code, {
                'loc': True,
                'range': True,
                'attachComment': True
            })
        except esprima.Error as e:
            logger.error(f"Error parsing JavaScript file {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing {file_path}: {e}")
            return None
        
        functions = []
        classes = []
        
        for node in tree.body:
            if node.type == 'ClassDeclaration':
                classes.append(self._process_class(node, source_code))
            elif node.type == 'FunctionDeclaration':
                functions.append(self._process_function(node, source_code))
            elif node.type == 'VariableDeclaration':
                # Handle function expressions and arrow functions
                for declaration in node.declarations:
                    if declaration.init and declaration.init.type in ('FunctionExpression', 'ArrowFunctionExpression'):
                        func_data = self._process_function(
                            declaration.init,
                            source_code,
                            declaration.id.name
                        )
                        functions.append(func_data)
        
        ladom = {
            "project_name": os.path.basename(os.path.dirname(os.path.abspath(file_path))) or "JavaScript Project",
            "files": [
                {
                    "path": os.path.abspath(file_path),
                    "functions": functions,
                    "classes": classes
                }
            ]
        }
        
        return self._validate_and_normalize(ladom)
    
    def _process_class(self, node, source_code: str) -> Dict[str, Any]:
        """
        Process a class node into LADOM format.
        
        Args:
            node: Esprima class node
            source_code: Full source code
            
        Returns:
            Class dictionary in LADOM format
        """
        docstring = self._find_jsdoc(node, source_code)
        
        if docstring:
            _, _, brief_desc = self._parse_jsdoc(docstring)
        else:
            code_snippet = source_code[node.range[0]:node.range[1]]
            brief_desc = self._generate_docstring_with_llm(code_snippet, node.id.name)
            
        methods = []
        if hasattr(node.body, 'body'):
            for method_node in node.body.body:
                if method_node.type == 'MethodDefinition':
                    methods.append(self._process_method(method_node, source_code))
        
        return {
            'name': node.id.name,
            'description': brief_desc,
            'methods': methods
        }
    
    def _process_method(self, node, source_code: str) -> Dict[str, Any]:
        """
        Process a method node into LADOM format.
        
        Args:
            node: Esprima method node
            source_code: Full source code
            
        Returns:
            Method dictionary in LADOM format
        """
        docstring = self._find_jsdoc(node, source_code)
        
        if docstring:
            parsed_args, parsed_returns, brief_desc = self._parse_jsdoc(docstring)
        else:
            method_name = node.key.name if hasattr(node.key, 'name') else 'anonymous'
            code_snippet = source_code[node.range[0]:node.range[1]]
            generated_docstring = self._generate_docstring_with_llm(code_snippet, method_name)
            parsed_args, parsed_returns, brief_desc = self._parse_jsdoc(generated_docstring)
        
        method_name = node.key.name if hasattr(node.key, 'name') else 'anonymous'
        method_params = self._extract_parameters(node.value, source_code)
        
        # Convert to LADOM parameter format
        parameters = []
        for param_name in method_params:
            param_info = parsed_args.get(param_name, {})
            parameters.append({
                'name': param_name,
                'type': param_info.get('type', 'any'),
                'description': param_info.get('desc', 'No description available.')
            })
        
        return {
            'name': method_name,
            'description': brief_desc,
            'parameters': parameters,
            'returns': {
                'type': parsed_returns.get('type', 'void'),
                'description': parsed_returns.get('desc', 'No return description.')
            }
        }
    
    def _process_function(self, node, source_code: str, name: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a function node into LADOM format.
        
        Args:
            node: Esprima function node
            source_code: Full source code
            name: Optional function name (for expressions)
            
        Returns:
            Function dictionary in LADOM format
        """
        docstring = self._find_jsdoc(node, source_code)
        
        if docstring:
            parsed_args, parsed_returns, brief_desc = self._parse_jsdoc(docstring)
        else:
            func_name = name or (node.id.name if hasattr(node, 'id') and node.id and hasattr(node.id, 'name') else 'anonymous')
            code_snippet = source_code[node.range[0]:node.range[1]]
            generated_docstring = self._generate_docstring_with_llm(code_snippet, func_name)
            parsed_args, parsed_returns, brief_desc = self._parse_jsdoc(generated_docstring)
        
        func_name = name or (node.id.name if hasattr(node, 'id') and node.id and hasattr(node.id, 'name') else 'anonymous')
        func_params = self._extract_parameters(node, source_code)
        
        # Convert to LADOM parameter format
        parameters = []
        for param_name in func_params:
            param_info = parsed_args.get(param_name, {})
            parameters.append({
                'name': param_name,
                'type': param_info.get('type', 'any'),
                'description': param_info.get('desc', 'No description available.')
            })
        
        return {
            'name': func_name,
            'description': brief_desc,
            'parameters': parameters,
            'returns': {
                'type': parsed_returns.get('type', 'void'),
                'description': parsed_returns.get('desc', 'No return description.')
            }
        }
    
    def _extract_parameters(self, node, source_code: str) -> List[str]:
        """
        Extract parameter names from a function node.
        
        Args:
            node: Function node
            source_code: Full source code
            
        Returns:
            List of parameter names
        """
        params = []
        if not hasattr(node, 'params') or not node.params:
            return params
        
        for param in node.params:
            param_name = self._get_param_name(param, source_code)
            if param_name:
                params.append(param_name)
        return params
    
    def _get_param_name(self, param, source_code: str) -> Optional[str]:
        """
        Extract parameter name handling various param types.
        
        Args:
            param: Parameter node
            source_code: Full source code
            
        Returns:
            Parameter name or None
        """
        if param.type == 'Identifier':
            return param.name
        elif param.type == 'RestElement':
            if hasattr(param.argument, 'name'):
                return f"...{param.argument.name}"
            return "...args"
        elif param.type == 'AssignmentPattern':
            # Default parameter
            return self._get_param_name(param.left, source_code)
        elif param.type == 'ObjectPattern':
            return "{destructured}"
        elif param.type == 'ArrayPattern':
            return "[destructured]"
        elif hasattr(param, 'range'):
            # Fallback: extract from source
            try:
                return source_code[param.range[0]:param.range[1]]
            except:
                return "unknown"
        return "unknown"

    def _find_jsdoc(self, node, source_code: str) -> str:
        """Find JSDoc comment for a node."""
        if hasattr(node, 'leadingComments') and node.leadingComments:
            for comment in reversed(node.leadingComments):
                if comment.type == 'Block' and comment.value.strip().startswith('*'):
                    return f"/**{comment.value}*/"
        return ""
    
    def _parse_jsdoc(self, docstring: str) -> (Dict, Dict, str):
        """
        Parse JSDoc comment.
        
        Returns:
            (args_dict, returns_dict, brief_description)
        """
        # Normalize the docstring for parsing
        clean_doc = docstring.strip('/**').strip().rstrip('*/').strip()
        
        args = {}
        returns = {}
        description = ""
        
        # Split into main description and tag sections
        tag_start_match = re.search(r'^\s*@', clean_doc, re.MULTILINE)
        if tag_start_match:
            main_text = clean_doc[:tag_start_match.start()]
            tags_text = clean_doc[tag_start_match.start():]
            description = ' '.join(line.strip().lstrip('*').strip() 
                                  for line in main_text.split('\n') if line.strip())
        else:
            tags_text = ""
            description = ' '.join(line.strip().lstrip('*').strip() 
                                  for line in clean_doc.split('\n') if line.strip())

        # Parse @param tags
        param_pattern = r'@param\s+(?:\{([^}]+)\})?\s*(\[?\w+\.?\]?)(?:(?:\s+-\s*|\s*)(.*?))?(?=@|$)'
        for match in re.finditer(param_pattern, tags_text, re.DOTALL):
            param_type = match.group(1)
            param_name = match.group(2)
            param_desc = match.group(3)
            
            if param_name:
                param_name = param_name.strip('[]')
                args[param_name] = {
                    'type': param_type.strip() if param_type else 'any',
                    'desc': ' '.join(param_desc.split()) if param_desc else ''
                }
        
        # Parse @returns or @return tag
        returns_pattern = r'@returns?\s+(?:\{([^}]+)\})?\s*(.*?)(?=@|$)'
        returns_match = re.search(returns_pattern, tags_text, re.DOTALL)
        if returns_match:
            return_type = returns_match.group(1)
            return_desc = returns_match.group(2)
            returns = {
                'type': return_type.strip() if return_type else 'void',
                'desc': ' '.join(return_desc.split()) if return_desc else ''
            }
        
        return args, returns, description