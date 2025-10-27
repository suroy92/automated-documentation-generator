# src/providers/ollama_client.py
"""
Minimal local LLM client for Ollama.
- Pure stdlib (urllib) — no external deps
- POSTs to http://localhost:11434/api/generate (and /api/embeddings if you use it later)

Usage:
    from src.providers.ollama_client import LLM, LLMConfig
    llm = LLM(LLMConfig(model="qwen2.5-coder:7b"))
    text = llm.generate(system="", prompt="...")

Environment overrides:
    OLLAMA_BASE_URL  (default http://localhost:11434)
    DOCGEN_MODEL     (e.g., qwen2.5-coder:7b)
    OLLAMA_TEMPERATURE
    DOCGEN_TIMEOUT
    DOCGEN_EMBED_MODEL
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass
from typing import Any, List, Optional
from urllib.request import Request, urlopen


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"
    temperature: float = 0.2
    embedding_model: Optional[str] = "all-minilm:l6-v2"
    timeout_seconds: int = 120


class LLM:
    def __init__(self, cfg: Optional[LLMConfig] = None) -> None:
        cfg = cfg or LLMConfig()
        self.base = (os.getenv("OLLAMA_BASE_URL") or cfg.base_url).rstrip("/")
        self.model = os.getenv("DOCGEN_MODEL") or cfg.model
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE") or cfg.temperature)
        self.embedding_model = os.getenv("DOCGEN_EMBED_MODEL") or cfg.embedding_model
        self.timeout = int(os.getenv("DOCGEN_TIMEOUT") or cfg.timeout_seconds)

    def generate(
        self,
        *,
        system: str = "",
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        final_prompt = f"{system.strip()}\n\n{prompt.strip()}".strip() if system else prompt.strip()
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": final_prompt,
            "stream": False,
            "options": {"temperature": float(self.temperature if temperature is None else temperature)},
        }
        if max_tokens is not None:
            # Supported by some models/endpoints as num_predict
            payload["options"]["num_predict"] = int(max_tokens)

        req = Request(
            f"{self.base}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("response", "")

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not self.embedding_model:
            raise RuntimeError("No embedding_model configured")
        vectors: List[List[float]] = []
        for t in texts:
            req = Request(
                f"{self.base}/api/embeddings",
                data=json.dumps({"model": self.embedding_model, "prompt": t}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            vectors.append(data["embedding"])
        return vectors
