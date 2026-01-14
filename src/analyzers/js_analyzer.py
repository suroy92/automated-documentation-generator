# src/analyzers/js_analyzer.py
"""
JavaScript analyzer for extracting high-level symbols.

Covers:
- Top-level functions (declaration + const arrow)
- Classes
- Classic class methods:  methodName(a,b) { ... }
- Class field arrow methods:  name = (a,b) => { ... } / async
- Instance methods assigned INSIDE constructor:
    this.name = (a) => { ... }   OR   this.name = function(a) { ... }
- Prototype methods OUTSIDE class:
    ClassName.prototype.name = function(a) { ... }

Constructor handling:
- Forces empty returns
- Suppresses examples (constructors often cause vendor-biased snippets)
- Sanitizes summary to “Constructs a <ClassName> instance.” if LLM drifts
"""

from __future__ import annotations
import logging
import re
from typing import Any, Dict, List, Optional

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

# Top-level functions
FUNC_RE = re.compile(
    r"(^|\n)\s*function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)
ARROW_RE = re.compile(
    r"(^|\n)\s*const\s+(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\((?P<args>[^)]*)\)\s*=>\s*\{",
    re.MULTILINE,
)

# Classes & methods
CLASS_RE = re.compile(
    r"(^|\n)\s*class\s+(?P<name>[A-Za-z_$][\w$]*)[^{]*\{(?P<body>.*?)}",
    re.DOTALL,
)
# Classic class methods:  methodName(a,b) { ... }
METHOD_RE = re.compile(
    r"\n\s*(?P<name>[A-Za-z_$][\w$]*)\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)
# Class field arrow methods inside class body: name = (a) => { ... } / async
CLASS_FIELD_ARROW_RE = re.compile(
    r"\n\s*(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\((?P<args>[^)]*)\)\s*=>\s*\{",
    re.MULTILINE,
)

# Instance methods assigned INSIDE constructor body:
CTOR_THIS_FN_RE = re.compile(
    r"\bthis\.(?P<name>[A-Za-z_$][\w$]*)\s*=\s*function\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)
CTOR_THIS_ARROW_RE = re.compile(
    r"\bthis\.(?P<name>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s+)?\((?P<args>[^)]*)\)\s*=>\s*\{",
    re.MULTILINE,
)

# Prototype methods OUTSIDE class:
PROTOTYPE_RE = re.compile(
    r"(?P<class>[A-Za-z_$][\w$]*)\.prototype\.(?P<name>[A-Za-z_$][\w$]*)\s*=\s*function\s*\((?P<args>[^)]*)\)\s*\{",
    re.MULTILINE,
)


class JavaScriptAnalyzer(BaseAnalyzer):
    def _get_language_name(self) -> str:
        return "javascript"

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
        for m in FUNC_RE.finditer(source):
            name = m.group("name")
            args = m.group("args")
            start_line = source.count("\n", 0, m.start()) + 1
            snippet = self._extract_brace_block(source, m.end() - 1)
            end_line = start_line + snippet.count("\n")
            sym = self._build_function_symbol(
                name=name,
                signature=f"({args.strip()})",
                args=args,
                code_snippet=snippet,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                context=f"function {name}({args.strip()})",
                is_constructor=False,
                class_name=None,
            )
            file_entry["functions"].append(sym)

        # --- Top-level arrow functions (const name = (... ) => { ... }) ---
        for m in ARROW_RE.finditer(source):
            name = m.group("name")
            args = m.group("args")
            start_line = source.count("\n", 0, m.start()) + 1
            snippet = self._extract_brace_block(source, m.end() - 1)
            end_line = start_line + snippet.count("\n")
            sym = self._build_function_symbol(
                name=name,
                signature=f"({args.strip()}) => {{...}}",
                args=args,
                code_snippet=snippet,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                context=f"const {name} = ({args.strip()}) => {{...}}",
                is_constructor=False,
                class_name=None,
            )
            file_entry["functions"].append(sym)

        # --- Classes and methods (including constructor + class-field arrows) ---
        classes_found: List[Dict[str, Any]] = []
        for m in CLASS_RE.finditer(source):
            cls_name = m.group("name")
            body = m.group("body")
            cls_start = source.count("\n", 0, m.start()) + 1
            methods: List[Dict[str, Any]] = []

            # 1) classic methods: foo(a) { ... }
            for mm in METHOD_RE.finditer(body):
                mname = mm.group("name")
                margs = mm.group("args")
                body_prefix = body[:mm.start()]
                m_start = cls_start + body_prefix.count("\n") + 1
                method_src = self._extract_brace_block(body, mm.end() - 1)
                m_end = m_start + method_src.count("\n")
                is_ctor = (mname == "constructor")

                sym = self._build_function_symbol(
                    name=mname,
                    signature=f"({margs.strip()})" + ("" if not is_ctor else ""),
                    args=margs,
                    code_snippet=method_src,
                    file_path=file_path,
                    start_line=m_start,
                    end_line=m_end,
                    context=f"class {cls_name} :: method {mname}({margs.strip()})",
                    is_constructor=is_ctor,
                    class_name=cls_name,
                )
                methods.append(sym)

                # If this is the constructor, scan its body for instance methods assigned to `this.*`
                if is_ctor:
                    methods.extend(
                        self._extract_instance_methods_from_constructor(
                            ctor_body=method_src,
                            ctor_start_line=m_start,
                            cls_name=cls_name,
                            file_path=file_path,
                        )
                    )

            # 2) class field arrow methods: foo = (a) => { ... } / async
            for mm in CLASS_FIELD_ARROW_RE.finditer(body):
                mname = mm.group("name")
                margs = mm.group("args")
                body_prefix = body[:mm.start()]
                m_start = cls_start + body_prefix.count("\n") + 1
                method_src = self._extract_brace_block(body, mm.end() - 1)
                m_end = m_start + method_src.count("\n")
                methods.append(
                    self._build_function_symbol(
                        name=mname,
                        signature=f"({margs.strip()}) => {{...}}",
                        args=margs,
                        code_snippet=method_src,
                        file_path=file_path,
                        start_line=m_start,
                        end_line=m_end,
                        context=f"class {cls_name} :: field {mname} = ({margs.strip()}) => {{...}}",
                        is_constructor=False,
                        class_name=cls_name,
                    )
                )

            classes_found.append({
                "name": cls_name,
                "description": "",
                "methods": methods,
                "lines": {"start": cls_start, "end": None},
                "file_path": file_path,
                "language_hint": "javascript",
            })

        # Attach classes
        file_entry["classes"].extend(classes_found)

        # --- Prototype methods OUTSIDE class (augment corresponding class) ---
        if classes_found:
            class_names = {c["name"] for c in classes_found}
            for pm in PROTOTYPE_RE.finditer(source):
                cls = pm.group("class")
                if cls not in class_names:
                    continue
                mname = pm.group("name")
                margs = pm.group("args")
                start_line = source.count("\n", 0, pm.start()) + 1
                snippet = self._extract_brace_block(source, pm.end() - 1)
                end_line = start_line + snippet.count("\n")
                sym = self._build_function_symbol(
                    name=mname,
                    signature=f"({margs.strip()})",
                    args=margs,
                    code_snippet=snippet,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    context=f"{cls}.prototype.{mname}({margs.strip()})",
                    is_constructor=False,
                    class_name=cls,
                )
                # push onto the right class
                for c in file_entry["classes"]:
                    if c["name"] == cls:
                        c["methods"].append(sym)
                        break

        return {"files": [file_entry]}

    # ------------------------ helpers ------------------------

    def _extract_instance_methods_from_constructor(
        self, *, ctor_body: str, ctor_start_line: int, cls_name: str, file_path: str
    ) -> List[Dict[str, Any]]:
        """Find `this.name = function(...) {}` or `this.name = (...) => {}` inside constructor."""
        methods: List[Dict[str, Any]] = []

        # function(...) { ... }
        for mm in CTOR_THIS_FN_RE.finditer(ctor_body):
            name = mm.group("name")
            args = mm.group("args")
            body_prefix = ctor_body[:mm.start()]
            start_line = ctor_start_line + body_prefix.count("\n")
            snippet = self._extract_brace_block(ctor_body, mm.end() - 1)
            end_line = start_line + snippet.count("\n")
            methods.append(
                self._build_function_symbol(
                    name=name,
                    signature=f"({args.strip()})",
                    args=args,
                    code_snippet=snippet,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    context=f"class {cls_name} :: this.{name} = function({args.strip()}) {{...}}",
                    is_constructor=False,
                    class_name=cls_name,
                )
            )

        # (..) => { ... }
        for mm in CTOR_THIS_ARROW_RE.finditer(ctor_body):
            name = mm.group("name")
            args = mm.group("args")
            body_prefix = ctor_body[:mm.start()]
            start_line = ctor_start_line + body_prefix.count("\n")
            snippet = self._extract_brace_block(ctor_body, mm.end() - 1)
            end_line = start_line + snippet.count("\n")
            methods.append(
                self._build_function_symbol(
                    name=name,
                    signature=f"({args.strip()}) => {{...}}",
                    args=args,
                    code_snippet=snippet,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    context=f"class {cls_name} :: this.{name} = ({args.strip()}) => {{...}}",
                    is_constructor=False,
                    class_name=cls_name,
                )
            )

        return methods

    def _build_function_symbol(
        self,
        *,
        name: str,
        signature: str,
        args: str,
        code_snippet: str,
        file_path: str,
        start_line: int,
        end_line: Optional[int],
        context: str,
        is_constructor: bool,
        class_name: Optional[str],
    ) -> Dict[str, Any]:
        # Call LLM once with explicit context
        doc, details = self.generate_doc(code_snippet, node_name=name, context=context)

        # Prefer summary-only; sanitize constructor phrasing and strip examples
        if is_constructor:
            summary = self._sanitize_constructor_summary(class_name or "Class", (details.get("summary") or "").strip())
            examples: List[str] = []  # suppress constructor examples entirely
            returns = {"type": "", "description": ""}  # constructors don't return API values
        else:
            summary = (details.get("summary") or "").strip()
            examples = details.get("examples") or []
            dret = details.get("returns") or {}
            returns = {
                "type": (dret.get("type") or "").strip(),
                "description": (dret.get("desc") or dret.get("description") or "").strip(),
            }

        params = self._merge_params(args, details.get("params") or [])

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

    def _sanitize_constructor_summary(self, cls_name: str, summary: str) -> str:
        """Normalize constructor docs to avoid vendor-biased phrasing/returns."""
        cleaned = summary.strip()
        if not cleaned or cls_name not in cleaned:
            return f"Constructs a {cls_name} instance."
        if "return" in cleaned.lower() or "returns" in cleaned.lower():
            return f"Constructs a {cls_name} instance."
        return cleaned

    def _merge_params(self, arglist: str, details_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Split comma args and align with details by name if possible."""
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
        out: List[Dict[str, Any]] = []
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
