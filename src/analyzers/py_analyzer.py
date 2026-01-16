# src/analyzers/py_analyzer.py
"""
Python-specific analyzer for extracting documentation from Python source files.

Week 1 upgrade (patched):
- Uses BaseAnalyzer.generate_doc(...) to obtain structured details (JSON) + summary-only description
- Merges AST-derived facts (types/defaults/async/lines) with LLM details
- Emits richer LADOM with per-symbol fields and source anchors
"""

from __future__ import annotations
import ast
import logging
from typing import Any, Dict, List, Optional, Tuple

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


class PythonAnalyzer(BaseAnalyzer):
    def _get_language_name(self) -> str:
        return "python"

    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        source = self._safe_read_file(file_path)
        if source is None:
            return None

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return None

        module_doc = ast.get_docstring(tree) or ""
        file_entry: Dict[str, Any] = {
            "path": file_path,
            "summary": module_doc.strip(),
            "functions": [],
            "classes": [],
            "imports": self._extract_imports(tree),
            "constants": self._extract_constants(tree),
            "global_variables": self._extract_global_variables(tree),
        }

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_obj = self._process_function(node, source, file_path, tree)
                if func_obj:
                    file_entry["functions"].append(func_obj)
            elif isinstance(node, ast.ClassDef):
                cls_obj = self._process_class(node, source, file_path)
                if cls_obj:
                    file_entry["classes"].append(cls_obj)

        return {"files": [file_entry]}

    # ------------------------ helpers ------------------------

    def _process_function(self, node: ast.AST, source: str, file_path: str, tree: ast.AST) -> Optional[Dict[str, Any]]:
        name = getattr(node, "name", "anonymous")
        async_fn = isinstance(node, ast.AsyncFunctionDef)
        signature, params_ast = self._build_signature_and_params(node)
        returns_ann = self._annotation_to_str(getattr(node, "returns", None))
        lines = {"start": getattr(node, "lineno", None), "end": getattr(node, "end_lineno", None)}
        code_snippet = ast.get_source_segment(source, node) or ""

        # Extract decorators
        decorators = [self._expr_to_str(d) for d in getattr(node, "decorator_list", [])] if hasattr(node, "decorator_list") else []

        # Extract function calls (dependencies)
        function_calls = self._extract_function_calls(node)

        # Analyze complexity
        complexity = self._analyze_complexity(node)

        context = f"python {'async ' if async_fn else ''}function {name}{signature}"
        docstring, details = self.generate_doc(code_snippet, node_name=name, context=context)

        # Prefer summary-only for description
        summary = (details.get("summary") or "").strip()

        # Merge params: prefer LLM desc, fill missing type/default from AST
        merged_params: List[Dict[str, Any]] = []
        details_params = {p.get("name"): p for p in (details.get("params") or []) if p.get("name")}
        for p in params_ast:
            dp = details_params.get(p["name"], {})
            merged_params.append({
                "name": p["name"],
                "type": (dp.get("type") or p.get("type") or "").strip(),
                "default": dp.get("default", p.get("default")),
                "description": (dp.get("desc") or dp.get("description") or "").strip(),
                "optional": bool(dp.get("optional")) or (p.get("default") not in (None, "")),
            })

        # Returns
        dret = details.get("returns") or {}
        returns = {
            "type": (dret.get("type") or (f"Coroutine[{returns_ann}]" if async_fn and returns_ann else (returns_ann or ""))).strip(),
            "description": (dret.get("desc") or dret.get("description") or "").strip(),
        }

        sym: Dict[str, Any] = {
            "name": name,
            "signature": signature,
            "description": summary,
            "parameters": merged_params,
            "returns": returns,
            "throws": details.get("throws") or [],
            "examples": details.get("examples") or [],
            "performance": details.get("performance") or {"time_complexity": "", "space_complexity": "", "notes": ""},
            "error_handling": details.get("error_handling") or {"strategy": "", "recovery": "", "logging": ""},
            "decorators": decorators,
            "async": async_fn,
            "function_calls": function_calls,
            "complexity": complexity,
            "lines": lines,
            "file_path": file_path,
            "language_hint": "python",
        }
        return sym

    def _process_class(self, node: ast.ClassDef, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        cls_name = node.name
        bases = [self._expr_to_str(b) for b in node.bases]
        class_doc = ast.get_docstring(node) or ""

        # Extract decorators
        decorators = [self._expr_to_str(d) for d in node.decorator_list]

        # Extract class attributes and methods
        methods: List[Dict[str, Any]] = []
        class_attributes: List[Dict[str, Any]] = []

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m = self._process_function(child, source, file_path, node)
                if m:
                    # Identify special methods
                    method_name = m["name"]
                    if method_name == "__init__":
                        m["is_constructor"] = True
                    elif method_name.startswith("__") and method_name.endswith("__"):
                        m["is_magic"] = True
                    elif method_name.startswith("_") and not method_name.startswith("__"):
                        m["is_protected"] = True
                    else:
                        m["is_public"] = True

                    # Check if it's a static or class method
                    for dec in m.get("decorators", []):
                        if "staticmethod" in dec:
                            m["is_static"] = True
                        elif "classmethod" in dec:
                            m["is_classmethod"] = True
                        elif "property" in dec:
                            m["is_property"] = True

                    methods.append(m)

            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                # Class-level annotated attributes
                attr_name = child.target.id
                attr_type = self._annotation_to_str(child.annotation)
                attr_value = self._expr_to_str(child.value) if child.value else None

                class_attributes.append({
                    "name": attr_name,
                    "type": attr_type,
                    "value": attr_value,
                    "line": child.lineno,
                })

            elif isinstance(child, ast.Assign):
                # Class-level assignments
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        attr_value = self._expr_to_str(child.value)
                        attr_type = self._infer_type_from_value(child.value)

                        class_attributes.append({
                            "name": attr_name,
                            "type": attr_type,
                            "value": attr_value,
                            "line": child.lineno,
                        })

        return {
            "name": cls_name,
            "description": class_doc.strip(),
            "extends": ", ".join(bases) if bases else "",
            "decorators": decorators,
            "methods": methods,
            "attributes": class_attributes,
            "lines": {"start": node.lineno, "end": getattr(node, "end_lineno", node.lineno)},
            "file_path": file_path,
            "language_hint": "python",
        }

    # ------------------------ AST utilities ------------------------

    def _build_signature_and_params(self, node: ast.AST) -> Tuple[str, List[Dict[str, Any]]]:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return "", []

        args = node.args
        parts: List[str] = []
        params: List[Dict[str, Any]] = []

        def _default_for(i: int, defaults: List[ast.AST], total: int) -> Optional[str]:
            if not defaults:
                return None
            idx_from_end = total - i
            if idx_from_end <= len(defaults):
                return self._expr_to_str(defaults[-idx_from_end])
            return None

        pos = list(getattr(args, "posonlyargs", [])) + list(args.args)
        total_pos = len(pos)
        for i, a in enumerate(pos):
            name = a.arg
            ann = self._annotation_to_str(a.annotation)
            default = _default_for(i + 1, args.defaults, total_pos)
            parts.append(name if default is None else f"{name}={default}")
            params.append({"name": name, "type": ann, "default": default})

        if args.vararg:
            parts.append(f"*{args.vararg.arg}")
            params.append({"name": f"*{args.vararg.arg}", "type": "", "default": None})

        if args.kwonlyargs:
            if not args.vararg:
                parts.append("*")
            for i, a in enumerate(args.kwonlyargs):
                name = a.arg
                ann = self._annotation_to_str(a.annotation)
                default = self._expr_to_str(args.kw_defaults[i]) if args.kw_defaults and args.kw_defaults[i] is not None else None
                parts.append(name if default is None else f"{name}={default}")
                params.append({"name": name, "type": ann, "default": default})

        if args.kwarg:
            parts.append(f"**{args.kwarg.arg}")
            params.append({"name": f"**{args.kwarg.arg}", "type": "", "default": None})

        sig = f"({', '.join(parts)})"
        return sig, params

    def _annotation_to_str(self, ann: Optional[ast.AST]) -> str:
        if ann is None:
            return ""
        return self._expr_to_str(ann)

    def _expr_to_str(self, node: Optional[ast.AST]) -> str:
        if node is None:
            return ""
        try:
            return ast.unparse(node)  # py3.9+
        except Exception:
            from ast import Attribute, Name, Constant, Subscript
            if isinstance(node, Attribute):
                return f"{self._expr_to_str(node.value)}.{node.attr}"
            if isinstance(node, Name):
                return node.id
            if isinstance(node, Constant):
                return repr(node.value)
            if isinstance(node, Subscript):
                return f"{self._expr_to_str(node.value)}[{self._expr_to_str(node.slice)}]"
            return ""

    # ------------------------ Enhanced AST extraction methods ------------------------

    def _extract_imports(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract all import statements with detailed information."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "type": "import",
                        "module": alias.name,
                        "alias": alias.asname,
                        "from": None,
                        "line": node.lineno,
                    })

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append({
                        "type": "from_import",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname,
                        "from": module,
                        "line": node.lineno,
                        "level": node.level,  # Relative import level (0 = absolute)
                    })

        return imports

    def _extract_constants(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract module-level constants (UPPER_CASE variables)."""
        constants = []

        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        # Convention: UPPER_CASE names are constants
                        if name.isupper() and not name.startswith("_"):
                            value = self._expr_to_str(node.value)
                            constants.append({
                                "name": name,
                                "value": value,
                                "type": self._infer_type_from_value(node.value),
                                "line": node.lineno,
                            })

            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    name = node.target.id
                    if name.isupper() and not name.startswith("_"):
                        value = self._expr_to_str(node.value) if node.value else None
                        constants.append({
                            "name": name,
                            "value": value,
                            "type": self._annotation_to_str(node.annotation),
                            "line": node.lineno,
                        })

        return constants

    def _extract_global_variables(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract module-level variables (non-constants)."""
        variables = []

        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        name = target.id
                        # Skip constants, private, and dunder variables
                        if not name.isupper() and not name.startswith("_"):
                            value = self._expr_to_str(node.value)
                            variables.append({
                                "name": name,
                                "value": value,
                                "type": self._infer_type_from_value(node.value),
                                "line": node.lineno,
                            })

            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name):
                    name = node.target.id
                    if not name.isupper() and not name.startswith("_"):
                        value = self._expr_to_str(node.value) if node.value else None
                        variables.append({
                            "name": name,
                            "value": value,
                            "type": self._annotation_to_str(node.annotation),
                            "line": node.lineno,
                        })

        return variables

    def _infer_type_from_value(self, node: ast.AST) -> str:
        """Infer Python type from AST node."""
        if isinstance(node, ast.Constant):
            val = node.value
            if isinstance(val, bool):
                return "bool"
            elif isinstance(val, int):
                return "int"
            elif isinstance(val, float):
                return "float"
            elif isinstance(val, str):
                return "str"
            elif isinstance(val, bytes):
                return "bytes"
            elif val is None:
                return "None"
        elif isinstance(node, ast.List):
            return "list"
        elif isinstance(node, ast.Dict):
            return "dict"
        elif isinstance(node, ast.Set):
            return "set"
        elif isinstance(node, ast.Tuple):
            return "tuple"
        elif isinstance(node, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
            return "function"
        elif isinstance(node, ast.ListComp):
            return "list"
        elif isinstance(node, ast.DictComp):
            return "dict"
        elif isinstance(node, ast.SetComp):
            return "set"
        elif isinstance(node, ast.GeneratorExp):
            return "generator"

        return ""

    def _extract_function_calls(self, node: ast.AST) -> List[str]:
        """Extract all function calls within a node."""
        calls = []

        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                func_name = self._get_call_name(child.func)
                if func_name:
                    calls.append(func_name)

        return list(set(calls))  # Remove duplicates

    def _get_call_name(self, func_node: ast.AST) -> str:
        """Get the name of a called function."""
        if isinstance(func_node, ast.Name):
            return func_node.id
        elif isinstance(func_node, ast.Attribute):
            # For chained calls like obj.method()
            return self._expr_to_str(func_node)
        return ""

    def _analyze_complexity(self, node: ast.AST) -> Dict[str, Any]:
        """Analyze code complexity metrics."""
        complexity = {
            "cyclomatic": self._calculate_cyclomatic_complexity(node),
            "nesting_depth": self._calculate_nesting_depth(node),
            "num_branches": 0,
            "num_loops": 0,
        }

        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.IfExp)):
                complexity["num_branches"] += 1
            elif isinstance(child, (ast.For, ast.While, ast.AsyncFor)):
                complexity["num_loops"] += 1

        return complexity

    def _calculate_cyclomatic_complexity(self, node: ast.AST) -> int:
        """Calculate cyclomatic complexity (rough approximation)."""
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            # Each decision point adds 1 to complexity
            if isinstance(child, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # and/or operators add complexity
                complexity += len(child.values) - 1

        return complexity

    def _calculate_nesting_depth(self, node: ast.AST, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth."""
        max_depth = current_depth

        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                depth = self._calculate_nesting_depth(child, current_depth + 1)
                max_depth = max(max_depth, depth)
            else:
                depth = self._calculate_nesting_depth(child, current_depth)
                max_depth = max(max_depth, depth)

        return max_depth
