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
You are documenting code. Base your answer only on the provided CODE and optional CONTEXT.
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
- For "examples", provide up to 3 examples with:
  * title: Brief name (e.g., "Basic Usage", "Edge Case: Empty Input")
  * code: Minimal code snippet (no fencing)
  * description: What the example demonstrates
- For "performance":
  * time_complexity: Big O notation (e.g., "O(n)", "O(log n)", "O(1)")
  * space_complexity: Big O notation for memory usage
  * notes: Any performance considerations or bottlenecks
- For "error_handling":
  * strategy: How errors are handled (e.g., "try-catch with fallback", "returns None on error")
  * recovery: Recovery approach if applicable
  * logging: What gets logged and when
- Keep types simple (e.g., "string", "number", "object") unless explicitly present in the code.
- Language should match the code.

{ctx}CODE:
{code_snippet}
""".strip()

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

        if self.rate_limiter:
            self.rate_limiter.wait_if_needed()

        logger.info(f"Generating structured doc for `{node_name}` using local LLM")

        # Sanitize code snippet to prevent prompt injection
        safe_snippet = _sanitize_code_for_llm(code_snippet)
        prompt = self._create_json_prompt(safe_snippet, context=context)
        try:
            raw = self.client.generate(system="", prompt=prompt, temperature=0.2)
            details = self._parse_json_lenient(raw)
            details = self._normalize_details(details)
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
