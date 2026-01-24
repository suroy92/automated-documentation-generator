# src/utils/example_extractor.py
"""
Extracts meaningful code examples and usage patterns from the codebase.

Identifies:
- Main execution blocks
- Common usage patterns
- Configuration examples
- API usage examples
- Test cases that demonstrate functionality
"""

from __future__ import annotations
import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExampleExtractor:
    """Finds and formats code examples for documentation."""

    def __init__(self, ladom_data: Dict[str, Any], project_path: str):
        """
        Initialize the example extractor.
        
        Args:
            ladom_data: The aggregated LADOM data
            project_path: Root path of the project
        """
        self.ladom_data = ladom_data
        self.project_path = Path(project_path)
        self.files = ladom_data.get("files", [])

    def extract_all_examples(self) -> Dict[str, Any]:
        """
        Extract all types of examples.
        
        Returns:
            Dict containing various types of examples
        """
        return {
            "usage_examples": self.extract_usage_examples(),
            "configuration_examples": self.extract_configuration_examples(),
            "api_examples": self.extract_api_examples(),
            "cli_examples": self.extract_cli_examples(),
            "import_examples": self.extract_import_examples()
        }

    def extract_usage_examples(self) -> List[Dict[str, str]]:
        """
        Extract typical usage patterns from code.
        
        Looks for:
        - if __name__ == "__main__" blocks
        - Example functions
        - Demo code
        
        Returns:
            List of usage examples
        """
        examples = []
        
        for file_data in self.files:
            file_path = file_data.get("path", "")
            
            # Skip test files
            if "test" in file_path.lower():
                continue
            
            # Check for main execution blocks
            if self._has_main_block(file_path):
                example = self._extract_main_block(file_path)
                if example:
                    examples.append({
                        "title": "Basic Usage",
                        "description": f"Example from {Path(file_path).name}",
                        "code": example,
                        "language": "python"
                    })
            
            # Look for functions with "example" or "demo" in name
            for func in file_data.get("functions", []):
                func_name = func.get("name", "").lower()
                if any(keyword in func_name for keyword in ["example", "demo", "sample"]):
                    examples.append({
                        "title": f"Example: {func.get('name')}",
                        "description": func.get("description", ""),
                        "code": self._format_function_signature(func),
                        "language": "python"
                    })
        
        return examples[:5]  # Limit to 5 examples

    def _has_main_block(self, file_path: str) -> bool:
        """Check if file has a __main__ block."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                return 'if __name__ == "__main__"' in content or "if __name__ == '__main__'" in content
        except Exception as e:
            logger.debug(f"Error checking main block in {file_path}: {e}")
            return False

    def _extract_main_block(self, file_path: str) -> Optional[str]:
        """Extract code from __main__ block."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.If):
                    # Check if it's __name__ == "__main__"
                    if isinstance(node.test, ast.Compare):
                        left = node.test.left
                        if isinstance(left, ast.Name) and left.id == "__name__":
                            # Extract the code
                            try:
                                lines = content.split('\n')
                                start_line = node.lineno - 1
                                end_line = getattr(node, 'end_lineno', start_line + 10)
                                
                                # Get the main block code
                                main_code = '\n'.join(lines[start_line:end_line])
                                
                                # Extract just the body (indented part)
                                body_lines = []
                                in_body = False
                                for line in main_code.split('\n'):
                                    if 'if __name__' in line:
                                        in_body = True
                                        continue
                                    if in_body and line.strip():
                                        body_lines.append(line)
                                
                                if body_lines:
                                    # Remove common indentation
                                    min_indent = min(len(line) - len(line.lstrip()) 
                                                   for line in body_lines if line.strip())
                                    clean_lines = [line[min_indent:] if len(line) > min_indent else line 
                                                 for line in body_lines]
                                    return '\n'.join(clean_lines[:15])  # Limit lines
                            except Exception as e:
                                logger.debug(f"Error extracting main block: {e}")
            
            return None
        except Exception as e:
            logger.debug(f"Error parsing {file_path}: {e}")
            return None

    def extract_configuration_examples(self) -> List[Dict[str, str]]:
        """
        Find and extract configuration examples.
        
        Returns:
            List of configuration examples
        """
        examples = []
        
        # Common config file patterns
        config_files = [
            "config.yaml",
            "config.yml",
            "config.json",
            ".env.example",
            "settings.py",
            "configuration.py"
        ]
        
        for config_file in config_files:
            file_path = self.project_path / config_file
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Limit size
                    if len(content) > 1000:
                        content = content[:1000] + "\n# ... (truncated)"
                    
                    # Determine language
                    if config_file.endswith('.yaml') or config_file.endswith('.yml'):
                        lang = "yaml"
                    elif config_file.endswith('.json'):
                        lang = "json"
                    else:
                        lang = "python"
                    
                    examples.append({
                        "title": f"Configuration: {config_file}",
                        "description": f"Configuration settings from {config_file}",
                        "code": content,
                        "language": lang
                    })
                except Exception as e:
                    logger.debug(f"Error reading config file {file_path}: {e}")
        
        return examples

    def extract_api_examples(self) -> List[Dict[str, str]]:
        """
        Extract API usage examples.
        
        Looks for route handlers, API endpoints, etc.
        
        Returns:
            List of API examples
        """
        examples = []
        
        for file_data in self.files:
            file_path = file_data.get("path", "")
            
            # Look for API-related files
            if not any(keyword in file_path.lower() for keyword in ["api", "route", "endpoint", "handler"]):
                continue
            
            # Find decorated functions (likely endpoints)
            for func in file_data.get("functions", []):
                decorators = func.get("decorators", [])
                
                # Check for common API decorators
                if any(dec for dec in decorators if any(keyword in dec.lower() 
                       for keyword in ["route", "get", "post", "put", "delete", "api"])):
                    
                    code = self._format_function_with_decorator(func)
                    examples.append({
                        "title": f"API Endpoint: {func.get('name')}",
                        "description": func.get("description", "API endpoint handler"),
                        "code": code,
                        "language": "python"
                    })
            
            if len(examples) >= 3:
                break
        
        return examples

    def extract_cli_examples(self) -> List[Dict[str, str]]:
        """
        Extract CLI usage examples.
        
        Looks for argparse usage, click commands, etc.
        
        Returns:
            List of CLI examples
        """
        examples = []
        
        for file_data in self.files:
            # Check for CLI-related imports
            imports = file_data.get("imports", [])
            has_cli = any(imp for imp in imports if any(keyword in str(imp).lower() 
                         for keyword in ["argparse", "click", "typer", "fire"]))
            
            if not has_cli:
                continue
            
            # Look for parser or CLI setup
            for func in file_data.get("functions", []):
                func_name = func.get("name", "").lower()
                description = func.get("description", "").lower()
                
                if any(keyword in func_name or keyword in description 
                      for keyword in ["parse", "cli", "command", "main"]):
                    
                    code = self._format_function_signature(func)
                    examples.append({
                        "title": f"CLI: {func.get('name')}",
                        "description": func.get("description", "Command-line interface"),
                        "code": code,
                        "language": "python"
                    })
                    break
        
        # Add a generic CLI example if entry point exists
        if not examples:
            entry_points = [f for f in self.files if "main.py" in f.get("path", "")]
            if entry_points:
                examples.append({
                    "title": "Running the Application",
                    "description": "Basic command to run the application",
                    "code": f"python {Path(entry_points[0].get('path', 'main.py')).name}",
                    "language": "bash"
                })
        
        return examples

    def extract_import_examples(self) -> List[Dict[str, str]]:
        """
        Extract examples of how to import and use the project's modules.
        
        Returns:
            List of import examples
        """
        examples = []
        
        # Find main modules (those with classes or many functions)
        main_modules = []
        
        for file_data in self.files:
            file_path = file_data.get("path", "")
            
            # Skip test files and __init__ files
            if "test" in file_path.lower() or "__init__" in file_path:
                continue
            
            classes = file_data.get("classes", [])
            functions = file_data.get("functions", [])
            
            # Consider it a main module if it has classes or multiple functions
            if len(classes) > 0 or len(functions) >= 3:
                main_modules.append(file_data)
        
        # Create import examples for top modules
        for module in main_modules[:3]:
            file_path = module.get("path", "")
            module_name = Path(file_path).stem
            
            # Get main classes
            classes = module.get("classes", [])
            functions = module.get("functions", [])
            
            import_lines = []
            if classes:
                class_names = [cls.get("name") for cls in classes[:2]]
                import_lines.append(f"from {module_name} import {', '.join(class_names)}")
            elif functions:
                func_names = [func.get("name") for func in functions[:3] 
                            if not func.get("name", "").startswith("_")]
                if func_names:
                    import_lines.append(f"from {module_name} import {', '.join(func_names)}")
            
            if import_lines:
                examples.append({
                    "title": f"Importing from {module_name}",
                    "description": f"How to import and use {module_name} module",
                    "code": "\n".join(import_lines),
                    "language": "python"
                })
        
        return examples

    def _format_function_signature(self, func: Dict[str, Any]) -> str:
        """Format a function signature with parameters."""
        name = func.get("name", "unknown")
        signature = func.get("signature", "()")
        description = func.get("description", "")
        
        lines = []
        if description:
            lines.append(f'"""' + description[:100] + '"""')
        lines.append(f"def {name}{signature}:")
        lines.append("    # Function implementation")
        
        return "\n".join(lines)

    def _format_function_with_decorator(self, func: Dict[str, Any]) -> str:
        """Format a function with its decorators."""
        decorators = func.get("decorators", [])
        name = func.get("name", "unknown")
        signature = func.get("signature", "()")
        description = func.get("description", "")
        
        lines = []
        for dec in decorators[:2]:  # Limit to 2 decorators
            lines.append(f"@{dec}")
        
        lines.append(f"def {name}{signature}:")
        if description:
            lines.append(f'    """' + description[:100] + '"""')
        lines.append("    # Implementation")
        
        return "\n".join(lines)
