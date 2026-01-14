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
from typing import Any, Dict, List

from .providers.ollama_client import LLM
from .utils.text_utils import TextUtils
from .utils.mermaid_generator import MermaidGenerator
from .utils.markdown_builder import MarkdownBuilder

# ------------------------- LADOM helpers -------------------------


def _compact_ladom(
    ladom: Dict[str, Any], limit_files: int | None = 30
) -> Dict[str, Any]:
    """
    Produce a compact view of LADOM for prompting (avoid huge payloads).

    Parameters
    ----------
    ladom : dict
        The full LADOM payload.
    limit_files : int | None, optional
        Maximum number of files to keep in the compact view.
        If ``None`` (the default), returns up to 30 files.

    Returns
    -------
    dict
        A lightweight representation suitable for LLM prompting.
    """
    out = {
        "project_name": ladom.get("project_name", ""),
        "stats": {"files": 0, "functions": 0, "classes": 0},
        "files": [],
    }
    files = ladom.get("files") or []
    if limit_files is None:
        limit_files = 30
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
            item["functions"].append(
                {
                    "name": func.get("name", ""),
                    "signature": func.get("signature", ""),
                    "desc": (func.get("description") or "")[:200],
                }
            )
        for cls in (f.get("classes") or [])[:20]:
            item["classes"].append(
                {
                    "name": cls.get("name", ""),
                    "desc": (cls.get("description") or "")[:200],
                    "method_count": len(cls.get("methods") or []),
                }
            )
        fn += len(item["functions"])
        cl += len(item["classes"])
        out["files"].append(item)
    out["stats"]["functions"] = fn
    out["stats"]["classes"] = cl
    return out


def _lenient_json(s: str) -> Dict[str, Any]:
    """Parse JSON; if it fails, extract the first {...} block; else return a skeleton."""
    default_schema = {
        "executive_summary": "",
        "audience": [],
        "goals": [],
        "kpis": [],
        "capabilities": [],
        "user_journeys": [],
        "inputs": [],
        "outputs": [],
        "dependencies": {
            "external_services": [],
            "third_party_apis": [],
            "databases": [],
            "message_queues": [],
            "file_systems": [],
        },
        "operations": {
            "how_to_run": [],
            "config_keys": [],
            "logs": [],
            "troubleshooting": [],
            "deployment": {
                "environments": [],
                "strategy": "",
                "prerequisites": [],
            },
            "monitoring": {
                "metrics": [],
                "alerts": [],
                "dashboards": [],
            },
            "performance": {
                "benchmarks": [],
                "slas": [],
                "bottlenecks": [],
            },
            "disaster_recovery": {
                "backup_strategy": "",
                "restore_procedure": [],
                "rpo_rto": "",
            },
        },
        "security": {"data_flow": "", "pii": "", "storage": "", "llm_usage": ""},
        "risks": [],
        "assumptions": [],
        "glossary": {},
        "roadmap": [],
    }
    return TextUtils.lenient_json_parse(s, default_schema)


# ------------------------- Business sections -------------------------


