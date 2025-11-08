# src/business_doc_generator.py
"""
Business-oriented documentation generator (project-centric diagrams).

What it does:
- Summarizes LADOM into stakeholder-friendly sections (Executive Summary, etc.)
- Renders dynamic Mermaid diagrams for the *scanned project*:
  1) Project Structure (flowchart with subgraphs per top-level folder)
  2) Language Mix (pie)
  3) Top Classes map (optional; capped)
- Keeps a short Appendix diagram showing how *this doc tool* works.

No external services; uses the local LLM (providers/ollama_client.py) once.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List, Tuple

from .providers.ollama_client import LLM


# ------------------------- LADOM helpers -------------------------

def _compact_ladom(ladom: Dict[str, Any], limit_files: int = 30) -> Dict[str, Any]:
    """Produce a compact view of LADOM for prompting (avoid huge payloads)."""
    out = {
        "project_name": ladom.get("project_name", ""),
        "stats": {"files": 0, "functions": 0, "classes": 0},
        "files": [],
    }
    files = ladom.get("files") or []
    out["stats"]["files"] = len(files)
    fn = 0
    cl = 0
    for f in files[:limit_files]:
        item = {
            "path": f.get("path", ""),
            "summary": (f.get("summary") or "")[:300],
            "functions": [],
            "classes": [],
        }
        for func in (f.get("functions") or [])[:30]:
            item["functions"].append({
                "name": func.get("name", ""),
                "signature": func.get("signature", ""),
                "desc": (func.get("description") or "")[:200],
            })
        for cls in (f.get("classes") or [])[:20]:
            item["classes"].append({
                "name": cls.get("name", ""),
                "desc": (cls.get("description") or "")[:200],
                "method_count": len(cls.get("methods") or []),
            })
        fn += len(item["functions"])
        cl += len(item["classes"])
        out["files"].append(item)
    out["stats"]["functions"] = fn
    out["stats"]["classes"] = cl
    return out


def _lenient_json(s: str) -> Dict[str, Any]:
    """Parse JSON; if it fails, extract the first {...} block; else return a skeleton."""
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {
        "executive_summary": "",
        "audience": [],
        "goals": [],
        "kpis": [],
        "capabilities": [],
        "user_journeys": [],
        "inputs": [],
        "outputs": [],
        "operations": {"how_to_run": [], "config_keys": [], "logs": [], "troubleshooting": []},
        "security": {"data_flow": "", "pii": "", "storage": "", "llm_usage": ""},
        "risks": [],
        "assumptions": [],
        "glossary": {},
        "roadmap": [],
    }


# ------------------------- Business sections -------------------------

class BusinessDocGenerator:
    """Synthesizes business-friendly documentation and writes Markdown."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def _prompt(self, compact: Dict[str, Any]) -> str:
        return f"""
You are a product/technical writer. Based ONLY on the provided PROJECT STRUCTURE,
write a concise BUSINESS-FRIENDLY summary in STRICT JSON (no prose outside JSON).
If a field is unknown, leave it empty — do not invent frameworks or vendors.

Return JSON with this schema:
{{
  "executive_summary": "string (2–4 sentences)",
  "audience": ["role1","role2"],
  "goals": ["goal1","goal2"],
  "kpis": ["kpi1","kpi2"],
  "capabilities": [{{"name":"", "desc":""}}],
  "user_journeys": [
     {{"actor":"User/Stakeholder","steps":["Step 1","Step 2","Success criteria"]}}
  ],
  "inputs": ["what the app consumes"],
  "outputs": ["what the app produces"],
  "operations": {{
     "how_to_run": ["command or menu sequence"],
     "config_keys": ["KEY=meaning"],
     "logs": ["where to look"],
     "troubleshooting": ["common issue -> quick fix"]
  }},
  "security": {{
     "data_flow": "where data goes",
     "pii": "PII considerations",
     "storage": "cache / output locations",
     "llm_usage": "local model vs remote"
  }},
  "risks": ["risk1","risk2"],
  "assumptions": ["assumption1","assumption2"],
  "glossary": {{"term":"definition"}},
  "roadmap": ["next item","later item"]
}}

PROJECT STRUCTURE (compact LADOM):
{json.dumps(compact, ensure_ascii=False)}
""".strip()

    def synthesize_sections(self, ladom: Dict[str, Any]) -> Dict[str, Any]:
        compact = _compact_ladom(ladom)
        raw = self.llm.generate(system="", prompt=self._prompt(compact), temperature=0.2)
        data = _lenient_json(raw)

        # Normalize shapes
        if not isinstance(data.get("audience"), list):
            data["audience"] = [str(data.get("audience") or "")] if data.get("audience") else []
        for k in ("goals", "kpis", "inputs", "outputs", "risks", "assumptions", "roadmap"):
            v = data.get(k)
            data[k] = v if isinstance(v, list) else ([str(v)] if v else [])

        if not isinstance(data.get("capabilities"), list):
            data["capabilities"] = []
        else:
            data["capabilities"] = [
                {"name": str(c.get("name", "")), "desc": str(c.get("desc", ""))}
                for c in data["capabilities"] if isinstance(c, dict)
            ]

        if not isinstance(data.get("user_journeys"), list):
            data["user_journeys"] = []
        else:
            norm_j = []
            for j in data["user_journeys"]:
                if isinstance(j, dict):
                    actor = str(j.get("actor", "User"))
                    steps = j.get("steps") if isinstance(j.get("steps"), list) else []
                    norm_j.append({"actor": actor, "steps": [str(s) for s in steps]})
            data["user_journeys"] = norm_j

        ops = data.get("operations") or {}
        data["operations"] = {
            "how_to_run": [str(x) for x in (ops.get("how_to_run") or [])],
            "config_keys": [str(x) for x in (ops.get("config_keys") or [])],
            "logs": [str(x) for x in (ops.get("logs") or [])],
            "troubleshooting": [str(x) for x in (ops.get("troubleshooting") or [])],
        }

        sec = data.get("security") or {}
        data["security"] = {
            "data_flow": str(sec.get("data_flow") or ""),
            "pii": str(sec.get("pii") or ""),
            "storage": str(sec.get("storage") or ""),
            "llm_usage": str(sec.get("llm_usage") or ""),
        }

        if not isinstance(data.get("glossary"), dict):
            data["glossary"] = {}

        return data

    # ------------------------- Diagram helpers -------------------------

    def _language_of_path(self, path: str) -> str:
        p = (path or "").lower()
        if p.endswith(".py"):
            return "Python"
        if p.endswith(".js") or p.endswith(".mjs") or p.endswith(".cjs") or p.endswith(".ts"):
            return "JavaScript"
        if p.endswith(".java"):
            return "Java"
        return "Other"

    def _split_segments(self, path: str) -> List[str]:
        """Normalize to forward slashes and split; drop Windows drive if present."""
        s = (path or "").replace("\\", "/")
        segs = [seg for seg in s.split("/") if seg]
        if segs and segs[0].endswith(":"):  # e.g., 'C:'
            segs = segs[1:]
        return segs

    def _common_prefix(self, list_of_seg_lists: List[List[str]]) -> List[str]:
        if not list_of_seg_lists:
            return []
        prefix: List[str] = []
        for i in range(min(len(s) for s in list_of_seg_lists)):
            col = {s[i] for s in list_of_seg_lists}
            if len(col) == 1:
                prefix.append(next(iter(col)))
            else:
                break
        return prefix

    def _rel_segments(self, path: str, common_prefix: List[str]) -> List[str]:
        segs = self._split_segments(path)
        return segs[len(common_prefix):] if len(segs) >= len(common_prefix) else segs

    def _safe_id(self, *parts: str) -> str:
        raw = "_".join(parts)
        return re.sub(r"[^a-zA-Z0-9_]", "_", raw)

    def _short_rel_label(self, rel_segs: List[str], keep: int = 3) -> str:
        if not rel_segs:
            return "(root)"
        if len(rel_segs) <= keep:
            return "/".join(rel_segs)
        return ".../" + "/".join(rel_segs[-keep:])

    def _esc_label(self, s: str, max_len: int = 80) -> str:
        """Escape quotes/newlines for Mermaid labels and cap length."""
        s = (s or "")
        s = s.replace('"', '\\"')                          # escape double quotes
        s = re.sub(r"[\r\n\t]+", " ", s)                   # strip newlines/tabs
        s = re.sub(r"\s{2,}", " ", s).strip()
        return s[:max_len]

    # ------------------------- Project-centric Mermaid -------------------------

    def _project_structure_mermaid(
        self, ladom: Dict[str, Any], *, max_dirs: int = 8, max_files_per_dir: int = 10
    ) -> str:
        """
        Build a flowchart with subgraphs per *top-level* directory under the project root,
        and file nodes within each. Caps dirs/files to keep diagrams readable.
        """
        files = ladom.get("files") or []
        if not files:
            return "flowchart TD\n  A[No files]"

        # Compute common root prefix across all file paths
        all_segs = [self._split_segments(f.get("path", "")) for f in files]
        common_prefix = self._common_prefix(all_segs)

        # Group files by first relative segment (= top-level folder), else "(root)"
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for f in files:
            rel = self._rel_segments(f.get("path", ""), common_prefix)
            top = rel[0] if len(rel) > 1 else "(root)"
            groups.setdefault(top, []).append({"rel": rel, "raw": f})

        # Sort groups by size and cap
        ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        if len(ordered) > max_dirs:
            head = ordered[: max_dirs - 1]
            tail_count = sum(len(v) for _, v in ordered[max_dirs - 1 :])
            ordered = head + [("…other", [{"rel": ["(many)"], "raw": {"path": f"... {tail_count} files"}}])]

        lines: List[str] = ["flowchart TD"]
        proj = ladom.get("project_name") or "Project"
        root_id = self._safe_id("ROOT", proj)
        lines.append(f'  {root_id}[{self._esc_label(proj)}]')

        for top, entries in ordered:
            sg_id = self._safe_id("SG", top)
            lines.append(f"  subgraph {sg_id}[{self._esc_label(top)}]")
            # list up to max_files_per_dir
            for i, e in enumerate(entries[:max_files_per_dir], 1):
                rel_label = self._short_rel_label(e["rel"], keep=3)
                rel_label = self._esc_label(rel_label)
                nid = self._safe_id("F", top, str(i))
                lines.append(f'    {nid}["{rel_label}"]')
                lines.append(f"    {root_id} --> {nid}")
            if len(entries) > max_files_per_dir:
                more = len(entries) - max_files_per_dir
                mid = self._safe_id("MORE", top)
                lines.append(f'    {mid}["{self._esc_label("… +" + str(more) + " more")}"]')
                lines.append(f"    {root_id} --> {mid}")
            lines.append("  end")
        return "\n".join(lines)

    def _language_pie_mermaid(self, ladom: Dict[str, Any]) -> str:
        files = ladom.get("files") or []
        c = Counter(self._language_of_path(f.get("path", "")) for f in files)
        if not c:
            return "pie title Language Mix\n  \"Unknown\" : 1"
        lines = ["pie title Language Mix"]
        for lang, count in c.items():
            lines.append(f'  "{self._esc_label(lang)}" : {int(count)}')
        return "\n".join(lines)

    def _top_classes_mermaid(self, ladom: Dict[str, Any], *, limit: int = 12) -> str | None:
        """Optional class map: top classes by method count; connects class nodes to their file."""
        files = ladom.get("files") or []
        classes: List[Tuple[str, int, str]] = []  # (name, method_count, rel_label)

        all_segs = [self._split_segments(f.get("path", "")) for f in files]
        common_prefix = self._common_prefix(all_segs)

        for f in files:
            rel = self._rel_segments(f.get("path", ""), common_prefix)
            rel_label = self._short_rel_label(rel, keep=3)
            for cls in (f.get("classes") or []):
                name = cls.get("name") or ""
                mcount = len(cls.get("methods") or [])
                if name:
                    classes.append((f"{name}", mcount, rel_label))

        if not classes:
            return None

        classes.sort(key=lambda t: (-t[1], t[0]))
        classes = classes[:limit]

        lines = ["flowchart LR", "  subgraph Classes (top)"]
        for i, (name, mcount, rel_label) in enumerate(classes, 1):
            cid = self._safe_id("C", name, str(i))
            fid = self._safe_id("CF", rel_label, str(i))
            nm = self._esc_label(name)
            rl = self._esc_label(rel_label)
            lines.append(f'    {cid}["{nm} ({mcount})"]')
            lines.append(f'    {fid}["{rl}"]')
            lines.append(f"    {cid} --> {fid}")
        lines.append("  end")
        return "\n".join(lines)

    def _docgen_flow_mermaid(self) -> str:
        """Appendix: how this documentation tool works (kept concise)."""
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

    # ------------------------- Markdown rendering -------------------------

    def generate_markdown(
        self,
        project_name: str,
        sections: Dict[str, Any],
        output_md_path: str,
        ladom: Dict[str, Any],
    ) -> None:
        lines: List[str] = []
        lines.append(f"# {project_name} — Business Overview\n")
        if sections.get("executive_summary"):
            lines.append(sections["executive_summary"].strip() + "\n")

        if sections.get("audience"):
            lines.append("## Audience\n")
            for a in sections["audience"]:
                lines.append(f"- {a}")
            lines.append("")

        for title in ("Goals", "KPIs"):
            items = sections.get(title.lower(), [])
            if items:
                lines.append(f"## {title}\n")
                for i in items:
                    lines.append(f"- {i}")
                lines.append("")

        if sections.get("capabilities"):
            lines.append("## Capabilities\n")
            for c in sections["capabilities"]:
                if c.get("name") or c.get("desc"):
                    lines.append(f"- **{c.get('name','')}** — {c.get('desc','')}")
            lines.append("")

        if sections.get("user_journeys"):
            lines.append("## User Journeys\n")
            for j in sections["user_journeys"]:
                lines.append(f"**{j.get('actor','User')}**")
                for idx, s in enumerate(j.get("steps") or [], 1):
                    lines.append(f"  {idx}. {s}")
                lines.append("")
            lines.append("")

        # ----- Project-centric diagrams -----
        lines.append("## Diagrams\n")

        lines.append("**Project Structure**")
        lines.append("```mermaid")
        lines.append(self._project_structure_mermaid(ladom))
        lines.append("```")
        lines.append("")

        lines.append("**Language Mix**")
        lines.append("```mermaid")
        lines.append(self._language_pie_mermaid(ladom))
        lines.append("```")
        lines.append("")

        cls_map = self._top_classes_mermaid(ladom)
        if cls_map:
            lines.append("**Top Classes (by methods)**")
            lines.append("```mermaid")
            lines.append(cls_map)
            lines.append("```")
            lines.append("")

        if sections.get("inputs") or sections.get("outputs"):
            lines.append("## Inputs & Outputs\n")
            if sections.get("inputs"):
                lines.append("**Inputs**")
                for i in sections["inputs"]:
                    lines.append(f"- {i}")
            if sections.get("outputs"):
                lines.append("\n**Outputs**")
                for o in sections["outputs"]:
                    lines.append(f"- {o}")
            lines.append("")

        ops = sections.get("operations") or {}
        if any(ops.get(k) for k in ("how_to_run", "config_keys", "logs", "troubleshooting")):
            lines.append("## Operations\n")
            if ops.get("how_to_run"):
                lines.append("**How to Run**")
                for i in ops["how_to_run"]:
                    lines.append(f"- {i}")
            if ops.get("config_keys"):
                lines.append("\n**Config Keys**")
                for i in ops["config_keys"]:
                    lines.append(f"- {i}")
            if ops.get("logs"):
                lines.append("\n**Logs to Watch**")
                for i in ops["logs"]:
                    lines.append(f"- {i}")
            if ops.get("troubleshooting"):
                lines.append("\n**Troubleshooting**")
                for i in ops["troubleshooting"]:
                    lines.append(f"- {i}")
            lines.append("")

        sec = sections.get("security") or {}
        if any(sec.get(k) for k in ("data_flow", "pii", "storage", "llm_usage")):
            lines.append("## Security & Privacy\n")
            if sec.get("data_flow"):
                lines.append(f"- **Data Flow:** {sec['data_flow']}")
            if sec.get("pii"):
                lines.append(f"- **PII:** {sec['pii']}")
            if sec.get("storage"):
                lines.append(f"- **Storage:** {sec['storage']}")
            if sec.get("llm_usage"):
                lines.append(f"- **LLM Usage:** {sec['llm_usage']}")
            lines.append("")

        if sections.get("risks"):
            lines.append("## Risks\n")
            for r in sections["risks"]:
                lines.append(f"- {r}")
            lines.append("")

        if sections.get("assumptions"):
            lines.append("## Assumptions\n")
            for a in sections["assumptions"]:
                lines.append(f"- {a}")
            lines.append("")

        if sections.get("glossary"):
            lines.append("## Glossary\n")
            for k, v in sections["glossary"].items():
                lines.append(f"- **{k}:** {v}")
            lines.append("")

        if sections.get("roadmap"):
            lines.append("## Roadmap\n")
            for r in sections["roadmap"]:
                lines.append(f"- {r}")
            lines.append("")

        # Appendix: how this doc tool works (kept brief)
        lines.append("## Appendix — How this documentation was generated\n")
        lines.append("```mermaid")
        lines.append(self._docgen_flow_mermaid())
        lines.append("```")
        lines.append("")

        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).strip() + "\n")

    # Public API: one-shot convenience
    def generate(self, ladom: Dict[str, Any], output_md_path: str) -> None:
        project_name = ladom.get("project_name") or "Project"
        sections = self.synthesize_sections(ladom)
        self.generate_markdown(project_name, sections, output_md_path, ladom)
