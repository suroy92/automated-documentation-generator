# src/technical_doc_generator.py
"""
Technical Markdown + HTML rendering with Mermaid support.

- Technical Markdown (overview, TOC, file/class/method listings)
- HTML conversion (Python-Markdown) with Mermaid diagrams support
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import os
import re
import html
import pathlib

import markdown  # Python-Markdown for MD -> HTML


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

        lines.append("## Overview\n")
        lines.append(f"- **Files:** {counts.files}")
        lines.append(f"- **Functions:** {counts.functions}")
        lines.append(f"- **Classes:** {counts.classes}\n")

        lines.append("## Table of Contents\n")
        for f in files:
            anchor = self._anchor_for_file(f.get("path", "unknown"))
            short = self._short_path(f.get("path", "unknown"))
            lines.append(f"- [{short}](#{anchor})")
        lines.append("")

        lines.append("## File Summaries\n")
        lines.append("| File | Functions | Classes |")
        lines.append("|---|---:|---:|")
        for f in files:
            short = self._short_path(f.get("path", ""))
            fn = len(f.get("functions") or [])
            cl = len(f.get("classes") or [])
            lines.append(f"| {short} | {fn} | {cl} |")
        lines.append("")

        for f in files:
            path = f.get("path", "")
            anchor = self._anchor_for_file(path)
            short = self._short_path(path)
            lines.append(f"---\n")
            lines.append(f"### {short}\n<a id=\"{anchor}\"></a>\n")
            if f.get("summary"):
                lines.append(f"{f['summary']}\n")

            funcs = f.get("functions") or []
            if funcs:
                lines.append("#### Functions\n")
                for fn in funcs:
                    lines.extend(self._emit_symbol(fn, kind="function"))

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

    def _emit_symbol(self, sym: Dict[str, Any], *, kind: str) -> List[str]:
        name = sym.get("name", f"unnamed-{kind}")
        sig = sym.get("signature") or ""
        desc = sym.get("description") or ""
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

        li = sym.get("lines") or {}
        start = li.get("start")
        end = li.get("end")
        file_path = sym.get("file_path") or ""
        if start:
            suffix = f"#L{start}-L{end}" if end else f"#L{start}"
            lines.append(f"\n*Source:* `{self._short_path(file_path)}{suffix}`\n")

        return lines

    def _anchor_for_file(self, path: str) -> str:
        raw = (path or "unknown").replace("\\", "/").lower()
        raw = re.sub(r"^[a-z]:/", "", raw)
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
    """Convert Markdown to HTML and render Mermaid diagrams."""

    def _md_to_html(self, md_text: str) -> str:
        html_text = markdown.markdown(
            md_text,
            extensions=["fenced_code", "tables", "toc"],
            output_format="html5",
        )
        # Turn ```mermaid``` blocks into <div class="mermaid">…</div>
        html_text = re.sub(
            r'<pre><code class="language-mermaid">(.*?)</code></pre>',
            lambda m: f'<div class="mermaid">{html.unescape(m.group(1))}</div>',
            html_text,
            flags=re.DOTALL,
        )
        return html_text

    def generate(self, ladom: Dict[str, Any], output_path: str) -> None:
        base, _ = os.path.splitext(output_path)
        md_path = base + ".md"
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md = f.read()
        except Exception:
            md = "# Documentation\n\n(Unable to load Markdown.)"

        body = self._md_to_html(md)

        # Prefer local mermaid if present under ./assets/
        assets_dir = os.path.join(os.path.dirname(output_path), "assets")
        local_mermaid = os.path.join(assets_dir, "mermaid.min.js")
        if os.path.exists(local_mermaid):
            mermaid_src = "assets/mermaid.min.js"
        else:
            mermaid_src = "https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"

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
    .mermaid {{ background: #0b1020; color: #e0e6ff; padding: 8px; border-radius: 8px; }}
  </style>
  <script src="{mermaid_src}"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function () {{
      if (window.mermaid) {{
        mermaid.initialize({{ startOnLoad: true, securityLevel: 'strict' }});
      }}
    }});
  </script>
</head>
<body>
{body}
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
