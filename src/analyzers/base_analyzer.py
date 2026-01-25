# src/analyzers/base_analyzer.py

"""
Abstract base for language analyzers.

Week 1 upgrades (patched):
- Ask LLM for STRICT JSON (summary/params/returns/throws/examples/notes)
- Normalize types from the LLM (coerce dict/list → string) BEFORE formatting
- Minimal schema validation + safe fallbacks
- Cache stores normalized JSON
- Prompt tightened to avoid hallucinated libraries/types; empty fields allowed
"""

from __future__ import annotations
from abc import ABC, abstractmethod
import hashlib
import json
import logging
import os
import re
from typing import Optional, Dict, Any, Tuple, List

from ..ladom_schema import LADOMValidator, normalize_ladom
from ..cache_manager import DocstringCache
from ..rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


def _hashtext(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _sanitize_code_for_llm(code: str, max_length: int = 50000) -> str:
    """
    Sanitize code snippets before sending to LLM to prevent prompt injection.

    Args:
        code: Raw code snippet
        max_length: Maximum allowed character count

    Returns:
        Sanitized code snippet safe for LLM prompts
    """
    if not code:
        return ""

    # Remove potential prompt injection patterns
    dangerous_patterns = [
        r"\\b(?:ignore|reset|reset\\s+chat)\\b",
        r"\\b(?:system|assistant|user)\\s*:\\s*",
        r"<<\\|.*?>>",  # Heredoc patterns
        r"`[^`]*`[^`]*`",  # Triple backticks with injection
        r"\\$\\{[^}]*\\}",  # Shell variables
        r"\\$\\([^)]*\\)",  # Command substitution
    ]

    sanitized = code
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)

    # Remove control characters except newlines and tabs
    sanitized = "".join(c for c in sanitized if c.isprintable() or c in "\n\t")

    # Enforce length limits
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "\n... [truncated due to length]"

    # Strip excessive whitespace
    sanitized = "\n".join(line.strip() for line in sanitized.split("\n"))

    return sanitized


