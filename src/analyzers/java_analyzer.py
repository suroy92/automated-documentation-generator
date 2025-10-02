# src/analyzers/java_analyzer.py

"""
Java-specific analyzer for extracting documentation from Java source files.
"""

import os
import re
import logging
from typing import Optional, Dict, Any, List
import javalang
from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class JavaAnalyzer(BaseAnalyzer):
    """Analyzer for Java source files."""
    
    def _get_language_name(self) -> str:
        return "java"

    def _create_docstring_prompt(self, code_snippet: str) -> str:
        """Create prompt for Java Javadoc generation."""
        return (
            f"Generate a concise Javadoc-style documentation comment for this Java code. "
            f"Include a brief description, @param tags for all parameters, and an @return tag for the return value. "
            f"Return ONLY the comment content without the `/** ... */` block.\n\n"
            f"Code:\n```java\n{code_snippet}\n```"
        )
    
    def _clean_llm_response(self, response: str) -> str:
        """Clean LLM response for Java Javadoc."""
        response = response.strip()
        # Remove any leading `/**` and trailing `*/` if the model includes it
        if response.startswith('/**'):
            response = response[3:]
        if response.endswith('*/'):
            response = response[:-2]
        # Remove any markdown code blocks
        response = re.sub(r'```[\s\S]*?```', '', response).strip()
        return response
    
    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Parse a Java file and return LADOM structure.
        
        Args:
            file_path: Path to the Java file
            
        Returns:
            LADOM structure or None on error
        """
        source_code = self._safe_read_file(file_path)
        if not source_code:
            return None
        
        try:
            tree = javalang.parse.parse(source_code)
        except javalang.parser.JavaSyntaxError as e:
            logger.error(f"Syntax error parsing {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing {file_path}: {e}")
            return None
        
        classes = []
        for path, node in tree.filter(javalang.tree.ClassDeclaration):
            classes.append(self._process_class(node, source_code))

        ladom = {
            "project_name": os.path.basename(os.path.dirname(os.path.abspath(file_path))) or "Java Project",
            "files": [
                {
                    "path": os.path.abspath(file_path),
                    "functions": [],  # Java doesn't have top-level functions
                    "classes": classes
                }
            ]
        }
        
        return self._validate_and_normalize(ladom)

    def _process_class(self, node: javalang.tree.ClassDeclaration, source_code: str) -> Dict[str, Any]:
        """
        Process a class node into LADOM format.
        
        Args:
            node: Javalang class declaration node
            source_code: Full source code
            
        Returns:
            Class dictionary in LADOM format
        """
        docstring = self._find_javadoc(node)
        
        if docstring:
            brief_desc = self._get_brief_description(docstring)
        else:
            # Generate docstring for the entire class
            # Since we can't easily extract position, we'll use the class name
            brief_desc = self._generate_docstring_with_llm(
                f"class {node.name}", 
                node.name
            )

        methods = []
        for member in node.body:
            if isinstance(member, javalang.tree.MethodDeclaration):
                methods.append(self._process_method(member, source_code))
            elif isinstance(member, javalang.tree.ConstructorDeclaration):
                methods.append(self._process_constructor(member, source_code))

        return {
            'name': node.name,
            'description': brief_desc,
            'methods': methods
        }

    def _process_method(self, node: javalang.tree.MethodDeclaration, source_code: str) -> Dict[str, Any]:
        """
        Process a method node into LADOM format.
        
        Args:
            node: Javalang method declaration node
            source_code: Full source code
            
        Returns:
            Method dictionary in LADOM format
        """
        docstring = self._find_javadoc(node)

        if docstring:
            parsed_args, parsed_returns, brief_desc = self._parse_javadoc(docstring)
        else:
            # Generate method signature for LLM
            params_str = ', '.join([f"{p.type.name} {p.name}" for p in node.parameters])
            return_type = node.return_type.name if node.return_type else "void"
            method_sig = f"{return_type} {node.name}({params_str})"
            
            generated_docstring = self._generate_docstring_with_llm(method_sig, node.name)
            parsed_args, parsed_returns, brief_desc = self._parse_javadoc(generated_docstring)
            
        parameters = []
        for param in node.parameters:
            param_info = parsed_args.get(param.name, {})
            param_type = param.type.name if hasattr(param.type, 'name') else str(param.type)
            
            parameters.append({
                "name": param.name,
                "type": param_type,
                "description": param_info.get('description', 'No description available.')
            })

        # Get return type from node
        return_type = node.return_type.name if node.return_type else "void"

        return {
            'name': node.name,
            'description': brief_desc,
            'parameters': parameters,
            'returns': {
                'type': return_type,
                'description': parsed_returns.get('description', 'No return description.')
            }
        }
        
    def _process_constructor(self, node: javalang.tree.ConstructorDeclaration, source_code: str) -> Dict[str, Any]:
        """
        Process a constructor node into LADOM format.
        
        Args:
            node: Javalang constructor declaration node
            source_code: Full source code
            
        Returns:
            Method dictionary in LADOM format
        """
        docstring = self._find_javadoc(node)
        
        if docstring:
            parsed_args, _, brief_desc = self._parse_javadoc(docstring)
        else:
            params_str = ', '.join([f"{p.type.name} {p.name}" for p in node.parameters])
            constructor_sig = f"{node.name}({params_str})"
            
            generated_docstring = self._generate_docstring_with_llm(constructor_sig, node.name)
            parsed_args, _, brief_desc = self._parse_javadoc(generated_docstring)
        
        parameters = []
        for param in node.parameters:
            param_info = parsed_args.get(param.name, {})
            param_type = param.type.name if hasattr(param.type, 'name') else str(param.type)
            
            parameters.append({
                "name": param.name,
                "type": param_type,
                "description": param_info.get('description', 'No description available.')
            })
            
        return {
            'name': node.name,
            'description': brief_desc,
            'parameters': parameters,
            'returns': {
                'type': 'void',
                'description': 'Constructor, no return value.'
            }
        }

    def _find_javadoc(self, node: javalang.tree.Node) -> str:
        """Find Javadoc comment for a node."""
        if hasattr(node, 'documentation') and node.documentation:
            return node.documentation
        return ""

    def _get_brief_description(self, docstring: str) -> str:
        """Extract brief description from a Javadoc docstring."""
        if not docstring:
            return self._get_fallback_docstring()
        
        # Clean up the docstring
        clean_doc = docstring.strip()
        
        # Javadoc's first sentence is the brief description
        # Look for the first period followed by whitespace or end of string
        first_sentence_match = re.search(r'^(.*?\.)\s+(?=@|\s*$|[A-Z])', clean_doc, re.DOTALL)
        if first_sentence_match:
            desc = first_sentence_match.group(1).strip()
        else:
            # Try to get content before first @tag
            tag_match = re.search(r'^(.*?)(?=@)', clean_doc, re.DOTALL)
            if tag_match:
                desc = tag_match.group(1).strip()
            else:
                desc = clean_doc
        
        # Remove asterisks and clean up
        desc = re.sub(r'^\s*\*+\s*', '', desc, flags=re.MULTILINE)
        desc = ' '.join(desc.split())
        
        return desc if desc else self._get_fallback_docstring()

    def _parse_javadoc(self, docstring: str) -> tuple:
        """
        Parse Javadoc comment to extract tags and description.
        
        Args:
            docstring: Javadoc comment string
            
        Returns:
            Tuple of (args_dict, returns_dict, description)
        """
        args = {}
        returns = {'type': 'void', 'description': 'No return description.'}
        description = ""
        
        if not docstring:
            return args, returns, self._get_fallback_docstring()
        
        # Clean docstring
        clean_doc = docstring.strip()
        clean_doc = re.sub(r'^\s*\*+\s*', '', clean_doc, flags=re.MULTILINE)
        
        # Split into main description and tags
        tag_start_match = re.search(r'^\s*@', clean_doc, re.MULTILINE)
        if tag_start_match:
            main_text = clean_doc[:tag_start_match.start()]
            tags_text = clean_doc[tag_start_match.start():]
            description = ' '.join(main_text.strip().split())
        else:
            tags_text = ""
            description = ' '.join(clean_doc.strip().split())

        # Parse @param tags (format: @param name description)
        param_pattern = r'@param\s+(\w+)\s+(.*?)(?=@|\Z)'
        for match in re.finditer(param_pattern, tags_text, re.DOTALL):
            param_name = match.group(1)
            param_desc = ' '.join(match.group(2).strip().split())
            args[param_name] = {'description': param_desc}
        
        # Parse @return tag
        returns_pattern = r'@return\s+(.*?)(?=@|\Z)'
        returns_match = re.search(returns_pattern, tags_text, re.DOTALL)
        if returns_match:
            return_desc = ' '.join(returns_match.group(1).strip().split())
            returns = {'description': return_desc, 'type': 'unknown'}
        
        return args, returns, description if description else self._get_fallback_docstring()