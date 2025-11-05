# src/business_doc_generator.py
"""
Business-oriented documentation generator.

- Summarizes the aggregated LADOM into business-friendly sections:
  Executive Summary, Audience, Capabilities, User Journeys, Inputs/Outputs,
  Operations, Security/Privacy, Risks/Assumptions, Glossary, Roadmap.
- Uses the local Ollama LLM (providers/ollama_client.py) once per project.
- Writes Markdown to the provided output path.

This module is intentionally self-contained (no extra deps).
"""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Tuple

from .providers.ollama_client import LLM


def _compact_ladom(ladom: Dict[str, Any], limit_files: int = 30) -> Dict[str, Any]:
    """Produce a compact view of LADOM for the prompt (avoid huge payloads)."""
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
    """Parse JSON, or extract the first {...} block, else fallback."""
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
    # Fallback minimal skeleton
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


class BusinessDocGenerator:
    """Synthesizes business-friendly documentation and writes Markdown."""

    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def _prompt(self, compact: Dict[str, Any]) -> str:
        return f"""
You are a product/technical writer. Based ONLY on the provided PROJECT STRUCTURE,
write a concise BUSINESS-FRIENDLY summary in STRICT JSON (no prose outside JSON).
If a field is unknown, leave it empty — do not guess frameworks or vendors.

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
  "inputs": ["what the app consumes (files, paths, codebase)"],
  "outputs": ["what the app produces (markdown, html, artifacts)"],
  "operations": {{
     "how_to_run": ["command or menu sequence"],
     "config_keys": ["KEY=meaning"],
     "logs": ["where to look"],
     "troubleshooting": ["common issue -> quick fix"]
  }},
  "security": {{
     "data_flow": "where data goes",
     "pii": "does it process PII? how to avoid?",
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

        # Mild sanitation
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

    def generate_markdown(self, project_name: str, sections: Dict[str, Any], output_md_path: str) -> None:
        lines: List[str] = []
        lines.append(f"# {project_name} — Business Overview\n")
        if sections.get("executive_summary"):
            lines.append(sections["executive_summary"].strip() + "\n")

        if sections.get("audience"):
            lines.append("## Audience\n")
            for a in sections["audience"]:
                lines.append(f"- {a}")
            lines.append("")

        block_specs: List[Tuple[str, Any, Any]] = [
            ("Goals", sections.get("goals"), None),
            ("KPIs", sections.get("kpis"), None),
        ]
        for title, items, _ in block_specs:
            if items:
                lines.append(f"## {title}\n")
                for i in items:
                    lines.append(f"- {i}")
                lines.append("")

        if sections.get("capabilities"):
            lines.append("## Capabilities\n")
            for c in sections["capabilities"]:
                if c["name"] or c["desc"]:
                    lines.append(f"- **{c['name']}** — {c['desc']}")
            lines.append("")

        if sections.get("user_journeys"):
            lines.append("## User Journeys\n")
            for j in sections["user_journeys"]:
                lines.append(f"**{j.get('actor','User')}**")
                steps = j.get("steps") or []
                for idx, s in enumerate(steps, 1):
                    lines.append(f"  {idx}. {s}")
                lines.append("")
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

        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines).strip() + "\n")

    # Public: one-shot convenience
    def generate(self, ladom: Dict[str, Any], output_md_path: str) -> None:
        project_name = ladom.get("project_name") or "Project"
        sections = self.synthesize_sections(ladom)
        self.generate_markdown(project_name, sections, output_md_path)
