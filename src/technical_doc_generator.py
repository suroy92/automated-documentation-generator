"""
Technical Markdown + HTML rendering with Mermaid support.

Features:
- Configurable limits (files, functions, classes)
- Exclusion patterns (glob with ** via pathlib; optional regex via `re:` prefix)
- Jinja2 templating with user-supplied template or defaults
- Basic schema validation of LADOM
- Optional CSS theme injection
- Markdown -> HTML conversion with Mermaid block support

Security notes:
- If `template_string` / `template_path` is user-controlled, enable `sandbox_templates=True` to reduce template injection risk.
- If LADOM/Markdown content is untrusted and you will serve the HTML, sanitize the generated HTML (e.g., via `bleach`) to reduce XSS risk.
- HTML generation may load Mermaid from a public CDN if a local asset is not present; pin and self-host for supply-chain control.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import jinja2

from .utils.path_utils import PathUtils
from .utils.html_renderer import HTMLRenderer

# -------------------------------------------------------------- #
# Configuration
# -------------------------------------------------------------- #


@dataclass
class GeneratorConfig:
    """Runtime configuration for the documentation generator."""

    # Limits
    file_limit: Optional[int] = None
    function_limit: Optional[int] = None
    class_limit: Optional[int] = None

    # Exclusion patterns:
    # - Glob patterns are matched with pathlib's PurePosixPath.match (supports **).
    # - Regex patterns can be provided as: "re:<pattern>"
    exclude_patterns: List[str] = field(
        default_factory=lambda: ["tests/**", "venv/**", "build/**"]
    )

    # Templating
    template_path: Optional[str] = None
    template_string: Optional[str] = None  # If provided, overrides template_path
    sandbox_templates: bool = False  # Safer when templates are not trusted

    # CSS theme
    css_theme_path: Optional[str] = None  # Path to a CSS file; if None use default

    # Extra metadata to inject into the template
    metadata: Dict[str, Any] = field(default_factory=dict)


# Default Jinja2 template – users can override via config
# NOTE: The template uses ~~~ fenced blocks (not ```), which are supported by Python-Markdown's fenced_code extension.
DEFAULT_TEMPLATE = r"""
# {{ project }} — Documentation
> Generated locally via {{ generator }}

## Overview
- **Files:** {{ counts.files }}
- **Functions:** {{ counts.functions }}
- **Classes:** {{ counts.classes }}

{{ metadata_overview }}

