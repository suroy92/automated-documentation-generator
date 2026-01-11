"""Mermaid diagram generation utilities."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Tuple

from .path_utils import PathUtils
from .text_utils import TextUtils


class MermaidGenerator:
    """Centralized Mermaid diagram generation."""

    @staticmethod
    def language_of_path(path: str) -> str:
        """
        Determine programming language from file extension.
        
        Parameters
        ----------
        path : str
            File path.
            
        Returns
        -------
        str
            Language name or "Other".
        """
        p = (path or "").lower()
        if p.endswith(".py"):
            return "Python"
        if p.endswith((".js", ".mjs", ".cjs", ".ts")):
            return "JavaScript"
        if p.endswith(".java"):
            return "Java"
        if p.endswith((".c", ".cpp", ".cc", ".h", ".hpp")):
            return "C/C++"
        if p.endswith((".cs",)):
            return "C#"
        if p.endswith((".go",)):
            return "Go"
        if p.endswith((".rs",)):
            return "Rust"
        if p.endswith((".rb",)):
            return "Ruby"
        if p.endswith((".php",)):
            return "PHP"
        return "Other"

    @staticmethod
    def project_structure_flowchart(
        ladom: Dict[str, Any],
        *,
        max_dirs: int = 8,
        max_files_per_dir: int = 10
    ) -> str:
        """
        Generate a Mermaid flowchart showing project structure.
        
        Creates subgraphs for top-level directories with file nodes.
        
        Parameters
        ----------
        ladom : Dict[str, Any]
            LADOM structure containing project files.
        max_dirs : int, optional
            Maximum number of directories to show, by default 8.
        max_files_per_dir : int, optional
            Maximum files per directory, by default 10.
            
        Returns
        -------
        str
            Mermaid flowchart diagram.
        """
        files = ladom.get("files") or []
        if not files:
            return "flowchart TD\n  A[No files]"

        # Compute common root prefix
        all_segs = [PathUtils.split_segments(f.get("path", "")) for f in files]
        common_prefix = PathUtils.common_prefix(all_segs)

        # Group files by top-level folder
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in files:
            rel = PathUtils.relative_segments(f.get("path", ""), common_prefix)
            top = rel[0] if len(rel) > 1 else "(root)"
            groups.setdefault(top, []).append({"rel": rel, "raw": f})

        # Sort and cap groups
        ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        if len(ordered) > max_dirs:
            head = ordered[: max_dirs - 1]
            tail_count = sum(len(v) for _, v in ordered[max_dirs - 1 :])
            ordered = head + [
                (
                    "…other",
                    [{"rel": ["(many)"], "raw": {"path": f"... {tail_count} files"}}],
                )
            ]

        # Build diagram
        lines: List[str] = ["flowchart TD"]
        proj = ladom.get("project_name") or "Project"
        root_id = PathUtils.safe_id("ROOT", proj)
        lines.append(f"  {root_id}[{TextUtils.escape_mermaid_label(proj)}]")

        for top, entries in ordered:
            sg_id = PathUtils.safe_id("SG", top)
            lines.append(f"  subgraph {sg_id}[{TextUtils.escape_mermaid_label(top)}]")
            
            # List files up to max_files_per_dir
            for i, e in enumerate(entries[:max_files_per_dir], 1):
                rel_label = PathUtils.short_relative_label(e["rel"], keep=3)
                rel_label = TextUtils.escape_mermaid_label(rel_label)
                nid = PathUtils.safe_id("F", top, str(i))
                lines.append(f'    {nid}["{rel_label}"]')
                lines.append(f"    {root_id} --> {nid}")
            
            if len(entries) > max_files_per_dir:
                more = len(entries) - max_files_per_dir
                mid = PathUtils.safe_id("MORE", top)
                lines.append(
                    f'    {mid}["{TextUtils.escape_mermaid_label("… +" + str(more) + " more")}"]'
                )
                lines.append(f"    {root_id} --> {mid}")
            
            lines.append("  end")
        
        return "\n".join(lines)

    @staticmethod
    def language_pie_chart(ladom: Dict[str, Any]) -> str:
        """
        Generate a Mermaid pie chart showing language distribution.
        
        Parameters
        ----------
        ladom : Dict[str, Any]
            LADOM structure containing project files.
            
        Returns
        -------
        str
            Mermaid pie chart diagram.
        """
        files = ladom.get("files") or []
        counter = Counter(
            MermaidGenerator.language_of_path(f.get("path", "")) for f in files
        )
        
        if not counter:
            return 'pie title Language Mix\n  "Unknown" : 1'
        
        lines = ["pie title Language Mix"]
        for lang, count in counter.items():
            lines.append(f'  "{TextUtils.escape_mermaid_label(lang)}" : {int(count)}')
        
        return "\n".join(lines)

    @staticmethod
    def top_classes_map(
        ladom: Dict[str, Any], *, limit: int = 12
    ) -> str | None:
        """
        Generate a Mermaid flowchart of top classes by method count.
        
        Parameters
        ----------
        ladom : Dict[str, Any]
            LADOM structure containing project files.
        limit : int, optional
            Maximum number of classes to show, by default 12.
            
        Returns
        -------
        str | None
            Mermaid flowchart or None if no classes found.
        """
        files = ladom.get("files") or []
        classes: List[Tuple[str, int, str]] = []  # (name, method_count, rel_label)

        all_segs = [PathUtils.split_segments(f.get("path", "")) for f in files]
        common_prefix = PathUtils.common_prefix(all_segs)

        for f in files:
            rel = PathUtils.relative_segments(f.get("path", ""), common_prefix)
            rel_label = PathUtils.short_relative_label(rel, keep=3)
            for cls in f.get("classes") or []:
                name = cls.get("name") or ""
                mcount = len(cls.get("methods") or [])
                if name:
                    classes.append((name, mcount, rel_label))

        if not classes:
            return None

        classes.sort(key=lambda t: (-t[1], t[0]))
        classes = classes[:limit]

        lines = ["flowchart LR", "  subgraph TopClasses[Top Classes by Methods]"]
        for i, (name, mcount, rel_label) in enumerate(classes, 1):
            cid = PathUtils.safe_id("C", name, str(i))
            fid = PathUtils.safe_id("CF", rel_label, str(i))
            nm = TextUtils.escape_mermaid_label(name)
            rl = TextUtils.escape_mermaid_label(rel_label)
            lines.append(f'    {cid}["{nm} ({mcount})"]')
            lines.append(f'    {fid}["{rl}"]')
            lines.append(f"    {cid} --> {fid}")
        lines.append("  end")
        
        return "\n".join(lines)

    @staticmethod
    def docgen_sequence_diagram() -> str:
        """
        Generate a Mermaid sequence diagram showing how the doc generator works.
        
        Returns
        -------
        str
            Mermaid sequence diagram.
        """
        return """sequenceDiagram
  autonumber
  participant User
  participant CLI as DocGen CLI
  participant Scan as Scanner
  participant AZ as Analyzers
  participant LLM as Local LLM (Ollama)
  participant Out as Renderers

  User->>CLI: Choose project path & doc type
  CLI->>Scan: Walk files (apply excludes)
  Scan->>AZ: Symbols per file -> LADOM
  AZ->>LLM: Summaries/normalization (local)
  LLM-->>AZ: JSON hints (no external calls)
  AZ->>Out: Technical.md/html & Business.md/html
"""

    @staticmethod
    def wrap_in_code_block(mermaid_code: str) -> str:
        """
        Wrap Mermaid code in a markdown code block.
        
        Parameters
        ----------
        mermaid_code : str
            Mermaid diagram code.
            
        Returns
        -------
        str
            Wrapped code block.
        """
        return f"```mermaid\n{mermaid_code}\n```"
