# src/analyzers/js_analyzer.py

import esprima
import re
import os
from unittest.mock import Mock # Using mock for LLM client in this non-runnable environment

class JavaScriptAnalyzer:
    def __init__(self, client=None):
        # Initialize client, using Mock if none provided
        self.client = client if client is not None else Mock()

    def analyze(self, file_path):
        """
        Parses a JavaScript file and returns a structured representation of its documentation.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None

        try:
            tree = esprima.parse(source_code, {'loc': True, 'range': True, 'attachComment': True})
        except esprima.Error as e:
            print(f"Error parsing JavaScript file {file_path}: {e}")
            return None

        doc_data = {
            'file_name': os.path.basename(file_path),
            'path': file_path, # Added the missing 'path' key
            'functions': [],
            'classes': []
        }

        for node in tree.body:
            if node.type == 'ClassDeclaration':
                doc_data['classes'].append(self._process_class(node, source_code))
            elif node.type == 'FunctionDeclaration':
                doc_data['functions'].append(self._process_function(node, source_code))
            elif node.type == 'VariableDeclaration':
                for declaration in node.declarations:
                    if declaration.init and (declaration.init.type == 'FunctionExpression' or declaration.init.type == 'ArrowFunctionExpression'):
                        doc_data['functions'].append(self._process_function(declaration.init, source_code, declaration.id.name))
        
        # Return the data in the expected LADOM format for main.py
        return {
            "files": [doc_data]
        }

    def _process_class(self, node, source_code):
        docstring = self._find_docstring(node, source_code)
        parsed_args, parsed_returns, brief_desc = self._parse_docstring(docstring)
        
        methods = []
        for method in node.body.body:
            if method.type == 'MethodDefinition':
                methods.append(self._process_method(method, source_code))
        
        return {
            'name': node.id.name,
            'docstring': docstring,
            'description': brief_desc,
            'methods': methods
        }
    
    def _process_method(self, node, source_code):
        docstring = self._find_docstring(node, source_code)
        parsed_args, parsed_returns, brief_desc = self._parse_docstring(docstring)

        method_name = node.key.name
        method_params = []
        if node.value and node.value.params:
            for param in node.value.params:
                if param.type == 'Identifier':
                    method_params.append(param.name)
                elif hasattr(param, 'range'):
                    method_params.append(source_code[param.range[0]:param.range[1]])
        
        return {
            'name': method_name,
            'docstring': docstring,
            'description': brief_desc,
            'params': method_params,
            'parsed_args': parsed_args,
            'parsed_returns': parsed_returns
        }

    def _process_function(self, node, source_code, name=None):
        docstring = self._find_docstring(node, source_code)
        parsed_args, parsed_returns, brief_desc = self._parse_docstring(docstring)
        
        func_name = name or (node.id.name if hasattr(node.id, 'name') else 'anonymous')
        func_params = []
        if node.params:
            for param in node.params:
                if param.type == 'Identifier':
                    func_params.append(param.name)
                elif hasattr(param, 'range'):
                    func_params.append(source_code[param.range[0]:param.range[1]])
        
        return {
            'name': func_name,
            'docstring': docstring,
            'description': brief_desc,
            'params': func_params,
            'parsed_args': parsed_args,
            'parsed_returns': parsed_returns
        }

    def _find_docstring(self, node, source_code):
        """Finds or generates a JSDoc comment for a JavaScript node."""
        if hasattr(node, 'leadingComments') and node.leadingComments:
            for comment in reversed(node.leadingComments):
                if comment.type == 'Block' and comment.value.strip().startswith('*'):
                    return f"/**{comment.value}*/"
        
        node_name = node.id.name if hasattr(node.id, 'name') else 'anonymous'
        print(f"  - Generating JSDoc for `{node_name}`...")
        if hasattr(node, 'range'):
            code_snippet = source_code[node.range[0]:node.range[1]]
            
            # Refined prompt for cleaner output
            prompt = (
                f"Generate a JSDoc comment for the following JavaScript code. "
                f"Provide only the JSDoc comment block, starting with `/**` and ending with `*/`. "
                f"Do not include the code snippet itself or any other text.\n\n"
                f"Code snippet to document:\n```javascript\n{code_snippet}\n```"
            )

            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                docstring = response.text.strip()
                return docstring
            except Exception as e:
                print(f"Error generating docstring: {e}")
                return "/**\n * Auto-generated docstring failed.\n */"
        return "/**\n * No source code available for docstring generation.\n */"


    def _parse_docstring(self, docstring):
        """Parses a JSDoc comment for params and returns, after cleaning out code blocks."""
        if not docstring:
            return {}, {}, "No description provided."
        
        # Proactively remove all code blocks from the docstring
        clean_docstring = re.sub(r'```[\s\S]*?```', '', docstring, flags=re.MULTILINE).strip()
        clean_docstring = clean_docstring.strip().replace('/**', '').replace('*/', '').strip()
        
        args = {}
        returns = {}
        description = "No description provided."

        # Find the description before the first JSDoc tag
        first_tag_match = re.search(r'(@[a-zA-Z]+)', clean_docstring)
        if first_tag_match:
            description = clean_docstring[:first_tag_match.start()].replace('*', '').strip()
        else:
            description = clean_docstring.replace('*', '').strip()
        
        description = description if description else "No description provided."

        tags_raw = re.findall(r'@(\w+)\s+([\s\S]*?)(?=@|$)', clean_docstring)
        
        for tag, content in tags_raw:
            tag = tag.lower().strip()
            content = content.replace('*', '').strip()
            
            if tag == 'param':
                param_match = re.match(r'(?:\{([^{}]+)\})?\s*(\[?\w+\]?)?(?:\s*[\-\s]*([\s\S]*))?', content)
                if param_match:
                    param_type, param_name, param_desc = param_match.groups()
                    param_name = param_name.strip('[]') if param_name else None
                    param_desc = param_desc.strip() if param_desc else ""
                    if param_name:
                        args[param_name] = {'type': param_type.strip() if param_type else 'any', 'desc': param_desc}
            elif tag == 'returns' or tag == 'return':
                returns_match = re.match(r'(?:\{([^{}]+)\})?\s*([\s\S]*)', content)
                if returns_match:
                    return_type, return_desc = returns_match.groups()
                    returns = {'type': return_type.strip() if return_type else 'any', 'desc': return_desc.strip() if return_desc else ""}
            
        return args, returns, description