"""HTML rendering utilities for documentation generation."""

from __future__ import annotations

import os
import pathlib
import re
from typing import Optional

import markdown

from .text_utils import TextUtils


class HTMLRenderer:
    """Centralized HTML generation and rendering."""

    DEFAULT_CSS = """
body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; line-height: 1.6; padding: 24px; }
pre { background: #0b1020; color: #e0e6ff; padding: 12px; overflow: auto; border-radius: 8px; }
code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
h1, h2, h3, h4 { margin-top: 1.8em; }
a { color: #005ad6; text-decoration: none; }
.mermaid { background: #0b1020; color: #e0e6ff; padding: 8px; border-radius: 8px; }
"""

    @staticmethod
    def markdown_to_html(md_text: str) -> str:
        """
        Convert Markdown text to HTML.
        
        Parameters
        ----------
        md_text : str
            Markdown text.
            
        Returns
        -------
        str
            HTML output.
        """
        html_text = markdown.markdown(
            md_text,
            extensions=["fenced_code", "tables", "toc"],
            output_format="html5",
        )

        # Convert Mermaid code fences to <div class="mermaid">
        # Match both ```mermaid and ~~~mermaid blocks
        html_text = re.sub(
            r'<pre><code class="language-mermaid">(.*?)</code></pre>',
            lambda m: f'<div class="mermaid">{TextUtils.unescape_html(m.group(1))}</div>',
            html_text,
            flags=re.DOTALL,
        )
        
        return html_text

    @staticmethod
    def load_css(css_path: Optional[str] = None) -> str:
        """
        Load CSS from file or return default CSS.
        
        Parameters
        ----------
        css_path : Optional[str], optional
            Path to CSS file, by default None.
            
        Returns
        -------
        str
            CSS content.
        """
        if css_path:
            css_file = pathlib.Path(css_path)
            if css_file.is_file():
                return css_file.read_text(encoding="utf-8")
        
        return HTMLRenderer.DEFAULT_CSS

    @staticmethod
    def get_mermaid_script_src(output_path: str) -> str:
        """
        Determine Mermaid script source (local or CDN).
        
        Parameters
        ----------
        output_path : str
            Path where HTML will be output.
            
        Returns
        -------
        str
            Script source path/URL.
        """
        assets_dir = os.path.join(os.path.dirname(output_path), "assets")
        local_mermaid = os.path.join(assets_dir, "mermaid.min.js")
        
        if os.path.exists(local_mermaid):
            return "assets/mermaid.min.js"
        return "https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"

    @staticmethod
    def build_html_document(
        body_html: str,
        *,
        title: str = "Documentation",
        css: Optional[str] = None,
        mermaid_src: Optional[str] = None,
    ) -> str:
        """
        Build a complete HTML document.
        
        Parameters
        ----------
        body_html : str
            HTML content for the body.
        title : str, optional
            Document title, by default "Documentation".
        css : Optional[str], optional
            CSS content, by default None (uses default CSS).
        mermaid_src : Optional[str], optional
            Mermaid script source, by default None (uses CDN).
            
        Returns
        -------
        str
            Complete HTML document.
        """
        css_content = css if css is not None else HTMLRenderer.DEFAULT_CSS
        mermaid_script = (
            mermaid_src
            if mermaid_src
            else "https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"
        )

        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{TextUtils.escape_html(title)}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
{css_content}
  </style>
  <script src="{mermaid_script}"></script>
  <script>
    document.addEventListener('DOMContentLoaded', function () {{
      if (window.mermaid) {{
        mermaid.initialize({{ startOnLoad: true, securityLevel: 'strict' }});
      }}
    }});
  </script>
</head>
<body>
{body_html}
</body>
</html>"""

    @staticmethod
    def render_markdown_file_to_html(
        md_path: str,
        html_path: str,
        *,
        title: str = "Documentation",
        css_path: Optional[str] = None,
    ) -> None:
        """
        Render a Markdown file to HTML and write to disk.
        
        Parameters
        ----------
        md_path : str
            Path to source Markdown file.
        html_path : str
            Path to output HTML file.
        title : str, optional
            Document title, by default "Documentation".
        css_path : Optional[str], optional
            Path to CSS file, by default None.
        """
        # Read Markdown
        try:
            md_text = pathlib.Path(md_path).read_text(encoding="utf-8")
        except Exception:
            md_text = "# Documentation\\n\\n(Unable to load Markdown.)"

        # Convert to HTML
        body_html = HTMLRenderer.markdown_to_html(md_text)

        # Load CSS and Mermaid
        css = HTMLRenderer.load_css(css_path)
        mermaid_src = HTMLRenderer.get_mermaid_script_src(html_path)

        # Build full document
        html_doc = HTMLRenderer.build_html_document(
            body_html, title=title, css=css, mermaid_src=mermaid_src
        )

        # Write to disk
        out_path = pathlib.Path(html_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html_doc, encoding="utf-8")
