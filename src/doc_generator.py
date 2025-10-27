# src/doc_generator.py

"""
Week 1: Richer Markdown
- Adds Project Overview (auto), Table of Contents, and Per-file Summary table
- Slugifies anchors (safe for Windows paths with spaces/colons)
- Avoids duplicate 'Returns' by expecting per-symbol 'description' to be summary-only
- Computes source links gracefully when end line is missing
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import os
import re
import html


@dataclass
class _Counts:
    files: int = 0
    functions: int = 0
    classes: int = 0


class MarkdownGenerator:
    def generate(self, ladom: Dict[str, Any], output_path: str) -> None:
        project = ladom.get("project_name") or "Project"
        files = ladom.get("files") or []

        counts = _Counts(files=len(files))
        for f in files:
            counts.functions += len((f.get("functions") or []))
            counts.classes += len((f.get("classes") or []))

        lines: List[str] = []
        lines.append(f"# {project} — Documentation\n")
        lines.append("> Generated locally via Ollama\n")

        # Overview
        lines.append("## Overview\n")
        lines.append(f"- **Files:** {counts.files}")
        lines.append(f"- **Functions:** {counts.functions}")
        lines.append(f"- **Classes:** {counts.classes}\n")

        # TOC
        lines.append("## Table of Contents\n")
        for f in files:
            anchor = self._anchor_for_file(f.get("path", "unknown"))
            short = self._short_path(f.get("path", "unknown"))
            lines.append(f"- [{short}](#{anchor})")
        lines.append("")

        # Per-file summary table
        lines.append("## File Summaries\n")
        lines.append("| File | Functions | Classes |")
        lines.append("|---|---:|---:|")
        for f in files:
            short = self._short_path(f.get("path", ""))
            fn = len(f.get("functions") or [])
            cl = len(f.get("classes") or [])
            lines.append(f"| {short} | {fn} | {cl} |")
        lines.append("")

        # Detailed sections
        for f in files:
            path = f.get("path", "")
            anchor = self._anchor_for_file(path)
            short = self._short_path(path)
            lines.append(f"---\n")
            lines.append(f"### {short}\n<a id=\"{anchor}\"></a>\n")
            if f.get("summary"):
                lines.append(f"{f['summary']}\n")

            # Functions
            funcs = f.get("functions") or []
            if funcs:
                lines.append("#### Functions\n")
                for fn in funcs:
                    lines.extend(self._emit_symbol(fn, kind="function"))

            # Classes
            classes = f.get("classes") or []
            if classes:
                lines.append("#### Classes\n")
                for cl in classes:
                    name = cl.get("name", "UnnamedClass")
                    lines.append(f"**class {name}**\n")
                    if cl.get("description"):
                        lines.append(f"{cl['description']}\n")
                    methods = cl.get("methods") or []
                    if methods:
                        for m in methods:
                            lines.extend(self._emit_symbol(m, kind="method"))

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).strip() + "\n")

    # --- helpers

    def _emit_symbol(self, sym: Dict[str, Any], *, kind: str) -> List[str]:
        name = sym.get("name", f"unnamed-{kind}")
        sig = sym.get("signature") or ""
        desc = sym.get("description") or ""  # summary-only expected
        params = sym.get("parameters") or []
        ret = sym.get("returns") or {}
        lines = []
        lines.append(f"**{name}**{(' ' + sig) if sig else ''}\n")
        if desc:
            lines.append(desc)

        if params:
            lines.append("\n**Parameters**")
            lines.append("| Name | Type | Default | Description |")
            lines.append("|---|---|---|---|")
            for p in params:
                lines.append(
                    f"| {p.get('name','')} | {p.get('type','')} | {p.get('default','')} | {p.get('description','')} |"
                )

        if ret.get("type") or ret.get("description"):
            lines.append("\n**Returns**")
            rtyp = ret.get("type", "")
            rdesc = ret.get("description", "")
            lines.append(f"- `{rtyp}` — {rdesc}")

        if sym.get("throws"):
            lines.append("\n**Throws**")
            for t in sym["throws"]:
                lines.append(f"- {t}")

        if sym.get("examples"):
            lines.append("\n**Examples**")
            for e in sym["examples"][:2]:
                code = (e or "").strip()
                lines.append(f"```{sym.get('language_hint','')}\n{code}\n```")

        # Source lines
        lines_info = sym.get("lines") or {}
        start = lines_info.get("start")
        end = lines_info.get("end")
        file_path = sym.get("file_path") or ""
        if start:
            suffix = f"#L{start}-L{end}" if end else f"#L{start}"
            lines.append(f"\n*Source:* `{self._short_path(file_path)}{suffix}`\n")

        return lines

    def _anchor_for_file(self, path: str) -> str:
        raw = (path or "unknown").replace("\\", "/").lower()
        # remove drive letters like d:/
        raw = re.sub(r"^[a-z]:/", "", raw)
        # slugify: keep alnum and dashes
        slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        return f"file-{slug}"

    def _short_path(self, path: str) -> str:
        if not path:
            return "(unknown)"
        parts = path.replace("\\", "/").split("/")
        if len(parts) <= 3:
            return path
        return ".../" + "/".join(parts[-3:])


class HTMLGenerator:
    """Write a minimal HTML that wraps the Markdown (no external libs)."""

    def generate(self, ladom: Dict[str, Any], output_path: str) -> None:
        md_path = os.path.join(os.path.dirname(output_path), "documentation.md")
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md = f.read()
        except Exception:
            md = "# Documentation\n\n(Unable to load Markdown.)"

        html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Documentation</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.6; padding: 24px; }}
    pre {{ background: #0b1020; color: #e0e6ff; padding: 12px; overflow: auto; border-radius: 8px; }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    h1, h2, h3, h4 {{ margin-top: 1.8em; }}
    a {{ color: #005ad6; text-decoration: none; }}
  </style>
</head>
<body>
  <pre>{html.escape(md)}</pre>
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
