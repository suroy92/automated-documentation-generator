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
# {{ project }}

**Technical API Reference**

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Modules](#modules)
{% for file in files -%}
  - [{{ file.display_path }}](#{{ file.anchor }})
{% endfor %}

---

## Overview

This codebase contains **{{ counts.files }}** modules with **{{ counts.functions }}** functions and **{{ counts.classes }}** classes.

{{ metadata_overview }}

## Project Structure

```
{{ project_tree }}
```

---

## Modules

{% for file in files %}
### {{ file.display_path }}
{%- if file.summary %}

{{ file.summary }}
{%- endif %}

<details id="{{ file.anchor }}">
<summary><b>Module API</b> ({{ file.func_count }} function{% if file.func_count != 1 %}s{% endif %}{% if file.classes %}, {{ file.class_count }} class{% if file.class_count != 1 %}es{% endif %}{% endif %})</summary>

{% if file.functions -%}
#### Functions
{% for fn in file.functions %}
---

##### {{ fn.name }}

```python
{{ fn.name }}{{ fn.signature or "()" }}
```
{%- if fn.description %}

{{ fn.description }}
{%- endif %}
{%- if fn.parameters %}

**Arguments:**

{% for p in fn.parameters -%}
- `{{ p.name }}`{% if p.type %} ({{ p.type }}){% endif %}{% if p.default and p.default != "None" %} = `{{ p.default }}`{% endif %}{% if p.description %} – {{ p.description }}{% endif %}
{% endfor -%}
{%- endif %}
{%- if fn.returns and (fn.returns.type or fn.returns.description) %}

**Returns:** {% if fn.returns.type %}`{{ fn.returns.type }}`{% endif %}{% if fn.returns.description %} – {{ fn.returns.description }}{% endif %}
{%- endif %}
{%- if fn.throws %}

**Raises:**

{% for t in fn.throws -%}
- {{ t }}
{% endfor -%}
{%- endif %}
{%- if fn.examples %}

**Example:**

{% for e in fn.examples[:2] -%}
```{{ e.language_hint or "" }}
{{ e.code.strip() }}
```
{% endfor -%}
{%- endif %}
{%- if fn.source %}

<sub>Source: `{{ fn.source }}`</sub>
{%- endif %}

{% endfor -%}
{%- endif %}
{%- if file.classes %}

#### Classes
{% for cl in file.classes %}
---

##### {{ cl.name }}

```python
class {{ cl.name }}
```
{%- if cl.description %}

{{ cl.description }}
{%- endif %}
{%- if cl.methods %}

**Methods:**

{% for m in cl.methods %}
###### {{ m.name }}

```python
{{ m.name }}{{ m.signature or "()" }}
```
{%- if m.description %}

{{ m.description }}
{%- endif %}
{%- if m.parameters %}

**Arguments:**

{% for p in m.parameters -%}
- `{{ p.name }}`{% if p.type %} ({{ p.type }}){% endif %}{% if p.default and p.default != "None" %} = `{{ p.default }}`{% endif %}{% if p.description %} – {{ p.description }}{% endif %}
{% endfor -%}
{%- endif %}
{%- if m.returns and (m.returns.type or m.returns.description) %}

**Returns:** {% if m.returns.type %}`{{ m.returns.type }}`{% endif %}{% if m.returns.description %} – {{ m.returns.description }}{% endif %}
{%- endif %}
{%- if m.throws %}

**Raises:**

{% for t in m.throws -%}
- {{ t }}
{% endfor -%}
{%- endif %}
{%- if m.examples %}

**Example:**

{% for e in m.examples[:2] -%}
```{{ e.language_hint or "" }}
{{ e.code.strip() }}
```
{% endfor -%}
{%- endif %}
{%- if m.source %}

<sub>Source: `{{ m.source }}`</sub>
{%- endif %}

{% endfor -%}
{%- endif %}
{% endfor -%}
{%- endif %}

</details>

{% endfor -%}

---

*Documentation generated by {{ generator }}*
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

    def _generate_project_tree(self, files: List[Dict[str, Any]], project_name: str) -> str:
        """Generate ASCII tree representation of project structure."""
        # Build directory tree
        tree: Dict[str, Any] = {"files": [], "dirs": {}}
        
        for f in files:
            display_path = f.get("display_path", "")
            if not display_path:
                continue
            
            parts = display_path.split("/")
            if len(parts) == 1:
                # Root level file
                tree["files"].append(parts[0])
            else:
                # File in subdirectory - navigate through dirs
                current = tree["dirs"]
                for i, part in enumerate(parts[:-1]):
                    if part not in current:
                        current[part] = {"files": [], "dirs": {}}
                    if i < len(parts) - 2:
                        current = current[part]["dirs"]
                # Add file to the last directory
                current[parts[-2]]["files"].append(parts[-1])
        
        # Generate ASCII tree
        lines = [project_name + "/"]
        
        def add_tree_lines(dirs: Dict, files: List[str], prefix: str = ""):
            all_dirs = sorted(dirs.keys())
            all_files = sorted(files)
            
            # Add directories first
            for i, dir_name in enumerate(all_dirs):
                is_last = (i == len(all_dirs) - 1) and not all_files
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{dir_name}/")
                
                extension = "    " if is_last else "│   "
                dir_node = dirs[dir_name]
                add_tree_lines(dir_node.get("dirs", {}), dir_node.get("files", []), prefix + extension)
            
            # Add files
            for i, fname in enumerate(all_files):
                is_last = i == len(all_files) - 1
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{fname}")
        
        add_tree_lines(tree.get("dirs", {}), tree.get("files", []))
        return "\n".join(lines)

    def _build_context(self, ladom: Dict[str, Any]) -> Dict[str, Any]:
        project = ladom.get("project_name") or "Project"
        files = ladom.get("files") or []

        files = self._filter_files(files)
        files = self._apply_limits(files)

        counts = _Counts(files=len(files))
        for f in files:
            counts.functions += len(f.get("functions", []) or [])
            counts.classes += len(f.get("classes", []) or [])

        # Calculate common prefix for display paths
        all_segs = [PathUtils.split_segments(f.get("path", "")) for f in files]
        common_prefix = PathUtils.common_prefix(all_segs)

        enriched_files: List[Dict[str, Any]] = []
        for f in files:
            fpath = str(f.get("path", ""))
            rel_segs = PathUtils.relative_segments(fpath, common_prefix)
            display = "/".join(rel_segs) if rel_segs else PathUtils.short_path(fpath)
            file_obj = {
                "path": fpath,
                "anchor": PathUtils.anchor_for_file(fpath),
                "short_path": PathUtils.short_path(fpath),
                "display_path": display,
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

        # Generate project tree
        project_tree = self._generate_project_tree(enriched_files, project)

        metadata_overview = (self.config.metadata or {}).get("overview", "")

        return {
            "project": project,
            "generator": "technical_doc_generator",
            "counts": counts,
            "files": enriched_files,
            "project_tree": project_tree,
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
        normalized_examples = []
        for e in examples:
            if isinstance(e, dict):
                e.setdefault("code", "")
                e.setdefault("language_hint", "")
                normalized_examples.append(e)
            elif isinstance(e, str):
                # Convert string examples to dict format
                normalized_examples.append({"code": e, "language_hint": ""})
            else:
                # Skip invalid example types
                continue

        return {
            "name": sym.get("name", "") or "",
            "signature": sym.get("signature", "") or "",
            "description": sym.get("description", "") or "",
            "parameters": params,
            "returns": ret,
            "throws": list(sym.get("throws", []) or []),
            "examples": normalized_examples,
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
