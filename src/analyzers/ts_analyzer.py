"""
TypeScript analyzer for extracting high-level symbols.

Supported constructs (initial version):
- Top-level functions:  function name(args: T): R { ... }
- Top-level arrow functions:  const name = (args: T) => { ... }
- Classes and methods:  methodName(a: T, b?: U): R { ... }
- Interfaces: method signatures collected as class-like methods

Notes:
- This analyzer is regex-based (no TypeScript compiler bindings) to keep runtime light.
- Parameter parsing strips TypeScript types/optional markers/defaults to derive names.
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)


# Top-level functions: function name(args: T): R { ... }
TS_FUNC_RE = re.compile(
    r"(^|\n)\s*function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)\s*(?::\s*[^\{\n]+)?\s*\{",
    re.MULTILINE,
)

# Top-level arrow functions: const name = (args: T) => { ... }
TS_ARROW_RE = re.compile(
    r"(^|\n)\s*const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=?\s*(?:async\s+)?\((?P<args>[^)]*)\)\s*(?::\s*[^=\n]+)?\s*=>\s*\{",
    re.MULTILINE,
)

# Classes & methods
TS_CLASS_RE = re.compile(
    r"(^|\n)\s*class\s+(?P<name>[A-Za-z_$][\w$]*)[^{]*\{(?P<body>.*?)}",
    re.DOTALL,
)

# Classic methods: methodName(a: T, b?: U): R { ... }
TS_METHOD_RE = re.compile(
    r"\n\s*(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)\s*(?::\s*[^\{\n]+)?\s*\{",
    re.MULTILINE,
)

# Interface and method signatures (no bodies)
TS_INTERFACE_RE = re.compile(
    r"(^|\n)\s*interface\s+(?P<name>[A-Za-z_$][\w$]*)[^{]*\{(?P<body>.*?)}",
    re.DOTALL,
)
TS_INTERFACE_METHOD_RE = re.compile(
    r"\n\s*(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)\s*:\s*(?P<ret>[A-Za-z_$][\w\[\]\.\|<>,\s]*)\s*;",
    re.MULTILINE,
)


class TypeScriptAnalyzer(BaseAnalyzer):
    def _get_language_name(self) -> str:
        return "typescript"

    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        source = self._safe_read_file(file_path)
        if source is None:
            return None

        file_entry: Dict[str, Any] = {
            "path": file_path,
            "summary": "",
            "functions": [],
            "classes": [],
        }

        # --- Top-level function declarations ---
        for m in TS_FUNC_RE.finditer(source):
            name = m.group("name")
            raw_args = m.group("args")
            args_clean = self._strip_types_from_args(raw_args)
            start_line = source.count("\n", 0, m.start()) + 1
            snippet = self._extract_brace_block(source, m.end() - 1)
            end_line = start_line + snippet.count("\n")
            sym = self._build_function_symbol(
                name=name,
                signature=f"({raw_args.strip()})",
                args=args_clean,
                code_snippet=snippet,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                context=f"function {name}({raw_args.strip()})",
                is_constructor=False,
                class_name=None,
            )
            file_entry["functions"].append(sym)

        # --- Top-level arrow functions ---
        for m in TS_ARROW_RE.finditer(source):
            name = m.group("name")
            raw_args = m.group("args")
            args_clean = self._strip_types_from_args(raw_args)
            start_line = source.count("\n", 0, m.start()) + 1
            snippet = self._extract_brace_block(source, m.end() - 1)
            end_line = start_line + snippet.count("\n")
            sym = self._build_function_symbol(
                name=name,
                signature=f"({raw_args.strip()}) => {{...}}",
                args=args_clean,
                code_snippet=snippet,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                context=f"const {name} = ({raw_args.strip()}) => {{...}}",
                is_constructor=False,
                class_name=None,
            )
            file_entry["functions"].append(sym)

        # --- Classes and methods ---
        classes_found: List[Dict[str, Any]] = []
        for m in TS_CLASS_RE.finditer(source):
            cls_name = m.group("name")
            body = m.group("body")
            cls_start = source.count("\n", 0, m.start()) + 1
            methods: List[Dict[str, Any]] = []

            for mm in TS_METHOD_RE.finditer(body):
                mname = mm.group("name")
                raw_args = mm.group("args")
                args_clean = self._strip_types_from_args(raw_args)
                body_prefix = body[:mm.start()]
                m_start = cls_start + body_prefix.count("\n") + 1
                method_src = self._extract_brace_block(body, mm.end() - 1)
                m_end = m_start + method_src.count("\n")
                is_ctor = (mname == "constructor")

                sym = self._build_function_symbol(
                    name=mname,
                    signature=f"({raw_args.strip()})",
                    args=args_clean,
                    code_snippet=method_src,
                    file_path=file_path,
                    start_line=m_start,
                    end_line=m_end,
                    context=f"class {cls_name} :: method {mname}({raw_args.strip()})",
                    is_constructor=is_ctor,
                    class_name=cls_name,
                )
                methods.append(sym)

            classes_found.append({
                "name": cls_name,
                "description": "",
                "methods": methods,
                "lines": {"start": cls_start, "end": None},
                "file_path": file_path,
                "language_hint": "typescript",
            })

        file_entry["classes"].extend(classes_found)

        # --- Interfaces (as class-like entries with signature-only methods) ---
        for im in TS_INTERFACE_RE.finditer(source):
            iface_name = im.group("name")
            ibody = im.group("body")
            iface_start = source.count("\n", 0, im.start()) + 1
            methods: List[Dict[str, Any]] = []

            for mm in TS_INTERFACE_METHOD_RE.finditer(ibody):
                mname = mm.group("name")
                raw_args = mm.group("args")
                args_clean = self._strip_types_from_args(raw_args)
                ret = (mm.group("ret") or "").strip()
                body_prefix = ibody[:mm.start()]
                m_start = iface_start + body_prefix.count("\n") + 1
                # No body; use signature line as snippet for context
                signature = f"({raw_args.strip()}) : {ret}".strip()
                doc, details = self.generate_doc(signature, node_name=mname, context=f"interface {iface_name} :: {mname}{signature}")

                params = self._merge_params_ts(args_clean, details.get("params") or [])
                returns = details.get("returns") or {"type": ret, "desc": ""}

                methods.append({
                    "name": mname,
                    "signature": signature,
                    "description": (details.get("summary") or "").strip(),
                    "parameters": params,
                    "returns": {
                        "type": (returns.get("type") or ret).strip(),
                        "description": (returns.get("desc") or returns.get("description") or "").strip(),
                    },
                    "throws": details.get("throws") or [],
                    "examples": details.get("examples") or [],
                    "lines": {"start": m_start, "end": None},
                    "file_path": file_path,
                    "language_hint": "typescript",
                })

            file_entry["classes"].append({
                "name": iface_name,
                "description": "",
                "methods": methods,
                "lines": {"start": iface_start, "end": None},
                "file_path": file_path,
                "language_hint": "typescript",
            })

        return {"files": [file_entry]}

    # ------------------------ helpers ------------------------

    def _strip_types_from_args(self, args: str) -> str:
        """Return a comma list of parameter names (strip TS types/defaults/optional)."""
        names: List[str] = []
        for raw in [a.strip() for a in args.split(",") if a.strip()]:
            # Remove default assignment
            if "=" in raw:
                raw = raw.split("=", 1)[0].strip()
            # Remove type annotation
            if ":" in raw:
                raw = raw.split(":", 1)[0].strip()
            # Remove optional marker
            raw = raw.replace("?", "").strip()
            # Rest parameter ( ...args )
            raw = raw.lstrip("...")
            names.append(raw)
        return ", ".join(names)

    def _merge_params_ts(self, arglist: str, details_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Align cleaned arg names with details from LLM."""
        names = [{"name": a.strip(), "default": None} for a in [x.strip() for x in arglist.split(",") if x.strip()]]
        dmap = {p.get("name"): p for p in details_params if p.get("name")}
        out: List[Dict[str, Any]] = []
        for p in names:
            dp = dmap.get(p["name"], {})
            out.append({
                "name": p["name"],
                "type": (dp.get("type") or "").strip(),
                "default": dp.get("default", p["default"]),
                "description": (dp.get("desc") or dp.get("description") or "").strip(),
                "optional": bool(dp.get("optional")) or False,
            })
        return out

    def _extract_brace_block(self, src: str, brace_pos: int) -> str:
        """Return text from the first '{' at/after brace_pos until its matching '}' (best-effort)."""
        i = src.find("{", brace_pos)
        if i == -1:
            return src[brace_pos: brace_pos + 400]
        depth = 0
        for j in range(i, len(src)):
            c = src[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return src[i:j+1]
        return src[i:]