class BusinessDocGenerator:
    """Synthesizes business-friendly documentation and writes Markdown."""

    def __init__(self, llm: LLM, *, max_files: int | None = 30) -> None:
        """
        Initialize the generator.

        Parameters
        ----------
        llm : Any
            The language model interface used to generate text.
        max_files : int | None, optional
            Maximum number of source files to include when building the compact LADOM view.
            If ``None``, all files are included.
            Defaults to 30 if not specified.
        """
        self.llm = llm
        self.max_files = max_files

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
     {{"actor":"User/Stakeholder","steps":["Step 1","Step 2","Success criteria"],"prerequisites":[],"duration":""}}
  ],
  "inputs": ["what the app consumes"],
  "outputs": ["what the app produces"],
  "dependencies": {{
     "external_services": ["service name: purpose"],
     "third_party_apis": ["API name: usage"],
     "databases": ["DB type: purpose"],
     "message_queues": ["queue type: purpose"],
     "file_systems": ["storage type: purpose"]
  }},
  "operations": {{
     "how_to_run": ["command or menu sequence"],
     "config_keys": ["KEY=meaning"],
     "logs": ["where to look"],
     "troubleshooting": ["common issue -> quick fix"],
     "deployment": {{
       "environments": ["env1: description"],
       "strategy": "blue-green/rolling/canary/etc",
       "prerequisites": ["requirement1"]
     }},
     "monitoring": {{
       "metrics": ["metric: threshold"],
       "alerts": ["condition: action"],
       "dashboards": ["dashboard name: purpose"]
     }},
     "performance": {{
       "benchmarks": ["operation: metric"],
       "slas": ["SLA description"],
       "bottlenecks": ["identified bottleneck"]
     }},
     "disaster_recovery": {{
       "backup_strategy": "description",
       "restore_procedure": ["step1"],
       "rpo_rto": "RPO: X hours, RTO: Y hours"
     }}
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
        """
        Synthesize business-friendly sections from the provided LADOM.

        Parameters
        ----------
        ladom : dict
            The full LADOM payload.

        Returns
        -------
        dict
            A dictionary containing synthesized sections.
        """
        compact = _compact_ladom(ladom, limit_files=self.max_files)
        raw = self.llm.generate(
            system="", prompt=self._prompt(compact), temperature=0.2
        )
        data = _lenient_json(raw)

        # Normalize shapes
        if not isinstance(data.get("audience"), list):
            data["audience"] = (
                [str(data.get("audience") or "")] if data.get("audience") else []
            )
        for k in (
            "goals",
            "kpis",
            "inputs",
            "outputs",
            "risks",
            "assumptions",
            "roadmap",
        ):
            v = data.get(k)
            data[k] = v if isinstance(v, list) else ([str(v)] if v else [])

        if not isinstance(data.get("capabilities"), list):
            data["capabilities"] = []
        else:
            data["capabilities"] = [
                {"name": str(c.get("name", "")), "desc": str(c.get("desc", ""))}
                for c in data["capabilities"]
                if isinstance(c, dict)
            ]

        if not isinstance(data.get("user_journeys"), list):
            data["user_journeys"] = []
        else:
            norm_j = []
            for j in data["user_journeys"]:
                if isinstance(j, dict):
                    actor = str(j.get("actor", "User"))
                    steps = j.get("steps") if isinstance(j.get("steps"), list) else []
                    prereqs = j.get("prerequisites") if isinstance(j.get("prerequisites"), list) else []
                    duration = str(j.get("duration", ""))
                    norm_j.append({
                        "actor": actor,
                        "steps": [str(s) for s in steps],
                        "prerequisites": [str(p) for p in prereqs],
                        "duration": duration
                    })
            data["user_journeys"] = norm_j

        # Normalize dependencies
        deps = data.get("dependencies") or {}
        data["dependencies"] = {
            "external_services": [str(x) for x in (deps.get("external_services") or [])],
            "third_party_apis": [str(x) for x in (deps.get("third_party_apis") or [])],
            "databases": [str(x) for x in (deps.get("databases") or [])],
            "message_queues": [str(x) for x in (deps.get("message_queues") or [])],
            "file_systems": [str(x) for x in (deps.get("file_systems") or [])],
        }

        ops = data.get("operations") or {}
        deployment = ops.get("deployment") or {}
        monitoring = ops.get("monitoring") or {}
        performance = ops.get("performance") or {}
        dr = ops.get("disaster_recovery") or {}
        
        data["operations"] = {
            "how_to_run": [str(x) for x in (ops.get("how_to_run") or [])],
            "config_keys": [str(x) for x in (ops.get("config_keys") or [])],
            "logs": [str(x) for x in (ops.get("logs") or [])],
            "troubleshooting": [str(x) for x in (ops.get("troubleshooting") or [])],
            "deployment": {
                "environments": [str(x) for x in (deployment.get("environments") or [])],
                "strategy": str(deployment.get("strategy") or ""),
                "prerequisites": [str(x) for x in (deployment.get("prerequisites") or [])],
            },
            "monitoring": {
                "metrics": [str(x) for x in (monitoring.get("metrics") or [])],
                "alerts": [str(x) for x in (monitoring.get("alerts") or [])],
                "dashboards": [str(x) for x in (monitoring.get("dashboards") or [])],
            },
            "performance": {
                "benchmarks": [str(x) for x in (performance.get("benchmarks") or [])],
                "slas": [str(x) for x in (performance.get("slas") or [])],
                "bottlenecks": [str(x) for x in (performance.get("bottlenecks") or [])],
            },
            "disaster_recovery": {
                "backup_strategy": str(dr.get("backup_strategy") or ""),
                "restore_procedure": [str(x) for x in (dr.get("restore_procedure") or [])],
                "rpo_rto": str(dr.get("rpo_rto") or ""),
            },
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

    # ------------------------- Markdown rendering -------------------------

    def generate_markdown(
        self,
        project_name: str,
        sections: Dict[str, Any],
        output_md_path: str,
        ladom: Dict[str, Any],
    ) -> None:
        builder = MarkdownBuilder()
        
        builder.add_heading(f"{project_name} — Business Overview", level=1)
        builder.add_blank_line()
        
        if sections.get("executive_summary"):
            builder.add_paragraph(sections["executive_summary"].strip())

        if sections.get("audience"):
            builder.add_heading("Audience", level=2)
            builder.add_blank_line()
            for a in sections["audience"]:
                builder.add_list_item(a)
            builder.add_blank_line()

        for title in ("Goals", "KPIs"):
            items = sections.get(title.lower(), [])
            if items:
                builder.add_heading(title, level=2)
                builder.add_blank_line()
                for i in items:
                    builder.add_list_item(i)
                builder.add_blank_line()

        if sections.get("capabilities"):
            builder.add_heading("Capabilities", level=2)
            builder.add_blank_line()
            for c in sections["capabilities"]:
                if c.get("name") or c.get("desc"):
                    builder.add_list_item(f"**{c.get('name', '')}** — {c.get('desc', '')}")
            builder.add_blank_line()

        if sections.get("user_journeys"):
            builder.add_heading("User Journeys", level=2)
            builder.add_blank_line()
            for j in sections["user_journeys"]:
                builder.add_line(f"**{j.get('actor', 'User')}**")
                if j.get("duration"):
                    builder.add_line(f"*Estimated Duration: {j['duration']}*")
                    builder.add_blank_line()
                if j.get("prerequisites"):
                    builder.add_line("*Prerequisites:*")
                    for p in j["prerequisites"]:
                        builder.add_list_item(p)
                    builder.add_blank_line()
                builder.add_line("*Steps:*")
                for idx, s in enumerate(j.get("steps") or [], 1):
                    builder.add_line(f"  {idx}. {s}")
                builder.add_blank_line()
            builder.add_blank_line()

        # ----- Project-centric diagrams -----
        builder.add_heading("Diagrams", level=2)
        builder.add_blank_line()

        builder.add_line("**Project Structure**")
        builder.add_code_block(MermaidGenerator.project_structure_flowchart(ladom), "mermaid")
        builder.add_blank_line()

        builder.add_line("**Language Mix**")
        builder.add_code_block(MermaidGenerator.language_pie_chart(ladom), "mermaid")
        builder.add_blank_line()

        cls_map = MermaidGenerator.top_classes_map(ladom)
        if cls_map:
            builder.add_line("**Top Classes (by methods)**")
            builder.add_code_block(cls_map, "mermaid")
            builder.add_blank_line()

        # Dependencies & Integrations
        deps = sections.get("dependencies") or {}
        if any(deps.get(k) for k in ("external_services", "third_party_apis", "databases", "message_queues", "file_systems")):
            builder.add_heading("Dependencies & Integrations", level=2)
            builder.add_blank_line()
            if deps.get("external_services"):
                builder.add_line("**External Services**")
                for item in deps["external_services"]:
                    builder.add_list_item(item)
                builder.add_blank_line()
            if deps.get("third_party_apis"):
                builder.add_line("**Third-Party APIs**")
                for item in deps["third_party_apis"]:
                    builder.add_list_item(item)
                builder.add_blank_line()
            if deps.get("databases"):
                builder.add_line("**Databases**")
                for item in deps["databases"]:
                    builder.add_list_item(item)
                builder.add_blank_line()
            if deps.get("message_queues"):
                builder.add_line("**Message Queues**")
                for item in deps["message_queues"]:
                    builder.add_list_item(item)
                builder.add_blank_line()
            if deps.get("file_systems"):
                builder.add_line("**File Systems & Storage**")
                for item in deps["file_systems"]:
                    builder.add_list_item(item)
                builder.add_blank_line()

        if sections.get("inputs") or sections.get("outputs"):
            builder.add_heading("Inputs & Outputs", level=2)
            builder.add_blank_line()
            if sections.get("inputs"):
                builder.add_line("**Inputs**")
                for i in sections["inputs"]:
                    builder.add_list_item(i)
            if sections.get("outputs"):
                builder.add_line("")
                builder.add_line("**Outputs**")
                for o in sections["outputs"]:
                    builder.add_list_item(o)
            builder.add_blank_line()

        ops = sections.get("operations") or {}
        if any(
            ops.get(k) for k in ("how_to_run", "config_keys", "logs", "troubleshooting")
        ) or ops.get("deployment") or ops.get("monitoring") or ops.get("performance") or ops.get("disaster_recovery"):
            builder.add_heading("Operations", level=2)
            builder.add_blank_line()
            
            if ops.get("how_to_run"):
                builder.add_heading("How to Run", level=3)
                for i in ops["how_to_run"]:
                    builder.add_list_item(i)
                builder.add_blank_line()
            
            if ops.get("config_keys"):
                builder.add_heading("Configuration", level=3)
                for i in ops["config_keys"]:
                    builder.add_list_item(i)
                builder.add_blank_line()
            
            # Deployment section
            deployment = ops.get("deployment") or {}
            if deployment.get("environments") or deployment.get("strategy") or deployment.get("prerequisites"):
                builder.add_heading("Deployment", level=3)
                if deployment.get("strategy"):
                    builder.add_line(f"**Strategy:** {deployment['strategy']}")
                    builder.add_blank_line()
                if deployment.get("environments"):
                    builder.add_line("**Environments:**")
                    for env in deployment["environments"]:
                        builder.add_list_item(env)
                    builder.add_blank_line()
                if deployment.get("prerequisites"):
                    builder.add_line("**Prerequisites:**")
                    for prereq in deployment["prerequisites"]:
                        builder.add_list_item(prereq)
                    builder.add_blank_line()
            
            # Monitoring section
            monitoring = ops.get("monitoring") or {}
            if monitoring.get("metrics") or monitoring.get("alerts") or monitoring.get("dashboards"):
                builder.add_heading("Monitoring", level=3)
                if monitoring.get("metrics"):
                    builder.add_line("**Key Metrics:**")
                    for metric in monitoring["metrics"]:
                        builder.add_list_item(metric)
                    builder.add_blank_line()
                if monitoring.get("alerts"):
                    builder.add_line("**Alerts:**")
                    for alert in monitoring["alerts"]:
                        builder.add_list_item(alert)
                    builder.add_blank_line()
                if monitoring.get("dashboards"):
                    builder.add_line("**Dashboards:**")
                    for dashboard in monitoring["dashboards"]:
                        builder.add_list_item(dashboard)
                    builder.add_blank_line()
            
            # Performance section
            performance = ops.get("performance") or {}
            if performance.get("benchmarks") or performance.get("slas") or performance.get("bottlenecks"):
                builder.add_heading("Performance", level=3)
                if performance.get("benchmarks"):
                    builder.add_line("**Benchmarks:**")
                    for bench in performance["benchmarks"]:
                        builder.add_list_item(bench)
                    builder.add_blank_line()
                if performance.get("slas"):
                    builder.add_line("**SLAs:**")
                    for sla in performance["slas"]:
                        builder.add_list_item(sla)
                    builder.add_blank_line()
                if performance.get("bottlenecks"):
                    builder.add_line("**Known Bottlenecks:**")
                    for bottleneck in performance["bottlenecks"]:
                        builder.add_list_item(bottleneck)
                    builder.add_blank_line()
            
            # Disaster Recovery section
            dr = ops.get("disaster_recovery") or {}
            if dr.get("backup_strategy") or dr.get("restore_procedure") or dr.get("rpo_rto"):
                builder.add_heading("Disaster Recovery", level=3)
                if dr.get("backup_strategy"):
                    builder.add_line(f"**Backup Strategy:** {dr['backup_strategy']}")
                    builder.add_blank_line()
                if dr.get("rpo_rto"):
                    builder.add_line(f"**Recovery Objectives:** {dr['rpo_rto']}")
                    builder.add_blank_line()
                if dr.get("restore_procedure"):
                    builder.add_line("**Restore Procedure:**")
                    for step in dr["restore_procedure"]:
                        builder.add_list_item(step)
                    builder.add_blank_line()
            
            if ops.get("logs"):
                builder.add_heading("Logging", level=3)
                for i in ops["logs"]:
                    builder.add_list_item(i)
                builder.add_blank_line()
            
            if ops.get("troubleshooting"):
                builder.add_heading("Troubleshooting", level=3)
                for i in ops["troubleshooting"]:
                    builder.add_list_item(i)
                builder.add_blank_line()

        sec = sections.get("security") or {}
        if any(sec.get(k) for k in ("data_flow", "pii", "storage", "llm_usage")):
            builder.add_heading("Security & Privacy", level=2)
            builder.add_blank_line()
            if sec.get("data_flow"):
                builder.add_list_item(f"**Data Flow:** {sec['data_flow']}")
            if sec.get("pii"):
                builder.add_list_item(f"**PII:** {sec['pii']}")
            if sec.get("storage"):
                builder.add_list_item(f"**Storage:** {sec['storage']}")
            if sec.get("llm_usage"):
                builder.add_list_item(f"**LLM Usage:** {sec['llm_usage']}")
            builder.add_blank_line()

        if sections.get("risks"):
            builder.add_heading("Risks", level=2)
            builder.add_blank_line()
            for r in sections["risks"]:
                builder.add_list_item(r)
            builder.add_blank_line()

        if sections.get("assumptions"):
            builder.add_heading("Assumptions", level=2)
            builder.add_blank_line()
            for a in sections["assumptions"]:
                builder.add_list_item(a)
            builder.add_blank_line()

        if sections.get("glossary"):
            builder.add_heading("Glossary", level=2)
            builder.add_blank_line()
            for k, v in sections["glossary"].items():
                builder.add_list_item(f"**{k}:** {v}")
            builder.add_blank_line()

        if sections.get("roadmap"):
            builder.add_heading("Roadmap", level=2)
            builder.add_blank_line()
            for r in sections["roadmap"]:
                builder.add_list_item(r)
            builder.add_blank_line()

        # Appendix: how this doc tool works (kept brief)
        builder.add_heading("Appendix — How this documentation was generated", level=2)
        builder.add_blank_line()
        builder.add_code_block(MermaidGenerator.docgen_sequence_diagram(), "mermaid")
        builder.add_blank_line()

        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write(builder.build())

    # Public API: one-shot convenience
    def generate(self, ladom: Dict[str, Any], output_md_path: str) -> None:
        project_name = ladom.get("project_name") or "Project"
        sections = self.synthesize_sections(ladom)
        self.generate_markdown(project_name, sections, output_md_path, ladom)
