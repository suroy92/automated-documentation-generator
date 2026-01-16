"""
TypeScript analyzer with AST-based parsing and regex fallback.

This module provides comprehensive TypeScript code analysis using tree-sitter
for AST parsing when available, with intelligent regex-based fallback.
"""

import logging
import re
from typing import Dict, List, Optional, Any
from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

# Try to import tree-sitter for AST parsing
try:
    from tree_sitter import Language, Parser
    try:
        from tree_sitter_typescript import language_typescript
        HAS_TREE_SITTER = True
    except ImportError:
        HAS_TREE_SITTER = False
except ImportError:
    HAS_TREE_SITTER = False


class TypeScriptAnalyzer(BaseAnalyzer):
    """
    Analyzer for TypeScript code.
    
    Uses tree-sitter for accurate AST parsing when available,
    falls back to regex patterns otherwise.
    """
    
    def __init__(self):
        super().__init__()
        self.parser = None
        
        # Initialize tree-sitter if available
        if HAS_TREE_SITTER:
            try:
                self.parser = Parser()
                ts_language = Language(language_typescript())
                self.parser.set_language(ts_language)
            except Exception:
                self.parser = None
    
    def _get_language_name(self) -> str:
        return "typescript"
    
    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Analyze TypeScript code and extract structural information.
        
        Args:
            file_path: Path to the TypeScript file
            
        Returns:
            Dictionary containing extracted code structure
        """
        source = self._safe_read_file(file_path)
        if source is None:
            return None
        
        # Try AST-based analysis first if tree-sitter is available
        if HAS_TREE_SITTER and self.parser:
            try:
                result = self._analyze_with_ast(source, file_path)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"AST parsing failed for {file_path}: {e}, falling back to regex")
        
        # Use regex fallback
        return self._analyze_with_regex(source, file_path)
    
    def _analyze_with_ast(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze TypeScript using tree-sitter AST parsing."""
        tree = self.parser.parse(bytes(source, "utf8"))
        root_node = tree.root_node
        
        result = {
            'imports': [],
            'exports': [],
            'classes': [],
            'interfaces': [],
            'functions': [],
            'type_aliases': [],
            'enums': [],
            'constants': [],
            'dependencies': []
        }
        
        # Process all nodes in the AST
        self._process_node(root_node, source.encode('utf8'), result)
        
        return result
    
    def _process_node(self, node, source: bytes, result: Dict):
        """Recursively process AST nodes."""
        node_type = node.type
        
        if node_type == 'import_statement':
            self._extract_import(node, source, result)
        elif node_type == 'export_statement':
            self._extract_export(node, source, result)
        elif node_type == 'class_declaration':
            self._extract_class(node, source, result)
        elif node_type == 'interface_declaration':
            self._extract_interface(node, source, result)
        elif node_type == 'function_declaration':
            self._extract_function(node, source, result)
        elif node_type == 'type_alias_declaration':
            self._extract_type_alias(node, source, result)
        elif node_type == 'enum_declaration':
            self._extract_enum(node, source, result)
        elif node_type == 'lexical_declaration' or node_type == 'variable_declaration':
            self._extract_constant(node, source, result)
        
        # Recursively process children
        for child in node.children:
            self._process_node(child, source, result)
    
    def _get_node_text(self, node, source: bytes) -> str:
        """Extract text from a tree-sitter node."""
        return source[node.start_byte:node.end_byte].decode('utf8')
    
    def _extract_import(self, node, source: bytes, result: Dict):
        """Extract import statement information."""
        import_text = self._get_node_text(node, source)
        
        # Extract module name
        module_match = re.search(r'from\s+[\'"]([^\'"]+)[\'"]', import_text)
        module = module_match.group(1) if module_match else ''
        
        # Extract imported items
        items = []
        if 'import {' in import_text:
            items_match = re.search(r'import\s*\{([^}]+)\}', import_text)
            if items_match:
                items = [item.strip() for item in items_match.group(1).split(',')]
        elif 'import * as' in import_text:
            alias_match = re.search(r'import\s+\*\s+as\s+(\w+)', import_text)
            if alias_match:
                items = [f"* as {alias_match.group(1)}"]
        else:
            default_match = re.search(r'import\s+(\w+)', import_text)
            if default_match:
                items = [default_match.group(1)]
        
        result['imports'].append({
            'module': module,
            'items': items,
            'line': node.start_point[0] + 1
        })
        
        if module and module not in result['dependencies']:
            result['dependencies'].append(module)
    
    def _extract_export(self, node, source: bytes, result: Dict):
        """Extract export statement information."""
        export_text = self._get_node_text(node, source)
        
        # Check for different export types
        if 'export default' in export_text:
            name_match = re.search(r'export\s+default\s+(class|function|interface)?\s*(\w+)', export_text)
            if name_match:
                result['exports'].append({
                    'name': name_match.group(2),
                    'type': 'default',
                    'line': node.start_point[0] + 1
                })
        elif 'export {' in export_text:
            items_match = re.search(r'export\s*\{([^}]+)\}', export_text)
            if items_match:
                items = [item.strip() for item in items_match.group(1).split(',')]
                for item in items:
                    result['exports'].append({
                        'name': item,
                        'type': 'named',
                        'line': node.start_point[0] + 1
                    })
    
    def _extract_class(self, node, source: bytes, result: Dict):
        """Extract class declaration information."""
        class_name = None
        extends = None
        implements = []
        methods = []
        properties = []
        decorators = []
        
        # Get class name
        for child in node.children:
            if child.type == 'type_identifier':
                class_name = self._get_node_text(child, source)
            elif child.type == 'class_heritage':
                heritage_text = self._get_node_text(child, source)
                extends_match = re.search(r'extends\s+(\w+)', heritage_text)
                if extends_match:
                    extends = extends_match.group(1)
                implements_match = re.search(r'implements\s+([^{]+)', heritage_text)
                if implements_match:
                    implements = [i.strip() for i in implements_match.group(1).split(',')]
            elif child.type == 'class_body':
                self._extract_class_members(child, source, methods, properties)
            elif child.type == 'decorator':
                decorator_text = self._get_node_text(child, source)
                decorators.append(decorator_text)
        
        if class_name:
            result['classes'].append({
                'name': class_name,
                'extends': extends,
                'implements': implements,
                'methods': methods,
                'properties': properties,
                'decorators': decorators,
                'line': node.start_point[0] + 1
            })
    
    def _extract_class_members(self, body_node, source: bytes, methods: List, properties: List):
        """Extract methods and properties from a class body."""
        for child in body_node.children:
            if child.type == 'method_definition':
                method_info = self._extract_method(child, source)
                if method_info:
                    methods.append(method_info)
            elif child.type == 'field_definition' or child.type == 'public_field_definition':
                property_info = self._extract_property(child, source)
                if property_info:
                    properties.append(property_info)
    
    def _extract_method(self, node, source: bytes) -> Optional[Dict]:
        """Extract method information from a method node."""
        method_name = None
        params = []
        return_type = None
        is_static = False
        is_async = False
        access_modifier = 'public'
        decorators = []
        
        method_text = self._get_node_text(node, source)
        
        # Check modifiers
        if 'static' in method_text.split('(')[0]:
            is_static = True
        if 'async' in method_text.split('(')[0]:
            is_async = True
        if method_text.strip().startswith('private'):
            access_modifier = 'private'
        elif method_text.strip().startswith('protected'):
            access_modifier = 'protected'
        
        for child in node.children:
            if child.type == 'property_identifier':
                method_name = self._get_node_text(child, source)
            elif child.type == 'formal_parameters':
                params = self._extract_parameters(child, source)
            elif child.type == 'type_annotation':
                return_type = self._get_node_text(child, source).lstrip(':').strip()
            elif child.type == 'decorator':
                decorator_text = self._get_node_text(child, source)
                decorators.append(decorator_text)
        
        if method_name:
            return {
                'name': method_name,
                'params': params,
                'return_type': return_type,
                'is_static': is_static,
                'is_async': is_async,
                'access_modifier': access_modifier,
                'decorators': decorators,
                'line': node.start_point[0] + 1
            }
        return None
    
    def _extract_property(self, node, source: bytes) -> Optional[Dict]:
        """Extract property information from a property node."""
        property_name = None
        property_type = None
        access_modifier = 'public'
        is_static = False
        is_readonly = False
        
        property_text = self._get_node_text(node, source)
        
        # Check modifiers
        if property_text.strip().startswith('private'):
            access_modifier = 'private'
        elif property_text.strip().startswith('protected'):
            access_modifier = 'protected'
        if 'static' in property_text.split(':')[0]:
            is_static = True
        if 'readonly' in property_text.split(':')[0]:
            is_readonly = True
        
        for child in node.children:
            if child.type == 'property_identifier':
                property_name = self._get_node_text(child, source)
            elif child.type == 'type_annotation':
                property_type = self._get_node_text(child, source).lstrip(':').strip()
        
        if property_name:
            return {
                'name': property_name,
                'type': property_type,
                'access_modifier': access_modifier,
                'is_static': is_static,
                'is_readonly': is_readonly,
                'line': node.start_point[0] + 1
            }
        return None
    
    def _extract_interface(self, node, source: bytes, result: Dict):
        """Extract interface declaration information."""
        interface_name = None
        extends = []
        properties = []
        methods = []
        
        for child in node.children:
            if child.type == 'type_identifier':
                interface_name = self._get_node_text(child, source)
            elif child.type == 'extends_clause':
                extends_text = self._get_node_text(child, source)
                extends_match = re.findall(r'\b\w+\b', extends_text)
                extends = [e for e in extends_match if e != 'extends']
            elif child.type == 'object_type':
                self._extract_interface_members(child, source, properties, methods)
        
        if interface_name:
            result['interfaces'].append({
                'name': interface_name,
                'extends': extends,
                'properties': properties,
                'methods': methods,
                'line': node.start_point[0] + 1
            })
    
    def _extract_interface_members(self, body_node, source: bytes, properties: List, methods: List):
        """Extract properties and methods from an interface."""
        for child in body_node.children:
            if child.type == 'property_signature':
                prop_text = self._get_node_text(child, source)
                name_match = re.match(r'(\w+)\s*:\s*(.+)', prop_text)
                if name_match:
                    properties.append({
                        'name': name_match.group(1),
                        'type': name_match.group(2).rstrip(';,').strip()
                    })
            elif child.type == 'method_signature':
                method_text = self._get_node_text(child, source)
                name_match = re.match(r'(\w+)\s*\(([^)]*)\)\s*:\s*(.+)', method_text)
                if name_match:
                    params_str = name_match.group(2)
                    params = []
                    if params_str.strip():
                        for param in params_str.split(','):
                            param = param.strip()
                            param_match = re.match(r'(\w+)\s*:\s*(.+)', param)
                            if param_match:
                                params.append({
                                    'name': param_match.group(1),
                                    'type': param_match.group(2)
                                })
                    
                    methods.append({
                        'name': name_match.group(1),
                        'params': params,
                        'return_type': name_match.group(3).rstrip(';,').strip()
                    })
    
    def _extract_function(self, node, source: bytes, result: Dict):
        """Extract function declaration information."""
        function_name = None
        params = []
        return_type = None
        is_async = False
        is_exported = False
        
        function_text = self._get_node_text(node, source)
        
        if 'async' in function_text.split('(')[0]:
            is_async = True
        if function_text.strip().startswith('export'):
            is_exported = True
        
        for child in node.children:
            if child.type == 'identifier':
                function_name = self._get_node_text(child, source)
            elif child.type == 'formal_parameters':
                params = self._extract_parameters(child, source)
            elif child.type == 'type_annotation':
                return_type = self._get_node_text(child, source).lstrip(':').strip()
        
        if function_name:
            result['functions'].append({
                'name': function_name,
                'params': params,
                'return_type': return_type,
                'is_async': is_async,
                'is_exported': is_exported,
                'line': node.start_point[0] + 1
            })
    
    def _extract_parameters(self, node, source: bytes) -> List[Dict]:
        """Extract function/method parameters."""
        params = []
        
        for child in node.children:
            if child.type == 'required_parameter' or child.type == 'optional_parameter':
                param_text = self._get_node_text(child, source)
                param_match = re.match(r'(\w+)\??\s*:\s*(.+?)(?:\s*=.+)?$', param_text)
                if param_match:
                    params.append({
                        'name': param_match.group(1),
                        'type': param_match.group(2),
                        'optional': '?' in param_text
                    })
                else:
                    # Handle parameter without type annotation
                    name_match = re.match(r'(\w+)', param_text)
                    if name_match:
                        params.append({
                            'name': name_match.group(1),
                            'type': 'any',
                            'optional': False
                        })
        
        return params
    
    def _extract_type_alias(self, node, source: bytes, result: Dict):
        """Extract type alias declaration information."""
        type_name = None
        type_definition = None
        
        for child in node.children:
            if child.type == 'type_identifier':
                type_name = self._get_node_text(child, source)
            elif child.type in ['union_type', 'intersection_type', 'object_type', 'type_identifier']:
                type_definition = self._get_node_text(child, source)
        
        if type_name and type_definition:
            result['type_aliases'].append({
                'name': type_name,
                'definition': type_definition,
                'line': node.start_point[0] + 1
            })
    
    def _extract_enum(self, node, source: bytes, result: Dict):
        """Extract enum declaration information."""
        enum_name = None
        members = []
        
        for child in node.children:
            if child.type == 'identifier':
                enum_name = self._get_node_text(child, source)
            elif child.type == 'enum_body':
                for member in child.children:
                    if member.type == 'property_identifier':
                        member_text = self._get_node_text(member, source)
                        members.append(member_text)
        
        if enum_name:
            result['enums'].append({
                'name': enum_name,
                'members': members,
                'line': node.start_point[0] + 1
            })
    
    def _extract_constant(self, node, source: bytes, result: Dict):
        """Extract constant/variable declarations."""
        declaration_text = self._get_node_text(node, source)
        
        # Only capture const declarations at module level
        if declaration_text.strip().startswith('const'):
            const_match = re.search(r'const\s+(\w+)\s*:\s*([^=]+)?\s*=', declaration_text)
            if const_match:
                result['constants'].append({
                    'name': const_match.group(1),
                    'type': const_match.group(2).strip() if const_match.group(2) else None,
                    'line': node.start_point[0] + 1
                })
    
    def _analyze_with_regex(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Fallback analysis using regex patterns."""
        result = {
            'imports': [],
            'exports': [],
            'classes': [],
            'interfaces': [],
            'functions': [],
            'type_aliases': [],
            'enums': [],
            'constants': [],
            'dependencies': []
        }
        
        lines = source.split('\n')
        
        for i, line in enumerate(lines, 1):
            line = line.strip()
            
            # Extract imports
            if line.startswith('import '):
                import_match = re.match(r'import\s+(?:\{([^}]+)\}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]', line)
                if import_match:
                    items = []
                    if import_match.group(1):  # Named imports
                        items = [item.strip() for item in import_match.group(1).split(',')]
                    elif import_match.group(2):  # Default import
                        items = [import_match.group(2)]
                    elif import_match.group(3):  # Namespace import
                        items = [f"* as {import_match.group(3)}"]
                    
                    module = import_match.group(4)
                    result['imports'].append({
                        'module': module,
                        'items': items,
                        'line': i
                    })
                    
                    if module and module not in result['dependencies']:
                        result['dependencies'].append(module)
            
            # Extract exports
            elif line.startswith('export '):
                if 'export default' in line:
                    default_match = re.search(r'export\s+default\s+(?:class|function|interface)?\s*(\w+)', line)
                    if default_match:
                        result['exports'].append({
                            'name': default_match.group(1),
                            'type': 'default',
                            'line': i
                        })
                elif 'export {' in line:
                    exports_match = re.search(r'export\s*\{([^}]+)\}', line)
                    if exports_match:
                        items = [item.strip() for item in exports_match.group(1).split(',')]
                        for item in items:
                            result['exports'].append({
                                'name': item,
                                'type': 'named',
                                'line': i
                            })
            
            # Extract classes
            elif 'class ' in line:
                class_match = re.match(r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?', line)
                if class_match:
                    implements = []
                    if class_match.group(3):
                        implements = [impl.strip() for impl in class_match.group(3).split(',')]
                    
                    result['classes'].append({
                        'name': class_match.group(1),
                        'extends': class_match.group(2),
                        'implements': implements,
                        'methods': [],
                        'properties': [],
                        'decorators': [],
                        'line': i
                    })
            
            # Extract interfaces
            elif 'interface ' in line:
                interface_match = re.match(r'(?:export\s+)?interface\s+(\w+)(?:\s+extends\s+([^{]+))?', line)
                if interface_match:
                    extends = []
                    if interface_match.group(2):
                        extends = [ext.strip() for ext in interface_match.group(2).split(',')]
                    
                    result['interfaces'].append({
                        'name': interface_match.group(1),
                        'extends': extends,
                        'properties': [],
                        'methods': [],
                        'line': i
                    })
            
            # Extract functions
            elif 'function ' in line:
                function_match = re.match(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?', line)
                if function_match:
                    params_str = function_match.group(2)
                    params = []
                    if params_str.strip():
                        for param in params_str.split(','):
                            param = param.strip()
                            param_match = re.match(r'(\w+)(?:\?)?(?:\s*:\s*([^=]+))?', param)
                            if param_match:
                                params.append({
                                    'name': param_match.group(1),
                                    'type': param_match.group(2).strip() if param_match.group(2) else 'any',
                                    'optional': '?' in param
                                })
                    
                    result['functions'].append({
                        'name': function_match.group(1),
                        'params': params,
                        'return_type': function_match.group(3).strip() if function_match.group(3) else None,
                        'is_async': 'async' in line,
                        'is_exported': line.strip().startswith('export'),
                        'line': i
                    })
            
            # Extract type aliases
            elif 'type ' in line and '=' in line:
                type_match = re.match(r'(?:export\s+)?type\s+(\w+)\s*=\s*(.+)', line)
                if type_match:
                    result['type_aliases'].append({
                        'name': type_match.group(1),
                        'definition': type_match.group(2).rstrip(';').strip(),
                        'line': i
                    })
            
            # Extract enums
            elif 'enum ' in line:
                enum_match = re.match(r'(?:export\s+)?enum\s+(\w+)', line)
                if enum_match:
                    result['enums'].append({
                        'name': enum_match.group(1),
                        'members': [],
                        'line': i
                    })
            
            # Extract constants
            elif line.startswith('const '):
                const_match = re.match(r'const\s+(\w+)\s*:\s*([^=]+)?\s*=', line)
                if const_match:
                    result['constants'].append({
                        'name': const_match.group(1),
                        'type': const_match.group(2).strip() if const_match.group(2) else None,
                        'line': i
                    })
        
        return result