def _to_text(value: Any) -> str:
    """Coerce arbitrary JSON-y value into a readable string."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        # Prefer common code/text keys first
        for k in ("code", "text", "value", "summary", "desc", "description", "content"):
            if k in value and isinstance(value[k], (str, int, float, bool)):
                return _to_text(value[k])
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)
    if isinstance(value, list):
        # Join list items as lines
        return "\n".join(_to_text(x) for x in value if x is not None)
    return str(value)


def _norm_param(p: Any) -> Dict[str, Any]:
    """Normalize one parameter entry to a standard dict of strings/bools."""
    if not isinstance(p, dict):
        # Heuristic: try to split "name: type - desc"
        s = _to_text(p)
        name, typ, desc = s, "", ""
        if ":" in s:
            name, rest = s.split(":", 1)
            if "-" in rest:
                typ, desc = [x.strip() for x in rest.split("-", 1)]
            else:
                typ = rest.strip()
        return {"name": name.strip(), "type": typ, "default": None, "desc": desc, "optional": False}

    return {
        "name": _to_text(p.get("name")).strip(),
        "type": _to_text(p.get("type")).strip(),
        "default": None if p.get("default") in (None, "", "None") else _to_text(p.get("default")).strip(),
        "desc": _to_text(p.get("desc") or p.get("description")).strip(),
        "optional": bool(p.get("optional", False)),
    }


class BaseAnalyzer(ABC):
    """Abstract base class for language-specific analyzers."""

    def __init__(self, client=None, cache: Optional[DocstringCache] = None,
                 rate_limiter: Optional[RateLimiter] = None):
        """
        Args:
            client: LLM client (must expose .generate(system=, prompt=, ...))
            cache: Cache manager for generated docs
            rate_limiter: Rate limiter for LLM calls
        """
        self.client = client
        self.cache = cache
        self.rate_limiter = rate_limiter
        self.language = self._get_language_name()
        self.ladom_validator = LADOMValidator()
        logger.info(f"Initialized {self.__class__.__name__}")

    # --- required API ---------------------------------------------------------

    @abstractmethod
    def _get_language_name(self) -> str:
        pass

    @abstractmethod
    def analyze(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Return LADOM for the file or None."""
        pass

    # --- helpers --------------------------------------------------------------

    def _validate_and_normalize(self, ladom: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.ladom_validator.validate_ladom(ladom):
            logger.error(f"LADOM validation failed for {self.language} analyzer")
            return None
        return normalize_ladom(ladom)

    def _create_json_prompt(self, code_snippet: str, *, context: str = "") -> str:
        """
        Ask the LLM for STRICT JSON only.
        Context can include filename, class/method signature, etc., to reduce hallucinations.
        """
        ctx = f"CONTEXT:\n{context}\n\n" if context else ""
        return f"""
You are documenting code. Base your answer ONLY on the provided CODE and optional CONTEXT.
If a detail is unknown from the code, leave it empty (do not guess). Do not invent external libraries or types.

Return STRICT JSON only with this schema:
{{
  "summary": "string",
  "params": [{{"name":"", "type":"", "default": null, "desc":"", "optional": false}}],
  "returns": {{"type":"", "desc":""}},
  "throws": [],
  "examples": [{{"title":"", "code":"", "description":""}}],
  "notes": [],
  "performance": {{"time_complexity":"", "space_complexity":"", "notes":""}},
  "error_handling": {{"strategy":"", "recovery":"", "logging":""}}
}}

QUALITY REQUIREMENTS:
- summary: Be specific and concise (1-2 sentences). Describe what the code does, not how.
- params: For each parameter:
  * desc: Explain purpose and usage, not just type. Include constraints/valid values if evident.
  * type: Use actual types from the code (e.g., "List[str]", "Optional[int]").
- returns: Describe what is returned and under what conditions.
- examples: Provide 2-3 COMPLETE, RUNNABLE examples:
  * title: Descriptive scenario name (e.g., "Basic Usage", "Handling Empty Input", "Error Case")
  * code: Complete code snippet WITHOUT markdown fencing (```). Must be copy-paste ready.
  * description: Explain what the example demonstrates and expected outcome.
- performance:
  * time_complexity: Big O notation if analyzable from code (e.g., "O(n)", "O(log n)", "O(1)")
  * space_complexity: Big O notation for memory usage
  * notes: Identify bottlenecks, loops, recursive calls, or data structure impacts
- error_handling:
  * strategy: Specific approach (e.g., "Validates input then tries operation with fallback to None")
  * recovery: What happens after errors (e.g., "Returns default value", "Re-raises with context")
  * logging: What gets logged at which level
- notes: Add important considerations like thread-safety, side effects, or dependencies

{ctx}CODE:
{code_snippet}
""".strip()

    def _create_refinement_prompt(self, code_snippet: str, draft: Dict[str, Any], 
                                   weak_sections: List[str], *, context: str = "") -> str:
        """
        Ask the LLM to refine specific weak sections identified in the draft.
        
        Args:
            code_snippet: The original code
            draft: Initial documentation attempt
            weak_sections: List of section names needing improvement (e.g., ['summary', 'params', 'examples'])
            context: Optional context information
        """
        ctx = f"CONTEXT:\n{context}\n\n" if context else ""
        draft_json = json.dumps(draft, ensure_ascii=False, indent=2)
        
        sections_focus = "\n".join(f"- {s}" for s in weak_sections) if weak_sections else "- All sections"
        
        return f"""
You are refining documentation JSON. Review the DRAFT and improve ONLY the weak sections identified below.
Use the CODE and optional CONTEXT to make targeted improvements. Do not invent details.

WEAK SECTIONS NEEDING IMPROVEMENT:
{sections_focus}

REFINEMENT CHECKLIST:
1. summary: Is it specific and actionable? Does it avoid vague words like "handles", "processes", "manages"?
2. params: Does each parameter have a clear purpose description beyond just restating the type?
3. returns: Is it clear what's returned and under what conditions (success/failure cases)?
4. examples: Are they complete and runnable? Do they cover typical use and edge cases?
5. performance: Are complexity analyses based on visible loops/recursion in the code?
6. error_handling: Is the strategy specific with actual error types and recovery steps?
7. throws: Are exception types accurate and complete based on the code?
8. notes: Are there important warnings about side effects, thread-safety, or constraints?

IMPROVEMENT GUIDELINES:
- Remove generic/vague descriptions - be specific
- Ensure examples are COMPLETE and copy-paste ready (no markdown fencing)
- Add concrete details from the code (loop patterns, conditional logic, validation steps)
- Identify actual exception types thrown, not generic ones
- For performance, look for loops, recursion, data structure operations

Return STRICT JSON with the FULL schema (even unchanged sections):
{{
  "summary": "string",
  "params": [{{"name":"", "type":"", "default": null, "desc":"", "optional": false}}],
  "returns": {{"type":"", "desc":""}},
  "throws": [],
  "examples": [{{"title":"", "code":"", "description":""}}],
  "notes": [],
  "performance": {{"time_complexity":"", "space_complexity":"", "notes":""}},
  "error_handling": {{"strategy":"", "recovery":"", "logging":""}}
}}

{ctx}DRAFT JSON:
{draft_json}

CODE:
{code_snippet}
""".strip()

    def _has_content(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, dict):
            return any(_to_text(v).strip() for v in value.values())
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    if any(_to_text(v).strip() for v in item.values()):
                        return True
                elif _to_text(item).strip():
                    return True
            return False
        return bool(_to_text(value).strip())

    def _score_section_quality(self, section_name: str, value: Any) -> float:
        """
        Score a documentation section's quality (0.0-1.0).
        Higher scores indicate better quality.
        
        Args:
            section_name: Name of the section (e.g., 'summary', 'params')
            value: The section content
            
        Returns:
            Quality score from 0.0 (poor) to 1.0 (excellent)
        """
        if not self._has_content(value):
            return 0.0
        
        if section_name == "summary":
            text = _to_text(value).strip()
            # Check for vague words
            vague_words = ["handles", "processes", "manages", "deals with", "works with", "does stuff"]
            has_vague = any(vw in text.lower() for vw in vague_words)
            # Prefer 20-200 chars
            length_ok = 20 <= len(text) <= 200
            score = 0.5
            if not has_vague:
                score += 0.3
            if length_ok:
                score += 0.2
            return min(1.0, score)
        
        elif section_name == "params":
            if not isinstance(value, list) or not value:
                return 0.0
            scores = []
            for p in value:
                if not isinstance(p, dict):
                    scores.append(0.3)
                    continue
                desc = _to_text(p.get("desc", "")).strip()
                # Good param description is >10 chars and not just type restating
                if len(desc) > 10 and desc.lower() not in [p.get("type", "").lower(), p.get("name", "").lower()]:
                    scores.append(0.9)
                elif len(desc) > 0:
                    scores.append(0.5)
                else:
                    scores.append(0.1)
            return sum(scores) / len(scores) if scores else 0.0
        
        elif section_name == "returns":
            if not isinstance(value, dict):
                return 0.3
            desc = _to_text(value.get("desc", "")).strip()
            typ = _to_text(value.get("type", "")).strip()
            score = 0.0
            if typ:
                score += 0.3
            if len(desc) > 15:  # Substantive description
                score += 0.7
            elif len(desc) > 0:
                score += 0.3
            return score
        
        elif section_name == "examples":
            if not isinstance(value, list) or not value:
                return 0.0
            scores = []
            for ex in value:
                if isinstance(ex, dict):
                    code = _to_text(ex.get("code", "")).strip()
                    desc = _to_text(ex.get("description", "")).strip()
                    # Good example has substantial code and description
                    if len(code) > 20 and len(desc) > 10:
                        scores.append(1.0)
                    elif len(code) > 10:
                        scores.append(0.6)
                    else:
                        scores.append(0.2)
                else:
                    text = _to_text(ex).strip()
                    scores.append(0.7 if len(text) > 20 else 0.3)
            return sum(scores) / len(scores) if scores else 0.0
        
        elif section_name == "performance":
            if not isinstance(value, dict):
                return 0.0
            time_comp = _to_text(value.get("time_complexity", "")).strip()
            space_comp = _to_text(value.get("space_complexity", "")).strip()
            notes = _to_text(value.get("notes", "")).strip()
            # Check for Big O notation
            has_time = bool(re.search(r"O\([^)]+\)", time_comp))
            has_space = bool(re.search(r"O\([^)]+\)", space_comp))
            has_notes = len(notes) > 10
            score = 0.0
            if has_time:
                score += 0.4
            if has_space:
                score += 0.3
            if has_notes:
                score += 0.3
            return score
        
        elif section_name == "error_handling":
            if not isinstance(value, dict):
                return 0.0
            strategy = _to_text(value.get("strategy", "")).strip()
            recovery = _to_text(value.get("recovery", "")).strip()
            # Good error handling has specific strategy
            if len(strategy) > 20 and "try" in strategy.lower() or "error" in strategy.lower():
                return 0.9
            elif len(strategy) > 10:
                return 0.6
            elif len(strategy) > 0:
                return 0.3
            return 0.0
        
        elif section_name == "throws":
            if not isinstance(value, list):
                return 0.0
            if not value:
                return 0.5  # Not having exceptions might be correct
            # Check if exceptions are specific (not just "Exception")
            specific = sum(1 for t in value if "Exception" in _to_text(t) and _to_text(t).strip() != "Exception")
            return 0.9 if specific > 0 else 0.5
        
        elif section_name == "notes":
            if not isinstance(value, list) or not value:
                return 0.5  # Notes are optional
            # Notes are good if substantive
            avg_len = sum(len(_to_text(n).strip()) for n in value) / len(value)
            return 0.9 if avg_len > 20 else 0.6
        
        return 0.5  # Default neutral score

    def _identify_weak_sections(self, details: Dict[str, Any], threshold: float = 0.6) -> List[str]:
        """
        Identify sections that score below quality threshold.
        
        Args:
            details: Documentation details dict
            threshold: Quality threshold (0.0-1.0). Sections below this need refinement.
            
        Returns:
            List of section names that need improvement
        """
        weak = []
        for section in ["summary", "params", "returns", "examples", "performance", "error_handling", "throws", "notes"]:
            score = self._score_section_quality(section, details.get(section))
            if score < threshold:
                weak.append(section)
                logger.debug(f"Section '{section}' scored {score:.2f}, marked for refinement")
        return weak

    def _merge_details(self, base: Dict[str, Any], refined: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently merge base and refined documentation by comparing quality scores.
        Keeps whichever version scores higher for each section.
        
        Args:
            base: Initial documentation attempt
            refined: Refined documentation from second pass
            
        Returns:
            Best-of-both merged documentation
        """
        out = {}

        # Score and compare each section
        for section in ["summary", "params", "returns", "throws", "examples", "notes", "performance", "error_handling"]:
            base_val = base.get(section)
            refined_val = refined.get(section)
            
            base_score = self._score_section_quality(section, base_val)
            refined_score = self._score_section_quality(section, refined_val)
            
            # Prefer refined if significantly better, or if base is weak
            if refined_score > base_score + 0.1:  # Refined is clearly better
                out[section] = refined_val
                logger.debug(f"Using refined '{section}' (score: {refined_score:.2f} vs {base_score:.2f})")
            elif base_score > refined_score + 0.1:  # Base is clearly better
                out[section] = base_val
                logger.debug(f"Keeping base '{section}' (score: {base_score:.2f} vs {refined_score:.2f})")
            else:  # Scores are close, prefer refined (it had more context)
                out[section] = refined_val if self._has_content(refined_val) else base_val
                logger.debug(f"Close scores for '{section}', using refined")
        
        # Special handling for params: merge individual parameter improvements
        if isinstance(base.get("params"), list) and isinstance(refined.get("params"), list):
            out["params"] = self._merge_params(base["params"], refined["params"])

        return out

    def _merge_params(self, base_params: List[Dict[str, Any]], refined_params: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Merge parameter lists intelligently by matching names and picking better descriptions.
        
        Args:
            base_params: Parameters from initial pass
            refined_params: Parameters from refinement pass
            
        Returns:
            Merged parameter list with best descriptions
        """
        if not base_params:
            return refined_params
        if not refined_params:
            return base_params
        
        # Create lookup by parameter name
        base_by_name = {_to_text(p.get("name", "")).strip(): p for p in base_params if isinstance(p, dict)}
        refined_by_name = {_to_text(p.get("name", "")).strip(): p for p in refined_params if isinstance(p, dict)}
        
        merged = []
        all_names = set(base_by_name.keys()) | set(refined_by_name.keys())
        
        for name in all_names:
            if not name:  # Skip empty names
                continue
            
            base_p = base_by_name.get(name, {})
            refined_p = refined_by_name.get(name, {})
            
            if base_p and refined_p:
                # Both have this param - pick better description
                base_desc_len = len(_to_text(base_p.get("desc", "")).strip())
                refined_desc_len = len(_to_text(refined_p.get("desc", "")).strip())
                
                if refined_desc_len > base_desc_len * 1.2:  # Refined is significantly better
                    merged.append(refined_p)
                else:
                    merged.append(base_p)
            elif refined_p:
                merged.append(refined_p)
            else:
                merged.append(base_p)
        
        return merged

    def _parse_json_lenient(self, raw: str) -> Dict[str, Any]:
        """Attempt to parse JSON, even if model added extra text."""
        try:
            return json.loads(raw)
        except Exception:
            pass
        # Try to isolate the first {...} block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        # Fallback minimal structure skimming the first 280 chars to summary
        return {
            "summary": _to_text(raw).strip()[:280],
            "params": [],
            "returns": {"type": "", "desc": ""},
            "throws": [],
            "examples": [],
            "notes": [],
            "performance": {"time_complexity": "", "space_complexity": "", "notes": ""},
            "error_handling": {"strategy": "", "recovery": "", "logging": ""},
        }

    def _normalize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """Coerce LLM output to the expected shapes and string types."""
        summary = _to_text(details.get("summary")).strip()

        raw_params = details.get("params") or []
        if not isinstance(raw_params, list):
            raw_params = [raw_params]
        params = [_norm_param(p) for p in raw_params if p is not None]

        raw_ret = details.get("returns") or {}
        if isinstance(raw_ret, dict):
            r_type = _to_text(raw_ret.get("type")).strip()
            r_desc = _to_text(raw_ret.get("desc") or raw_ret.get("description")).strip()
        else:
            s = _to_text(raw_ret)
            if " - " in s:
                r_type, r_desc = [x.strip() for x in s.split(" - ", 1)]
            else:
                r_type, r_desc = s.strip(), ""
        returns = {"type": r_type, "desc": r_desc}

        raw_throws = details.get("throws") or []
        if not isinstance(raw_throws, list):
            raw_throws = [raw_throws]
        throws = [_to_text(t).strip() for t in raw_throws if t is not None and _to_text(t).strip()]

        raw_examples = details.get("examples") or []
        if not isinstance(raw_examples, list):
            raw_examples = [raw_examples]
        examples = [_to_text(e).strip() for e in raw_examples if e is not None and _to_text(e).strip()]

        raw_notes = details.get("notes") or []
        if not isinstance(raw_notes, list):
            raw_notes = [raw_notes]
        notes = [_to_text(n).strip() for n in raw_notes if n is not None and _to_text(n).strip()]

        # Normalize examples to include title and description
        normalized_examples = []
        for e in raw_examples:
            if isinstance(e, dict):
                normalized_examples.append({
                    "title": _to_text(e.get("title", "")).strip(),
                    "code": _to_text(e.get("code", "")).strip(),
                    "description": _to_text(e.get("description", "") or e.get("desc", "")).strip(),
                })
            elif e is not None and _to_text(e).strip():
                # Simple string example - convert to dict format
                normalized_examples.append({
                    "title": "",
                    "code": _to_text(e).strip(),
                    "description": "",
                })
        
        # Normalize performance metadata
        raw_perf = details.get("performance") or {}
        if not isinstance(raw_perf, dict):
            raw_perf = {}
        performance = {
            "time_complexity": _to_text(raw_perf.get("time_complexity", "")).strip(),
            "space_complexity": _to_text(raw_perf.get("space_complexity", "")).strip(),
            "notes": _to_text(raw_perf.get("notes", "")).strip(),
        }
        
        # Normalize error handling metadata
        raw_err = details.get("error_handling") or {}
        if not isinstance(raw_err, dict):
            raw_err = {}
        error_handling = {
            "strategy": _to_text(raw_err.get("strategy", "")).strip(),
            "recovery": _to_text(raw_err.get("recovery", "")).strip(),
            "logging": _to_text(raw_err.get("logging", "")).strip(),
        }

        return {
            "summary": summary,
            "params": params,
            "returns": returns,
            "throws": throws,
            "examples": normalized_examples,
            "notes": notes,
            "performance": performance,
            "error_handling": error_handling,
        }

    def _format_google_style_docstring(self, d: Dict[str, Any]) -> str:
        """Produce a compact Google-style block from structured details."""
        parts: List[str] = []
        if d.get("summary"):
            parts.append(_to_text(d["summary"]).strip())

        params = d.get("params") or []
        if params:
            parts.append("\nArgs:")
            for p in params:
                name = _to_text(p.get("name")).strip()
                typ = _to_text(p.get("type")).strip()
                desc = _to_text(p.get("desc") or p.get("description")).strip()
                default = p.get("default", None)
                opt = bool(p.get("optional"))
                tail = ""
                if opt or (default not in (None, "", "None")):
                    tail = f" (optional, default={_to_text(default)})"
                parts.append(f"    {name} ({typ}): {desc}{tail}".rstrip())

        ret = d.get("returns") or {}
        if ret.get("type") or ret.get("desc") or ret.get("description"):
            parts.append("\nReturns:")
            rtyp = _to_text(ret.get("type")).strip()
            rdesc = _to_text(ret.get("desc") or ret.get("description")).strip()
            parts.append(f"    {rtyp}: {rdesc}".rstrip())

        throws = d.get("throws") or []
        if throws:
            parts.append("\nRaises:")
            for t in throws:
                parts.append(f"    {_to_text(t).strip()}")

        ex = d.get("examples") or []
        if ex:
            parts.append("\nExamples:")
            for e in ex[:2]:
                parts.append(f"    {_to_text(e).strip()}")

        return "\n".join(parts).strip() or "No documentation available."

    def _cache_key(self, code_snippet: str) -> str:
        return f"{self.language}:{_hashtext(code_snippet)}"

    def generate_doc(self, code_snippet: str, node_name: str = "unknown", *, context: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        Week 1: JSON contract + docstring text for backward compatibility.

        Returns:
            (docstring_text, normalized_details_dict)
        """
        if not self.client:
            logger.warning(f"No LLM client available for {node_name}")
            empty = {
                "summary": "", 
                "params": [], 
                "returns": {"type": "", "desc": ""}, 
                "throws": [], 
                "examples": [], 
                "notes": [],
                "performance": {"time_complexity": "", "space_complexity": "", "notes": ""},
                "error_handling": {"strategy": "", "recovery": "", "logging": ""},
            }
            return "No documentation available.", empty

        ck = self._cache_key(code_snippet)
        if self.cache:
            cached = self.cache.get(ck, self.language)
            if cached:
                try:
                    data = json.loads(cached)
                    data = self._normalize_details(data)
                    return self._format_google_style_docstring(data), data
                except json.JSONDecodeError:
                    logger.debug(f"Cache entry corrupted for {ck[:8]}..., will regenerate")
                except (TypeError, ValueError) as e:
                    logger.warning(f"Failed to parse cached data: {e}")

        logger.info(f"Generating structured doc for `{node_name}` using local LLM (multi-pass)")

        # Sanitize code snippet to prevent prompt injection
        safe_snippet = _sanitize_code_for_llm(code_snippet)
        prompt = self._create_json_prompt(safe_snippet, context=context)
        try:
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed()
            raw = self.client.generate(system="", prompt=prompt, temperature=0.2)
            details = self._normalize_details(self._parse_json_lenient(raw))
        except Exception as e:
            logger.error(f"LLM failed for {node_name}: {e}")
            details = {
                "summary": "", 
                "params": [], 
                "returns": {"type": "", "desc": ""}, 
                "throws": [], 
                "examples": [], 
                "notes": [],
                "performance": {"time_complexity": "", "space_complexity": "", "notes": ""},
                "error_handling": {"strategy": "", "recovery": "", "logging": ""},
            }
        else:
            # Quality-based selective refinement
            weak_sections = self._identify_weak_sections(details, threshold=0.6)
            
            if weak_sections:
                logger.info(f"Refining {len(weak_sections)} weak sections for `{node_name}`: {weak_sections}")
                try:
                    refine_prompt = self._create_refinement_prompt(
                        safe_snippet, details, weak_sections, context=context
                    )
                    if self.rate_limiter:
                        self.rate_limiter.wait_if_needed()
                    raw_refined = self.client.generate(system="", prompt=refine_prompt, temperature=0.2)
                    refined = self._normalize_details(self._parse_json_lenient(raw_refined))
                    details = self._merge_details(details, refined)
                    logger.info(f"Refinement completed for `{node_name}`")
                except Exception as e:
                    logger.warning(f"LLM refinement pass failed for {node_name}: {e}")
            else:
                logger.info(f"Initial quality sufficient for `{node_name}`, skipping refinement")

        if self.cache:
            try:
                self.cache.set(ck, json.dumps(details, ensure_ascii=False), self.language)
            except Exception:
                pass

        return self._format_google_style_docstring(details), details

    # --- I/O helpers ----------------------------------------------------------

    def _safe_read_file(self, file_path: str, max_size_mb: int = 10) -> Optional[str]:
        """
        Safely read a file with size limits to prevent memory exhaustion.

        Args:
            file_path: Path to file to read
            max_size_mb: Maximum file size in megabytes (default: 10MB)

        Returns:
            File contents as string, or None if file is too large or read fails
        """
        try:
            # Check file size before reading
            file_size = os.path.getsize(file_path)
            max_size_bytes = max_size_mb * 1024 * 1024  # Convert MB to bytes

            if file_size > max_size_bytes:
                logger.warning(
                    f"File {file_path} exceeds size limit ({max_size_mb}MB), skipping. "
                    f"Actual size: {file_size / (1024*1024):.2f}MB"
                )
                return None

            # Read file with progress tracking for large files
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            logger.warning(f"Failed to read {file_path} with UTF-8, trying latin-1")
            try:
                with open(file_path, "r", encoding="latin-1") as f:
                    return f.read()
            except (OSError, IOError) as e:
                logger.error(f"Failed to read {file_path}: {e}")
                return None
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            return None
        except (OSError, IOError) as e:
            logger.error(f"Unexpected error while reading {file_path}: {e}")
            return None
