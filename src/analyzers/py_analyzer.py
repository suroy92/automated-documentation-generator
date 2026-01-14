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
            "decorators": [self._expr_to_str(d) for d in getattr(node, "decorator_list", [])] if hasattr(node, "decorator_list") else [],
            "async": async_fn,
            "lines": lines,
            "file_path": file_path,
            "language_hint": "python",
        }
        return sym

    def _process_class(self, node: ast.ClassDef, source: str, file_path: str) -> Optional[Dict[str, Any]]:
        cls_name = node.name
        bases = [self._expr_to_str(b) for b in node.bases]
        class_doc = ast.get_docstring(node) or ""

        methods: List[Dict[str, Any]] = []
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                m = self._process_function(child, source, file_path, node)
                if m:
                    methods.append(m)

        return {
            "name": cls_name,
            "description": class_doc.strip(),
            "extends": ", ".join(bases) if bases else "",
            "methods": methods,
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
