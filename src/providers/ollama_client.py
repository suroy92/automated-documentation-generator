# src/providers/ollama_client.py
"""
Minimal local LLM client for Ollama.
- No external deps (uses urllib)
- Safe defaults (local-only)
- Tiny API: LLM.generate(...) and LLM.embed(...)

Usage:
    from src.providers.ollama_client import LLM, LLMConfig, from_config
    llm = from_config(cfg_dict)  # or LLM()
    text = llm.generate(system="...", prompt="...")

Ollama must be running locally:
    - Base URL: http://localhost:11434
    - Endpoints: /api/generate, /api/embeddings
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

    # --- Text generation -----------------------------------------------------
    def generate(self, *, system: str = "", prompt: str, temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        # We concatenate system + prompt for Ollama's /api/generate
        final_prompt = f"{system.strip()}\n\n{prompt.strip()}".strip() if system else prompt.strip()
        payload = {
            "model": self.model,
            "prompt": final_prompt,
            "stream": False,
            "options": {"temperature": float(self.temperature if temperature is None else temperature)},
        }
        if max_tokens is not None:
            # Ollama ignores max_tokens for many models, but include if it starts supporting it
            payload["options"]["num_predict"] = int(max_tokens)

        req = Request(
            f"{self.base}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("response", "")

    # --- Embeddings ----------------------------------------------------------
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


# Helper to construct from your YAML dict
def from_config(cfg_dict: dict) -> LLM:
    llm_cfg = (cfg_dict.get("llm") or {}) if isinstance(cfg_dict, dict) else {}
    return LLM(
        LLMConfig(
            base_url=llm_cfg.get("base_url", "http://localhost:11434"),
            model=llm_cfg.get("model", "qwen2.5-coder:7b"),
            temperature=float(llm_cfg.get("temperature", 0.2) or 0.2),
            embedding_model=llm_cfg.get("embedding_model", "all-minilm:l6-v2"),
            timeout_seconds=int(llm_cfg.get("timeout_seconds", 120) or 120),
        )
    )
