# src/analyzers/js_analyzer.py
"""
JavaScript analyzer with integrated AST-based parsing (esprima) and regex fallback.

AST Mode (when esprima available):
- Full structural analysis via Abstract Syntax Tree
- Accurate parameter extraction with defaults/destructuring
- Async/generator/arrow function detection
- Import/export analysis
- Precise location tracking

Regex Fallback Mode:
- Pattern-based extraction
- Basic function and class detection
- Good enough for documentation generation
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

# Try to import esprima for AST parsing
try:
    import esprima
    HAS_ESPRIMA = True
except ImportError:
    esprima = None
    HAS_ESPRIMA = False

# Regex patterns for fallback mode
FUNC_RE = re.compile(
    r"(^|\n)\s*function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)
ARROW_RE = re.compile(
    r"(^|\n)\s*const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\((?P<args>[^)]*)\)\s*=>\s*\{",
    re.MULTILINE,
)
CLASS_RE = re.compile(
    r"(^|\n)\s*class\s+(?P<name>[A-Za-z_$][\w$]*)[^{]*\{(?P<body>.*?)}",
    re.DOTALL,
)
METHOD_RE = re.compile(
    r"\n\s*(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)
CLASS_FIELD_ARROW_RE = re.compile(
    r"\n\s*(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\((?P<args>[^)]*)\)\s*=>\s*\{",
    re.MULTILINE,
)
CTOR_THIS_FN_RE = re.compile(
    r"\bthis\.(?P<name>[A-Za-z_$][\w$]*)\s*=\s*function\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)
CTOR_THIS_ARROW_RE = re.compile(
    r"\bthis\.(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\((?P<args>[^)]*)\)\s*=>\s*\{",
    re.MULTILINE,
)
PROTOTYPE_RE = re.compile(
    r"(?P<class>[A-Za-z_$][\w$]*)\.prototype\.(?P<name>[A-Za-z_$][\w$]*)\s*=\s*function\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)


class JavaScriptAnalyzer(BaseAnalyzer):
    """JavaScript analyzer with AST support and regex fallback."""

    def _get_language_name(self) -> str:
        return "javascript"

    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze JavaScript file using AST if available, otherwise regex."""
        source = self._safe_read_file(file_path)
        if source is None:
            return None

        # Try AST-based analysis first
        if HAS_ESPRIMA:
            result = self._analyze_with_ast(source, file_path)
            if result:
                return result
            logger.warning(f"AST parsing failed for {file_path}, falling back to regex")

        # Fallback to regex-based analysis
        return self._analyze_with_regex(source, file_path)

    # ==================== AST-Based Analysis ====================

    def _analyze_with_ast(self, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Analyze using esprima AST."""
        try:
            tree = esprima.parseScript(source, {"loc": True, "range": True, "comment": True})
        except Exception as e:
            logger.debug(f"Failed to parse as script: {e}, trying module...")
            try:
                tree = esprima.parseModule(source, {"loc": True, "range": True, "comment": True})
            except Exception as e2:
                logger.error(f"Failed to parse {file_path}: {e2}")
                return None

        file_entry: Dict[str, Any] = {
            "path": file_path,
            "summary": self._extract_file_comment_ast(tree, source),
            "functions": [],
            "classes": [],
        }

        for node in tree.body:
            self._process_top_level_node_ast(node, source, file_path, file_entry)

        return {"files": [file_entry]}

    def _process_top_level_node_ast(
        self, node: Any, source: str, file_path: str, file_entry: Dict[str, Any]
    ) -> None:
        """Process top-level AST nodes."""
        node_type = node.type

        if node_type == "FunctionDeclaration":
            func = self._process_function_ast(node, source, file_path)
            if func:
                file_entry["functions"].append(func)

        elif node_type == "VariableDeclaration":
            for decl in node.declarations:
                if decl.init and self._is_function_node(decl.init):
                    func = self._process_function_ast(decl.init, source, file_path, name=decl.id.name)
                    if func:
                        file_entry["functions"].append(func)

        elif node_type == "ClassDeclaration":
            cls = self._process_class_ast(node, source, file_path)
            if cls:
                file_entry["classes"].append(cls)

        elif node_type in ("ExportNamedDeclaration", "ExportDefaultDeclaration"):
            if hasattr(node, "declaration") and node.declaration:
                decl = node.declaration
                if decl.type == "FunctionDeclaration":
                    func = self._process_function_ast(decl, source, file_path)
                    if func:
                        func["exported"] = True
                        file_entry["functions"].append(func)
                elif decl.type == "ClassDeclaration":
                    cls = self._process_class_ast(decl, source, file_path)
                    if cls:
                        cls["exported"] = True
                        file_entry["classes"].append(cls)

    def _process_function_ast(
        self, node: Any, source: str, file_path: str, name: Optional[str] = None, class_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Process function node from AST."""
        func_name = name or (getattr(node.id, "name", None) if hasattr(node, "id") else None) or "anonymous"

        is_async = getattr(node, "async", False)
        is_generator = getattr(node, "generator", False)
        is_arrow = node.type == "ArrowFunctionExpression"

        params_ast = self._extract_parameters_ast(node)
        signature = self._build_signature_ast(params_ast, is_arrow, is_async, is_generator)

        loc = getattr(node, "loc", None)
        lines = {"start": loc.start.line if loc else None, "end": loc.end.line if loc else None}

        range_info = getattr(node, "range", None)
        code_snippet = source[range_info[0] : range_info[1]] if range_info else source[:5000]

        context = f"javascript {'async ' if is_async else ''}{'generator ' if is_generator else ''}function {func_name}{signature}"
        docstring, details = self.generate_doc(code_snippet, node_name=func_name, context=context)

        summary = (details.get("summary") or "").strip()
        merged_params = self._merge_parameters_ast(params_ast, details.get("params") or [])

        dret = details.get("returns") or {}
        returns = {
            "type": (dret.get("type") or "").strip(),
            "description": (dret.get("desc") or dret.get("description") or "").strip(),
        }

        return {
            "name": func_name,
            "signature": signature,
            "description": summary,
            "parameters": merged_params,
            "returns": returns,
            "throws": details.get("throws") or [],
            "examples": details.get("examples") or [],
            "performance": details.get("performance") or {"time_complexity": "", "space_complexity": "", "notes": ""},
            "error_handling": details.get("error_handling") or {"strategy": "", "recovery": "", "logging": ""},
            "async": is_async,
            "generator": is_generator,
            "arrow": is_arrow,
            "lines": lines,
            "file_path": file_path,
            "language_hint": "javascript",
        }

    def _process_class_ast(self, node: Any, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        """Process class declaration from AST."""
        class_name = getattr(node.id, "name", "AnonymousClass") if hasattr(node, "id") else "AnonymousClass"

        extends = ""
        if hasattr(node, "superClass") and node.superClass:
            extends = getattr(node.superClass, "name", "")

        loc = getattr(node, "loc", None)
        lines = {"start": loc.start.line if loc else None, "end": loc.end.line if loc else None}

        methods: List[Dict[str, Any]] = []
        if hasattr(node, "body") and hasattr(node.body, "body"):
            for member in node.body.body:
                if member.type == "MethodDefinition":
                    method_name = getattr(member.key, "name", None)
                    if method_name:
                        is_constructor = member.kind == "constructor"
                        method = self._process_function_ast(member.value, source, file_path, name=method_name, class_name=class_name)
                        if method:
                            method["kind"] = member.kind
                            method["static"] = getattr(member, "static", False)
                            if is_constructor:
                                method["description"] = self._sanitize_constructor_summary(class_name, method["description"])
                                method["returns"] = {"type": "", "description": ""}
                                method["examples"] = []
                            methods.append(method)

        return {
            "name": class_name,
            "description": "",
            "extends": extends,
            "methods": methods,
            "lines": lines,
            "file_path": file_path,
            "language_hint": "javascript",
        }

    def _extract_parameters_ast(self, node: Any) -> List[Dict[str, Any]]:
        """Extract parameters from function AST node."""
        params = []
        if not hasattr(node, "params"):
            return params

        for param in node.params:
            param_info = self._process_parameter_ast(param)
            if param_info:
                params.append(param_info)

        return params

    def _process_parameter_ast(self, param: Any) -> Optional[Dict[str, Any]]:
        """Process single parameter from AST."""
        param_type = param.type

        if param_type == "Identifier":
            return {"name": param.name, "type": "", "default": None, "rest": False}

        elif param_type == "AssignmentPattern":
            name = self._get_pattern_name_ast(param.left)
            default = self._expression_to_string_ast(param.right)
            return {"name": name, "type": "", "default": default, "rest": False}

        elif param_type == "RestElement":
            name = self._get_pattern_name_ast(param.argument)
            return {"name": f"...{name}", "type": "Array", "default": None, "rest": True}

        elif param_type in ("ObjectPattern", "ArrayPattern"):
            name = self._get_pattern_name_ast(param)
            return {"name": name, "type": "Object", "default": None, "rest": False}

        return None

    def _get_pattern_name_ast(self, pattern: Any) -> str:
        """Extract name from pattern node."""
        if pattern.type == "Identifier":
            return pattern.name
        elif pattern.type == "ObjectPattern":
            return "{...}"
        elif pattern.type == "ArrayPattern":
            return "[...]"
        return "param"

    def _build_signature_ast(self, params: List[Dict[str, Any]], is_arrow: bool, is_async: bool, is_generator: bool) -> str:
        """Build function signature string."""
        parts = []
        for p in params:
            if p.get("default"):
                parts.append(f"{p['name']} = {p['default']}")
            else:
                parts.append(p["name"])

        sig = f"({', '.join(parts)})"
        if is_arrow:
            sig = f"{sig} => {{}}"
        if is_async:
            sig = f"async {sig}"
        if is_generator:
            sig = f"*{sig}"

        return sig

    def _merge_parameters_ast(self, ast_params: List[Dict[str, Any]], llm_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge AST params with LLM descriptions."""
        llm_map = {p.get("name"): p for p in llm_params if p.get("name")}

        merged = []
        for ast_p in ast_params:
            name = ast_p["name"]
            llm_p = llm_map.get(name, {})

            merged.append({
                "name": name,
                "type": (llm_p.get("type") or ast_p.get("type") or "").strip(),
                "default": llm_p.get("default", ast_p.get("default")),
                "description": (llm_p.get("desc") or llm_p.get("description") or "").strip(),
                "optional": bool(llm_p.get("optional")) or (ast_p.get("default") is not None),
                "rest": ast_p.get("rest", False),
            })

        return merged

    def _is_function_node(self, node: Any) -> bool:
        """Check if node is a function."""
        return node and node.type in ("FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression")

    def _expression_to_string_ast(self, expr: Any) -> str:
        """Convert expression AST node to string."""
        if not expr:
            return ""

        if expr.type == "Literal":
            value = getattr(expr, "value", None)
            return f'"{value}"' if isinstance(value, str) else str(value)
        elif expr.type == "Identifier":
            return expr.name
        elif expr.type in ("ObjectExpression", "ArrayExpression"):
            return "{...}" if expr.type == "ObjectExpression" else "[...]"

        return "..."

    def _extract_file_comment_ast(self, tree: Any, source: str) -> str:
        """Extract file-level comment from AST."""
        if hasattr(tree, "comments") and tree.comments:
            first_comment = tree.comments[0]
            if first_comment.type == "Block" and hasattr(first_comment, "value"):
                return first_comment.value.strip()
        return ""

    # ==================== Regex-Based Fallback Analysis ====================

    def _analyze_with_regex(self, source: str, file_path: str) -> Dict[str, Any]:
        """Fallback regex-based analysis."""
        file_entry: Dict[str, Any] = {
            "path": file_path,
            "summary": "",
            "functions": [],
            "classes": [],
        }

        # Top-level function declarations
        for m in FUNC_RE.finditer(source):
            name = m.group("name")
            args = m.group("args")
            start_line = source.count("\n", 0, m.start()) + 1
            snippet = self._extract_brace_block(source, m.end() - 1)
            end_line = start_line + snippet.count("\n")
            sym = self._build_function_symbol_regex(
                name, f"({args.strip()})", args, snippet, file_path, start_line, end_line, f"function {name}({args.strip()})"
            )
            file_entry["functions"].append(sym)

        # Arrow functions
        for m in ARROW_RE.finditer(source):
            name = m.group("name")
            args = m.group("args")
            start_line = source.count("\n", 0, m.start()) + 1
            snippet = self._extract_brace_block(source, m.end() - 1)
            end_line = start_line + snippet.count("\n")
            sym = self._build_function_symbol_regex(
                name, f"({args.strip()}) => {{}}", args, snippet, file_path, start_line, end_line, f"const {name} = ({args.strip()}) => {{}}"
            )
            file_entry["functions"].append(sym)

        # Classes
        for m in CLASS_RE.finditer(source):
            cls_name = m.group("name")
            cls_body = m.group("body")
            cls_start = source.count("\n", 0, m.start()) + 1

            methods = []
            for mm in METHOD_RE.finditer(cls_body):
                mname = mm.group("name")
                margs = mm.group("args")
                mstart = cls_start + cls_body.count("\n", 0, mm.start())
                snippet = self._extract_brace_block(cls_body, mm.end() - 1)
                mend = mstart + snippet.count("\n")
                is_constructor = mname == "constructor"
                method = self._build_function_symbol_regex(
                    mname, f"({margs.strip()})", margs, snippet, file_path, mstart, mend, f"class {cls_name} :: {mname}({margs.strip()})", is_constructor, cls_name
                )
                methods.append(method)

            file_entry["classes"].append({
                "name": cls_name,
                "description": "",
                "extends": "",
                "methods": methods,
                "lines": {"start": cls_start, "end": None},
                "file_path": file_path,
                "language_hint": "javascript",
            })

        return {"files": [file_entry]}

    def _build_function_symbol_regex(
        self, name: str, signature: str, args: str, code_snippet: str, file_path: str,
        start_line: int, end_line: int, context: str, is_constructor: bool = False, class_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Build function symbol from regex extraction."""
        docstring, details = self.generate_doc(code_snippet, node_name=name, context=context)

        if is_constructor:
            summary = self._sanitize_constructor_summary(class_name or "Class", details.get("summary") or "")
            examples = []
            returns = {"type": "", "description": ""}
        else:
            summary = (details.get("summary") or "").strip()
            examples = details.get("examples") or []
            dret = details.get("returns") or {}
            returns = {"type": (dret.get("type") or "").strip(), "description": (dret.get("desc") or dret.get("description") or "").strip()}

        params = self._merge_params_regex(args, details.get("params") or [])

        return {
            "name": name,
            "signature": signature,
            "description": summary,
            "parameters": params,
            "returns": returns,
            "throws": details.get("throws") or [],
            "examples": examples,
            "performance": details.get("performance") or {"time_complexity": "", "space_complexity": "", "notes": ""},
            "error_handling": details.get("error_handling") or {"strategy": "", "recovery": "", "logging": ""},
            "lines": {"start": start_line, "end": end_line},
            "file_path": file_path,
            "language_hint": "javascript",
        }

    def _merge_params_regex(self, arglist: str, details_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge regex-extracted params with LLM descriptions."""
        names = []
        for raw in [a.strip() for a in arglist.split(",") if a.strip()]:
            if raw.startswith("{"):
                names.append({"name": "options", "default": None})
            else:
                if "=" in raw:
                    n, d = raw.split("=", 1)
                    names.append({"name": n.strip(), "default": d.strip()})
                else:
                    names.append({"name": raw, "default": None})

        dmap = {p.get("name"): p for p in details_params if p.get("name")}
        out = []
        for p in names:
            dp = dmap.get(p["name"], {})
            out.append({
                "name": p["name"],
                "type": (dp.get("type") or "").strip(),
                "default": dp.get("default", p["default"]),
                "description": (dp.get("desc") or dp.get("description") or "").strip(),
                "optional": bool(dp.get("optional")) or (p["default"] is not None),
            })
        return out

    def _extract_brace_block(self, src: str, brace_pos: int) -> str:
        """Extract code block from opening brace to matching closing brace."""
        i = src.find("{", brace_pos)
        if i == -1:
            return src[brace_pos: brace_pos + 400]
        depth = 0
        for j in range(i, len(src)):
            if src[j] == "{":
                depth += 1
            elif src[j] == "}":
                depth -= 1
                if depth == 0:
                    return src[i:j+1]
        return src[i:]

    def _sanitize_constructor_summary(self, cls_name: str, summary: str) -> str:
        """Normalize constructor docs."""
        cleaned = summary.strip()
        if not cleaned or cls_name not in cleaned:
            return f"Constructs a {cls_name} instance."
        if "return" in cleaned.lower() or "returns" in cleaned.lower():
            return f"Constructs a {cls_name} instance."
        return cleaned
