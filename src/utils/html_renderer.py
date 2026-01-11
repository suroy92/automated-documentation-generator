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
body { 
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
  line-height: 1.6; 
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
  color: #333;
}
pre { 
  background: #0b1020; 
  color: #e0e6ff; 
  padding: 16px; 
  overflow: auto; 
  border-radius: 8px;
  border: 1px solid #1a2332;
}
code { 
  font-family: 'Fira Code', 'Cascadia Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.9em;
}
pre code {
  background: none;
  padding: 0;
}
code:not(pre code) {
  background: #f4f4f4;
  padding: 2px 6px;
  border-radius: 3px;
  color: #e83e8c;
}
h1, h2, h3, h4, h5, h6 { 
  margin-top: 1.8em;
  margin-bottom: 0.8em;
  font-weight: 600;
}
h1 { border-bottom: 2px solid #eee; padding-bottom: 0.3em; }
h2 { border-bottom: 1px solid #eee; padding-bottom: 0.3em; }
a { color: #0066cc; text-decoration: none; }
a:hover { text-decoration: underline; }
.mermaid { 
  background: #0b1020; 
  color: #e0e6ff; 
  padding: 16px; 
  border-radius: 8px;
  margin: 16px 0;
}
details {
  border: 1px solid #e1e4e8;
  border-radius: 6px;
  padding: 16px;
  margin: 16px 0;
  background: #f6f8fa;
}
details summary {
  cursor: pointer;
  font-weight: 600;
  margin: -16px;
  padding: 16px;
  background: #f6f8fa;
  border-radius: 6px;
}
details summary:hover {
  background: #eaeef2;
}
details[open] summary {
  border-bottom: 1px solid #e1e4e8;
  margin-bottom: 16px;
}
table {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
}
th, td {
  border: 1px solid #ddd;
  padding: 12px;
  text-align: left;
}
th {
  background: #f6f8fa;
  font-weight: 600;
}
tr:hover {
  background: #f6f8fa;
}
ul, ol {
  padding-left: 2em;
}
li {
  margin: 0.5em 0;
}
blockquote {
  border-left: 4px solid #0066cc;
  padding-left: 16px;
  margin: 16px 0;
  color: #666;
}
hr {
  border: none;
  border-top: 1px solid #e1e4e8;
  margin: 24px 0;
}
sub {
  color: #666;
  font-size: 0.85em;
}
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
        # First, extract and replace Mermaid blocks with placeholders
        mermaid_blocks = []
        def extract_mermaid(match):
            mermaid_blocks.append(match.group(1))
            return f"{{{{MERMAIDBLOCK{len(mermaid_blocks) - 1}}}}}"
        
        # Match ```mermaid blocks
        md_text = re.sub(
            r'```mermaid\n(.*?)\n```',
            extract_mermaid,
            md_text,
            flags=re.DOTALL,
        )
        
        # Convert markdown to HTML
        html_text = markdown.markdown(
            md_text,
            extensions=[
                "extra",  # Includes fenced_code, tables, and other common features
                "toc",
                "nl2br",
                "codehilite",
                "md_in_html",  # Process markdown inside HTML blocks
            ],
            output_format="html5",
            extension_configs={
                "codehilite": {
                    "css_class": "highlight",
                    "guess_lang": True,
                },
            },
        )

        # Restore Mermaid blocks as <div class="mermaid">
        for idx, mermaid_content in enumerate(mermaid_blocks):
            placeholder = f"{{{{MERMAIDBLOCK{idx}}}}}"
            mermaid_div = f'<div class="mermaid">{mermaid_content}</div>'
            html_text = html_text.replace(f"<p>{placeholder}</p>", mermaid_div)
            html_text = html_text.replace(placeholder, mermaid_div)
        
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
