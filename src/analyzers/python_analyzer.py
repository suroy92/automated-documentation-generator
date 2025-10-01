# src/analyzers/python_analyzer.py

import ast
import os
import re

class PythonAnalyzer:
    def __init__(self, client):
        self.client = client

    def analyze(self, file_path):
        """
        Parses a Python file and returns a structured representation of its documentation.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source_code = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return None

        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            print(f"Error parsing Python file {file_path}: {e}")
            return None

        doc_data = {
            'file_name': os.path.basename(file_path),
            'module_docstring': self._find_docstring(tree),
            'functions': [],
            'classes': []
        }

        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                doc_data['functions'].append(self._process_function(node))
            elif isinstance(node, ast.ClassDef):
                doc_data['classes'].append(self._process_class(node))

        return doc_data

    def _process_function(self, node):
        docstring = self._find_docstring(node)
        parsed_args, parsed_returns = self._parse_docstring(docstring)
        
        params = [f"{arg.arg}: {ast.unparse(arg.annotation) if arg.annotation else 'any'}" for arg in node.args.args]
        
        return {
            'name': node.name,
            'docstring': docstring,
            'params': params,
            'parsed_args': parsed_args,
            'parsed_returns': parsed_returns
        }

    def _process_class(self, node):
        docstring = self._find_docstring(node)
        class_variables = []
        methods = []

        for sub_node in node.body:
            if isinstance(sub_node, ast.Assign) and all(isinstance(t, ast.Name) for t in sub_node.targets):
                class_variables.append({
                    'name': ast.unparse(sub_node.targets[0]),
                    'value': ast.unparse(sub_node.value)
                })
            elif isinstance(sub_node, ast.FunctionDef):
                methods.append(self._process_method(sub_node))

        return {
            'name': node.name,
            'docstring': docstring,
            'variables': class_variables,
            'methods': methods
        }

    def _process_method(self, node):
        docstring = self._find_docstring(node)
        parsed_args, parsed_returns = self._parse_docstring(docstring)
        
        method_params = [f"{arg.arg}: {ast.unparse(arg.annotation) if arg.annotation else 'any'}" for arg in node.args.args if arg.arg != 'self']
        
        return {
            'name': node.name,
            'docstring': docstring,
            'params': method_params,
            'parsed_args': parsed_args,
            'parsed_returns': parsed_returns
        }

    def _find_docstring(self, node):
        """Finds or generates a docstring for a Python node."""
        docstring = ast.get_docstring(node)
        if not docstring:
            print(f"  - Generating docstring for `{node.name}`...")
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
                source_code = ast.unparse(node)
                docstring = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=f"Generate a Google-style docstring for this Python code:\n```python\n{source_code}\n```"
                ).text.strip().strip('"""')
        return docstring

    def _parse_docstring(self, docstring):
        """Parses a Python docstring for args and returns."""
        if not docstring:
            return {}, {}
        
        args = {}
        returns = {}
        
        args_section_match = re.search(r'Args:\s*?\n(.*?)(?:\n\s*Returns:|\n\s*Raises:|$)', docstring, re.DOTALL)
        if args_section_match:
            args_text = args_section_match.group(1).strip()
            lines = re.split(r'\n\s*[\*-]\s*', args_text)
            for line in lines:
                line = line.strip()
                if not line: continue
                match = re.match(r'(\w+)\s*(?:\((.*?)\))?:\s*(.*)', line)
                if match:
                    param_name, param_type, param_desc = match.groups()
                    args[param_name] = {'type': param_type.strip() if param_type else None, 'desc': param_desc.strip()}
                else:
                    simple_match = re.match(r'(\w+)\s*:\s*(.*)', line)
                    if simple_match:
                        param_name, param_desc = simple_match.groups()
                        args[param_name] = {'type': None, 'desc': param_desc.strip()}

        returns_section_match = re.search(r'Returns:\s*?\n(.*?)(?:\n\s*Raises:|$)', docstring, re.DOTALL)
        if returns_section_match:
            return_line = returns_section_match.group(1).strip()
            match = re.match(r'(.*?):\s*(.*)', return_line)
            if match:
                return_type, return_desc = match.groups()
                returns = {'type': return_type.strip(), 'desc': return_desc.strip()}
            else:
                returns = {'type': None, 'desc': return_line.strip()}

        return args, returns