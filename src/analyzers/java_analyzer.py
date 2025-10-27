# src/analyzers/java_analyzer.py
"""
Java analyzer using javalang (if available).

Week 1 upgrade (patched):
- Collects classes and methods with modifiers/throws where possible
- Uses BaseAnalyzer.generate_doc(...) with CONTEXT to produce summary-only description
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

try:
    import javalang
except Exception:  # pragma: no cover
    javalang = None


class JavaAnalyzer(BaseAnalyzer):
    def _get_language_name(self) -> str:
        return "java"

    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        source = self._safe_read_file(file_path)
        if source is None:
            return None

        if javalang is None:
            logger.warning("javalang not installed; Java analysis will be limited.")
            return {"files": [{
                "path": file_path,
                "summary": "",
                "functions": [],
                "classes": [],
            }]}

        try:
            tree = javalang.parse.parse(source)
        except Exception as e:
            logger.error(f"Failed to parse Java file {file_path}: {e}")
            return None

        file_entry: Dict[str, Any] = {
            "path": file_path,
            "summary": "",
            "functions": [],
            "classes": [],
        }

        for type_decl in getattr(tree, "types", []) or []:
            if not hasattr(type_decl, "name"):
                continue
            cls_name = type_decl.name
            methods: List[Dict[str, Any]] = []

            for m in getattr(type_decl, "methods", []) or []:
                methods.append(self._process_method(m, source, file_path, cls_name))

            for c in getattr(type_decl, "constructors", []) or []:
                methods.append(self._process_constructor(c, source, file_path, cls_name))

            file_entry["classes"].append({
                "name": cls_name,
                "description": "",
                "methods": methods,
                "lines": {"start": getattr(type_decl, "position", (None,))[0], "end": None},
                "file_path": file_path,
                "language_hint": "java",
            })

        return {"files": [file_entry]}

    # ------------------------ helpers ------------------------

    def _process_method(self, m: Any, source: str, file_path: str, cls_name: str) -> Dict[str, Any]:
        name = getattr(m, "name", "method")
        params = [{"name": p.name, "type": getattr(p.type, "name", ""), "default": None} for p in (m.parameters or [])]
        sig = "(" + ", ".join(f"{p['type']} {p['name']}" if p['type'] else p['name'] for p in params) + ")"
        start = getattr(getattr(m, "position", None), "line", None) if hasattr(m, "position") else None
        code_snippet = self._get_lines(source, start, 60) if start else (getattr(m, "name", "") or "")
        context = f"java method {cls_name}.{name}{sig}"

        doc, details = self.generate_doc(code_snippet, node_name=name, context=context)
        summary = (details.get("summary") or "").strip()

        dmap = {p.get("name"): p for p in (details.get("params") or []) if p.get("name")}
        merged_params = []
        for p in params:
            dp = dmap.get(p["name"], {})
            merged_params.append({
                "name": p["name"],
                "type": (dp.get("type") or p["type"]).strip(),
                "default": dp.get("default", p["default"]),
                "description": (dp.get("desc") or dp.get("description") or "").strip(),
                "optional": bool(dp.get("optional", False)),
            })

        dret = details.get("returns") or {}
        rtype = getattr(m.return_type, "name", "") if getattr(m, "return_type", None) else "void"
        returns = {"type": (dret.get("type") or rtype).strip(), "description": (dret.get("desc") or dret.get("description") or "").strip()}

        throws = []
        if getattr(m, "throws", None):
            throws = [getattr(t, "name", str(t)) for t in m.throws]

        sym = {
            "name": name,
            "signature": sig,
            "description": summary,
            "parameters": merged_params,
            "returns": returns,
            "throws": throws or details.get("throws") or [],
            "examples": details.get("examples") or [],
            "modifiers": list(getattr(m, "modifiers", []) or []),
            "lines": {"start": start, "end": None},
            "file_path": file_path,
            "language_hint": "java",
        }
        return sym

    def _process_constructor(self, c: Any, source: str, file_path: str, cls_name: str) -> Dict[str, Any]:
        name = getattr(c, "name", "constructor")
        params = [{"name": p.name, "type": getattr(p.type, "name", ""), "default": None} for p in (c.parameters or [])]
        sig = "(" + ", ".join(f"{p['type']} {p['name']}" if p['type'] else p['name'] for p in params) + ")"
        start = getattr(getattr(c, "position", None), "line", None) if hasattr(c, "position") else None
        code_snippet = self._get_lines(source, start, 60) if start else (getattr(c, "name", "") or "")
        context = f"java constructor {cls_name}{sig}"

        doc, details = self.generate_doc(code_snippet, node_name=f"{name} (ctor)", context=context)
        summary = (details.get("summary") or "").strip()

        dmap = {p.get("name"): p for p in (details.get("params") or []) if p.get("name")}
        merged_params = []
        for p in params:
            dp = dmap.get(p["name"], {})
            merged_params.append({
                "name": p["name"],
                "type": (dp.get("type") or p["type"]).strip(),
                "default": dp.get("default", p["default"]),
                "description": (dp.get("desc") or dp.get("description") or "").strip(),
                "optional": bool(dp.get("optional", False)),
            })

        sym = {
            "name": name,
            "signature": sig,
            "description": summary,
            "parameters": merged_params,
            "returns": {"type": "", "description": ""},
            "throws": details.get("throws") or [],
            "examples": details.get("examples") or [],
            "modifiers": list(getattr(c, "modifiers", []) or []),
            "lines": {"start": start, "end": None},
            "file_path": file_path,
            "language_hint": "java",
        }
        return sym

    def _get_lines(self, source: str, start: int, count: int) -> str:
        lines = source.splitlines()
        i = max(0, start - 1)
        return "\n".join(lines[i:i+count])
