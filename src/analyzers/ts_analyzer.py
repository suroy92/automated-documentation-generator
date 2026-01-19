"""
TypeScript analyzer with AST-based parsing and regex fallback.

This module provides TypeScript code analysis using tree-sitter for AST parsing
when available, with regex-based fallback for reliability.
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
        logger.warning("tree-sitter-typescript not available, using regex fallback")
except ImportError:
    HAS_TREE_SITTER = False
    logger.warning("tree-sitter not available, using regex fallback")


class TypeScriptAnalyzer(BaseAnalyzer):
    """
    Analyzer for TypeScript code.
    
    Uses tree-sitter AST parsing when available, falls back to regex patterns.
    Generates documentation using LLM.
    """
    
    def __init__(self, client=None, cache=None, rate_limiter=None):
        super().__init__(client=client, cache=cache, rate_limiter=rate_limiter)
        self.parser = None
        
        # Initialize tree-sitter if available
        if HAS_TREE_SITTER:
            try:
                ts_language = Language(language_typescript())
                self.parser = Parser(ts_language)
                logger.debug("TypeScript AST parser initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize TypeScript parser: {e}")
                self.parser = None
    
    def _get_language_name(self) -> str:
        return "typescript"
    
    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Analyze TypeScript code and extract structural information.
        
        Args:
            file_path: Path to the TypeScript file
            
        Returns:
            Dictionary containing extracted code structure in LADOM format
        """
        source = self._safe_read_file(file_path)
        if source is None:
            return None
        
        # Try AST-based analysis first
        if self.parser:
            try:
                result = self._analyze_with_ast(source, file_path)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"AST parsing failed for {file_path}: {e}, falling back to regex")
        
        # Fallback to regex
        return self._analyze_with_regex(source, file_path)
    
    # ==================== AST-Based Analysis ====================
    
    def _analyze_with_ast(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze using tree-sitter AST."""
        tree = self.parser.parse(bytes(source, "utf8"))
        root_node = tree.root_node
        
        file_entry: Dict[str, Any] = {
            "path": file_path,
            "summary": "",
            "functions": [],
            "classes": [],
        }
        
        # Process all top-level nodes
        for node in root_node.children:
            if node.type == 'function_declaration':
                func_sym = self._process_function_ast(node, source, file_path)
                if func_sym:
                    file_entry["functions"].append(func_sym)
            elif node.type == 'class_declaration':
                class_obj = self._process_class_ast(node, source, file_path)
                if class_obj:
                    file_entry["classes"].append(class_obj)
            elif node.type == 'export_statement':
                # Handle exported functions/classes
                for child in node.children:
                    if child.type == 'function_declaration':
                        func_sym = self._process_function_ast(child, source, file_path)
                        if func_sym:
                            file_entry["functions"].append(func_sym)
                    elif child.type == 'class_declaration':
                        class_obj = self._process_class_ast(child, source, file_path)
                        if class_obj:
                            file_entry["classes"].append(class_obj)
        
        return {"files": [file_entry]}
    
    def _process_function_ast(self, node, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Process a function node from AST."""
        name = None
        params_list = []
        return_type = ""
        is_async = False
        
        # Extract function details
        for child in node.children:
            if child.type == 'identifier':
                name = self._get_node_text(child, source)
            elif child.type == 'formal_parameters':
                params_list = self._extract_params_ast(child, source)
            elif child.type == 'type_annotation':
                return_type = self._get_node_text(child, source).lstrip(':').strip()
        
        # Check for async
        func_text = self._get_node_text(node, source)
        is_async = func_text.strip().startswith('async')
        
        if not name:
            return None
        
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        
        # Get function body for documentation
        snippet = self._get_node_text(node, source)
        
        # Build params string for signature
        params_str = ', '.join([
            f"{p['name']}{('?' if p.get('optional') else '')}: {p.get('type', 'any')}"
            for p in params_list
        ])
        
        context = f"function {name}({params_str})"
        docstring, details = self.generate_doc(snippet, node_name=name, context=context)
        
        # Merge AST params with LLM details
        params = self._merge_params_ast(params_list, details.get("params") or [])
        
        summary = (details.get("summary") or "").strip()
        examples = details.get("examples") or []
        dret = details.get("returns") or {}
        returns = {
            "type": return_type or (dret.get("type") or "").strip(),
            "description": (dret.get("desc") or dret.get("description") or "").strip()
        }
        
        return {
            "name": name,
            "signature": f"({params_str})" + (f" => {return_type}" if return_type else ""),
            "description": summary,
            "parameters": params,
            "returns": returns,
            "throws": details.get("throws") or [],
            "examples": examples,
            "performance": details.get("performance") or {"time_complexity": "", "space_complexity": "", "notes": ""},
            "error_handling": details.get("error_handling") or {"strategy": "", "recovery": "", "logging": ""},
            "lines": {"start": start_line, "end": end_line},
            "file_path": file_path,
            "language_hint": "typescript",
        }
    
    def _process_class_ast(self, node, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Process a class node from AST."""
        class_name = None
        extends = ""
        methods = []
        
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        
        for child in node.children:
            if child.type == 'type_identifier':
                class_name = self._get_node_text(child, source)
            elif child.type == 'class_heritage':
                heritage_text = self._get_node_text(child, source)
                extends_match = re.search(r'extends\s+(\w+)', heritage_text)
                if extends_match:
                    extends = extends_match.group(1)
            elif child.type == 'class_body':
                methods = self._extract_class_methods_ast(child, source, file_path, class_name or "Unknown", start_line)
        
        if not class_name:
            return None
        
        return {
            "name": class_name,
            "description": "",
            "extends": extends,
            "methods": methods,
            "lines": {"start": start_line, "end": end_line},
            "file_path": file_path,
            "language_hint": "typescript",
        }
    
    def _extract_class_methods_ast(self, class_body_node, source: str, file_path: str, 
                                    class_name: str, class_start_line: int) -> List[Dict[str, Any]]:
        """Extract methods from a class body AST node."""
        methods = []
        
        for child in class_body_node.children:
            if child.type == 'method_definition':
                method_name = None
                params_list = []
                return_type = ""
                is_static = False
                is_async = False
                access_modifier = "public"
                
                # Get method text to check modifiers
                method_text = self._get_node_text(child, source)
                if 'private' in method_text.split('(')[0]:
                    access_modifier = "private"
                elif 'protected' in method_text.split('(')[0]:
                    access_modifier = "protected"
                is_static = 'static' in method_text.split('(')[0]
                is_async = 'async' in method_text.split('(')[0]
                
                for subchild in child.children:
                    if subchild.type == 'property_identifier':
                        method_name = self._get_node_text(subchild, source)
                    elif subchild.type == 'formal_parameters':
                        params_list = self._extract_params_ast(subchild, source)
                    elif subchild.type == 'type_annotation':
                        return_type = self._get_node_text(subchild, source).lstrip(':').strip()
                
                if not method_name:
                    continue
                
                start_line = child.start_point[0] + 1
                end_line = child.end_point[0] + 1
                
                snippet = self._get_node_text(child, source)
                is_constructor = method_name == "constructor"
                
                params_str = ', '.join([
                    f"{p['name']}{('?' if p.get('optional') else '')}: {p.get('type', 'any')}"
                    for p in params_list
                ])
                
                context = f"class {class_name} :: {method_name}({params_str})"
                docstring, details = self.generate_doc(snippet, node_name=method_name, context=context)
                
                if is_constructor:
                    summary = self._sanitize_constructor_summary(class_name, details.get("summary") or "")
                    examples = []
                    returns = {"type": "", "description": ""}
                else:
                    summary = (details.get("summary") or "").strip()
                    examples = details.get("examples") or []
                    dret = details.get("returns") or {}
                    returns = {
                        "type": return_type or (dret.get("type") or "").strip(),
                        "description": (dret.get("desc") or dret.get("description") or "").strip()
                    }
                
                params = self._merge_params_ast(params_list, details.get("params") or [])
                
                methods.append({
                    "name": method_name,
                    "signature": f"({params_str})" + (f" => {return_type}" if return_type else ""),
                    "description": summary,
                    "parameters": params,
                    "returns": returns,
                    "throws": details.get("throws") or [],
                    "examples": examples,
                    "performance": details.get("performance") or {"time_complexity": "", "space_complexity": "", "notes": ""},
                    "error_handling": details.get("error_handling") or {"strategy": "", "recovery": "", "logging": ""},
                    "lines": {"start": start_line, "end": end_line},
                    "file_path": file_path,
                    "language_hint": "typescript",
                })
        
        return methods
    
    def _extract_params_ast(self, params_node, source: str) -> List[Dict[str, Any]]:
        """Extract parameters from formal_parameters node."""
        params = []
        
        for child in params_node.children:
            if child.type in ['required_parameter', 'optional_parameter']:
                param_name = None
                param_type = "any"
                optional = child.type == 'optional_parameter'
                default_val = None
                
                param_text = self._get_node_text(child, source)
                
                # Parse: name?: type = default
                if '=' in param_text:
                    parts = param_text.split('=')
                    default_val = parts[1].strip()
                    param_text = parts[0].strip()
                
                if '?' in param_text:
                    optional = True
                    param_text = param_text.replace('?', '')
                
                if ':' in param_text:
                    name_type = param_text.split(':')
                    param_name = name_type[0].strip()
                    param_type = name_type[1].strip()
                else:
                    param_name = param_text.strip()
                
                if param_name:
                    params.append({
                        "name": param_name,
                        "type": param_type,
                        "optional": optional,
                        "default": default_val
                    })
        
        return params
    
    def _merge_params_ast(self, ast_params: List[Dict[str, Any]], llm_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge AST-extracted params with LLM descriptions."""
        llm_map = {p.get("name"): p for p in llm_params if p.get("name")}
        
        merged = []
        for ast_p in ast_params:
            name = ast_p["name"]
            llm_p = llm_map.get(name, {})
            
            merged.append({
                "name": name,
                "type": (llm_p.get("type") or ast_p.get("type") or "any").strip(),
                "default": llm_p.get("default", ast_p.get("default")),
                "description": (llm_p.get("desc") or llm_p.get("description") or "").strip(),
                "optional": ast_p.get("optional", False) or bool(llm_p.get("optional")),
            })
        
        return merged
    
    def _get_node_text(self, node, source: str) -> str:
        """Extract text from a tree-sitter node."""
        return source[node.start_byte:node.end_byte]
    
    # ==================== Regex-Based Fallback ====================
    
    def _analyze_with_regex(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze using regex patterns to generate LADOM structure."""
        file_entry: Dict[str, Any] = {
            "path": file_path,
            "summary": "",
            "functions": [],
            "classes": [],
        }
        
        # Extract functions
        func_pattern = re.compile(
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{',
            re.MULTILINE
        )
        
        for match in func_pattern.finditer(source):
            name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3).strip() if match.group(3) else ""
            start_line = source.count('\n', 0, match.start()) + 1
            
            # Extract function body
            snippet = self._extract_brace_block(source, match.end() - 1)
            end_line = start_line + snippet.count('\n')
            
            func_sym = self._build_function_symbol(
                name, params_str, return_type, snippet, file_path, start_line, end_line
            )
            file_entry["functions"].append(func_sym)
        
        # Extract classes
        class_pattern = re.compile(
            r'(?:export\s+)?(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?\s*\{',
            re.MULTILINE
        )
        
        for match in class_pattern.finditer(source):
            class_name = match.group(1)
            extends = match.group(2) or ""
            start_line = source.count('\n', 0, match.start()) + 1
            
            # Extract class body
            class_body = self._extract_brace_block(source, match.end() - 1)
            methods = self._extract_class_methods(class_body, class_name, file_path, start_line)
            
            file_entry["classes"].append({
                "name": class_name,
                "description": "",
                "extends": extends,
                "methods": methods,
                "lines": {"start": start_line, "end": start_line + class_body.count('\n')},
                "file_path": file_path,
                "language_hint": "typescript",
            })
        
        return {"files": [file_entry]}
    
    def _extract_class_methods(self, class_body: str, class_name: str, file_path: str, class_start_line: int) -> List[Dict[str, Any]]:
        """Extract methods from a class body."""
        methods = []
        
        # Method pattern
        method_pattern = re.compile(
            r'\n\s*(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:async\s+)?(\w+)\s*\(([^)]*)\)(?:\s*:\s*([^{]+))?\s*\{',
            re.MULTILINE
        )
        
        for match in method_pattern.finditer(class_body):
            method_name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3).strip() if match.group(3) else ""
            start_line = class_start_line + class_body.count('\n', 0, match.start())
            
            snippet = self._extract_brace_block(class_body, match.end() - 1)
            end_line = start_line + snippet.count('\n')
            
            is_constructor = method_name == "constructor"
            context = f"class {class_name} :: {method_name}({params_str.strip()})"
            
            method_sym = self._build_function_symbol(
                method_name, params_str, return_type, snippet, file_path, 
                start_line, end_line, context, is_constructor, class_name
            )
            methods.append(method_sym)
        
        return methods
    
    def _build_function_symbol(
        self, name: str, params_str: str, return_type: str, code_snippet: str,
        file_path: str, start_line: int, end_line: int, context: str = "",
        is_constructor: bool = False, class_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build function/method symbol with LLM-generated documentation."""
        
        if not context:
            context = f"function {name}({params_str.strip()})"
        
        docstring, details = self.generate_doc(code_snippet, node_name=name, context=context)
        
        if is_constructor:
            summary = self._sanitize_constructor_summary(class_name or "Class", details.get("summary") or "")
            examples = []
            returns = {"type": "", "description": ""}
        else:
            summary = (details.get("summary") or "").strip()
            examples = details.get("examples") or []
            dret = details.get("returns") or {}
            returns = {
                "type": return_type or (dret.get("type") or "").strip(),
                "description": (dret.get("desc") or dret.get("description") or "").strip()
            }
        
        params = self._parse_typescript_params(params_str, details.get("params") or [])
        
        return {
            "name": name,
            "signature": f"({params_str.strip()})" + (f" => {return_type}" if return_type else ""),
            "description": summary,
            "parameters": params,
            "returns": returns,
            "throws": details.get("throws") or [],
            "examples": examples,
            "performance": details.get("performance") or {"time_complexity": "", "space_complexity": "", "notes": ""},
            "error_handling": details.get("error_handling") or {"strategy": "", "recovery": "", "logging": ""},
            "lines": {"start": start_line, "end": end_line},
            "file_path": file_path,
            "language_hint": "typescript",
        }
    
    def _parse_typescript_params(self, params_str: str, llm_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse TypeScript parameters and merge with LLM descriptions."""
        if not params_str.strip():
            return []
        
        llm_map = {p.get("name"): p for p in llm_params if p.get("name")}
        parsed = []
        
        for param in params_str.split(','):
            param = param.strip()
            if not param:
                continue
            
            # Parse: name?: type = default
            optional = '?' in param
            param = param.replace('?', '')
            
            parts = param.split('=')
            default = parts[1].strip() if len(parts) > 1 else None
            
            name_type = parts[0].strip().split(':')
            name = name_type[0].strip()
            param_type = name_type[1].strip() if len(name_type) > 1 else "any"
            
            llm_p = llm_map.get(name, {})
            
            parsed.append({
                "name": name,
                "type": (llm_p.get("type") or param_type).strip(),
                "default": llm_p.get("default", default),
                "description": (llm_p.get("desc") or llm_p.get("description") or "").strip(),
                "optional": optional or (default is not None),
            })
        
        return parsed
    
    def _extract_brace_block(self, source: str, start_pos: int) -> str:
        """Extract code block between braces."""
        depth = 1
        i = start_pos
        while i < len(source) and depth > 0:
            if source[i] == '{':
                depth += 1
            elif source[i] == '}':
                depth -= 1
            i += 1
        return source[start_pos:i]
    
    def _sanitize_constructor_summary(self, class_name: str, llm_summary: str) -> str:
        """Sanitize constructor summary to avoid redundancy."""
        if not llm_summary:
            return f"Creates a new instance of {class_name}."
        
        lower_summary = llm_summary.lower()
        if "constructor" in lower_summary or "creates" in lower_summary or "initializes" in lower_summary:
            return llm_summary
        
        return f"Creates a new instance of {class_name}. {llm_summary}"