## Table of Contents
{% for file in files %}
- [{{ file.short_path }}](#{{ file.anchor }})
{% endfor %}

## File Summaries
| File | Functions | Classes |
|---|---:|---:|
{% for file in files %}
| {{ file.short_path }} | {{ file.func_count }} | {{ file.class_count }} |
{% endfor %}

{% for file in files %}
---
### {{ file.short_path }}
<a id="{{ file.anchor }}"></a>
{% if file.summary %}
{{ file.summary }}
{% endif %}

{% if file.functions %}
#### Functions
{% for fn in file.functions %}
**{{ fn.name }}** {{ fn.signature or "" }}
{% if fn.description %}
{{ fn.description }}
{% endif %}

{% if fn.parameters %}
**Parameters**
| Name | Type | Default | Description |
|---|---|---|---|
{% for p in fn.parameters %}
| {{ p.name }} | {{ p.type }} | {{ p.default }} | {{ p.description }} |
{% endfor %}
{% endif %}

{% if fn.returns %}
**Returns**
- `{{ fn.returns.type }}` — {{ fn.returns.description }}
{% endif %}

{% if fn.throws %}
**Throws**
{% for t in fn.throws %}
- {{ t }}
{% endfor %}
{% endif %}

{% if fn.examples %}
**Examples**
{% for e in fn.examples[:2] %}
~~~{{ e.language_hint or "" }}
{{ e.code.strip() }}
~~~
{% endfor %}
{% endif %}

{% if fn.source %}
*Source:* `{{ fn.source }}`
{% endif %}
{% endfor %}
{% endif %}

{% if file.classes %}
#### Classes
{% for cl in file.classes %}
**class {{ cl.name }}**
{% if cl.description %}
{{ cl.description }}
{% endif %}

{% if cl.methods %}
{% for m in cl.methods %}
**{{ m.name }}** {{ m.signature or "" }}
{% if m.description %}
{{ m.description }}
{% endif %}

{% if m.parameters %}
**Parameters**
| Name | Type | Default | Description |
|---|---|---|---|
{% for p in m.parameters %}
| {{ p.name }} | {{ p.type }} | {{ p.default }} | {{ p.description }} |
{% endfor %}
{% endif %}

{% if m.returns %}
**Returns**
- `{{ m.returns.type }}` — {{ m.returns.description }}
{% endif %}

{% if m.throws %}
**Throws**
{% for t in m.throws %}
- {{ t }}
{% endfor %}
{% endif %}

{% if m.examples %}
**Examples**
{% for e in m.examples[:2] %}
~~~{{ e.language_hint or "" }}
{{ e.code.strip() }}
~~~
{% endfor %}
{% endif %}

{% if m.source %}
*Source:* `{{ m.source }}`
{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
{% endif %}
{% endfor %}
"""


# -------------------------------------------------------------- #
# Utility types
# -------------------------------------------------------------- #


@dataclass
class _Counts:
    files: int = 0
    functions: int = 0
    classes: int = 0


# -------------------------------------------------------------- #
# Validation
# -------------------------------------------------------------- #


def _validate_ladom(ladom: Dict[str, Any]) -> None:
    """
    Basic schema validation. Raises ValueError with a clear message if the
    structure is invalid.
    """
    if not isinstance(ladom, dict):
        raise ValueError("ladom must be a dictionary.")
    if "files" not in ladom:
        raise ValueError("ladom must contain a 'files' key.")
    if not isinstance(ladom["files"], list):
        raise ValueError("'files' must be a list.")

    for idx, f in enumerate(ladom["files"]):
        if not isinstance(f, dict):
            raise ValueError(f"File at index {idx} must be a dictionary.")
        if "path" not in f:
            raise ValueError(f"File at index {idx} missing required 'path' field.")

        for kind in ("functions", "classes"):
            if kind in f and not isinstance(f[kind], list):
                raise ValueError(f"File {f['path']} - '{kind}' must be a list.")

        for kind in ("functions", "classes"):
            for item in f.get(kind, []) or []:
                if not isinstance(item, dict):
                    raise ValueError(f"Item in {kind} of {f['path']} must be a dict.")
                if "name" not in item:
                    raise ValueError(f"Item in {kind} of {f['path']} missing 'name'.")
                if "parameters" in item and not isinstance(item["parameters"], list):
                    raise ValueError(
                        f"Item {item['name']} in {kind} of {f['path']} has non-list 'parameters'."
                    )
                if "returns" in item and not isinstance(item["returns"], dict):
                    raise ValueError(
                        f"Item {item['name']} in {kind} of {f['path']} has non-dict 'returns'."
                    )
                if "throws" in item and not isinstance(item["throws"], list):
                    raise ValueError(
                        f"Item {item['name']} in {kind} of {f['path']} has non-list 'throws'."
                    )
                if "examples" in item and not isinstance(item["examples"], list):
                    raise ValueError(
                        f"Item {item['name']} in {kind} of {f['path']} has non-list 'examples'."
                    )


# -------------------------------------------------------------- #
# Markdown generation
# -------------------------------------------------------------- #


class MarkdownGenerator:
    def __init__(self, config: GeneratorConfig) -> None:
        self.config = config

        if self.config.sandbox_templates:
            # Security: reduces template injection surface, but still treat untrusted templates cautiously.
            from jinja2.sandbox import SandboxedEnvironment  # type: ignore

            env: jinja2.Environment = SandboxedEnvironment(
                undefined=jinja2.StrictUndefined, autoescape=False
            )
        else:
            env = jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=False)

        if self.config.template_string:
            self.template = env.from_string(self.config.template_string)
        elif self.config.template_path:
            tmpl_path = pathlib.Path(self.config.template_path)
            if not tmpl_path.is_file():
                raise FileNotFoundError(f"Template file not found: {tmpl_path}")
            self.template = env.from_string(tmpl_path.read_text(encoding="utf-8"))
        else:
            self.template = env.from_string(DEFAULT_TEMPLATE)

    @staticmethod
    def _normalize_path(path: str) -> str:
        return (path or "").replace("\\", "/")

    def _anchor_for_file(self, path: str) -> str:
        raw = self._normalize_path(path).lower()
        raw = re.sub(r"^[a-z]:/", "", raw)
        slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
        return f"file-{slug or 'unknown'}"

    def _short_path(self, path: str) -> str:
        path = self._normalize_path(path)
        if not path:
            return "(unknown)"
        parts = path.split("/")
        if len(parts) <= 3:
            return path
        return ".../" + "/".join(parts[-3:])

    def _excluded(self, path: str) -> bool:
        path = self._normalize_path(path)
        p = pathlib.PurePosixPath(path)

        for pat in self.config.exclude_patterns or []:
            if pat.startswith("re:"):
                try:
                    if re.search(pat[3:], path):
                        return True
                except re.error as e:
                    logging.warning("Invalid regex exclude pattern %r: %s", pat, e)
                continue

            # PurePosixPath.match supports **, but matches from start of the path.
            # To match "tests/" anywhere, users can specify "**/tests/**".
            try:
                if p.match(pat):
                    return True
            except Exception as e:
                logging.warning("Invalid glob exclude pattern %r: %s", pat, e)

        return False

    def _filter_files(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for f in files:
            path = str(f.get("path", ""))
            if self._excluded(path):
                logging.debug("Excluding file by pattern: %s", path)
                continue
            filtered.append(f)
        return filtered

    def _apply_limits(self, files: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Return a new list of file dicts with limits applied.

        Performance note: this makes shallow copies to avoid mutating the caller's LADOM structure.
        """
        flimit = self.config.file_limit
        selected = files[:flimit] if flimit is not None else list(files)

        out: List[Dict[str, Any]] = []
        for f in selected:
            f2 = dict(f)  # shallow copy
            funcs = list(f.get("functions", []) or [])
            classes = list(f.get("classes", []) or [])

            if self.config.function_limit is not None:
                funcs = funcs[: self.config.function_limit]
            if self.config.class_limit is not None:
                classes = classes[: self.config.class_limit]

            f2["functions"] = funcs
            f2["classes"] = classes
            out.append(f2)

        return out

    def _build_context(self, ladom: Dict[str, Any]) -> Dict[str, Any]:
        project = ladom.get("project_name") or "Project"
        files = ladom.get("files") or []

        files = self._filter_files(files)
        files = self._apply_limits(files)

        counts = _Counts(files=len(files))
        for f in files:
            counts.functions += len(f.get("functions", []) or [])
            counts.classes += len(f.get("classes", []) or [])

        enriched_files: List[Dict[str, Any]] = []
        for f in files:
            fpath = str(f.get("path", ""))
            file_obj = {
                "path": fpath,
                "anchor": PathUtils.anchor_for_file(fpath),
                "short_path": PathUtils.short_path(fpath),
                "summary": f.get("summary", "") or "",
                "func_count": len(f.get("functions", []) or []),
                "class_count": len(f.get("classes", []) or []),
                "functions": [
                    self._enrich_symbol(fn, default_file_path=fpath)
                    for fn in (f.get("functions", []) or [])
                ],
                "classes": [
                    self._enrich_class(cl, default_file_path=fpath)
                    for cl in (f.get("classes", []) or [])
                ],
            }
            enriched_files.append(file_obj)

        metadata_overview = (self.config.metadata or {}).get("overview", "")

        return {
            "project": project,
            "generator": "technical_doc_generator",
            "counts": counts,
            "files": enriched_files,
            "metadata_overview": metadata_overview,
            **(self.config.metadata or {}),
        }

    def _enrich_symbol(
        self, sym: Dict[str, Any], *, default_file_path: str
    ) -> Dict[str, Any]:
        """Prepare symbol dict for Jinja rendering."""
        lines = sym.get("lines") or {}
        src = None

        start = lines.get("start")
        end = lines.get("end")
        if start:
            suffix = f"#L{start}-L{end}" if end else f"#L{start}"
            src = (
                f"{PathUtils.short_path(sym.get('file_path') or default_file_path)}{suffix}"
            )

        params = list(sym.get("parameters", []) or [])
        for p in params:
            if isinstance(p, dict):
                p.setdefault("name", "")
                p.setdefault("type", "")
                p.setdefault("default", "")
                p.setdefault("description", "")

        ret = dict(sym.get("returns", {}) or {})
        ret.setdefault("type", "")
        ret.setdefault("description", "")

        examples = list(sym.get("examples", []) or [])
        for e in examples:
            if isinstance(e, dict):
                e.setdefault("code", "")
                e.setdefault("language_hint", "")

        return {
            "name": sym.get("name", "") or "",
            "signature": sym.get("signature", "") or "",
            "description": sym.get("description", "") or "",
            "parameters": params,
            "returns": ret,
            "throws": list(sym.get("throws", []) or []),
            "examples": examples,
            "source": src,
        }

    def _enrich_class(
        self, cl: Dict[str, Any], *, default_file_path: str
    ) -> Dict[str, Any]:
        """Enrich class info for the template."""
        methods = cl.get("methods", []) or []
        return {
            "name": cl.get("name", "UnnamedClass") or "UnnamedClass",
            "description": cl.get("description", "") or "",
            "methods": [
                self._enrich_symbol(m, default_file_path=default_file_path)
                for m in methods
            ],
        }

    def generate(self, ladom: Dict[str, Any], output_path: str) -> None:
        _validate_ladom(ladom)
        context = self._build_context(ladom)
        rendered = self.template.render(**context)

        out_path = pathlib.Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered.strip() + "\n", encoding="utf-8")


# -------------------------------------------------------------- #
# HTML generation
# -------------------------------------------------------------- #


class HTMLGenerator:
    """Convert Markdown to HTML and render Mermaid diagrams."""

    def __init__(self, config: GeneratorConfig) -> None:
        self.config = config

    def generate(self, ladom: Dict[str, Any], output_path: str) -> None:
        """Generate HTML from markdown file using HTMLRenderer utility."""
        base, _ = os.path.splitext(output_path)
        md_path = base + ".md"
        
        HTMLRenderer.render_markdown_file_to_html(
            md_path,
            output_path,
            title="Documentation",
            css_path=self.config.css_theme_path,
        )


# -------------------------------------------------------------- #
# Public façade
# -------------------------------------------------------------- #


def generate_docs(
    ladom: Dict[str, Any],
    output_dir: str,
    *,
    config: Optional[GeneratorConfig] = None,
) -> Tuple[str, str]:
    """
    Generate Markdown and HTML documentation for a LADOM structure.

    Returns
    -------
    Tuple[str, str]
        (md_path, html_path)
    """
    cfg = config or GeneratorConfig()

    os.makedirs(output_dir, exist_ok=True)
    md_path = os.path.join(output_dir, "documentation.md")
    html_path = os.path.join(output_dir, "documentation.html")

    md_gen = MarkdownGenerator(cfg)
    md_gen.generate(ladom, md_path)

    html_gen = HTMLGenerator(cfg)
    html_gen.generate(ladom, html_path)

    return md_path, html_path
