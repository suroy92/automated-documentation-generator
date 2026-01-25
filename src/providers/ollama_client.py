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
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import urllib.error
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"
    temperature: float = 0.2
    embedding_model: Optional[str] = "all-minilm:l6-v2"
    timeout_seconds: int = 300  # Increased from 120 to 300 for larger models


class LLM:
    def __init__(self, cfg: Optional[LLMConfig] = None) -> None:
        cfg = cfg or LLMConfig()
        self.base = (os.getenv("OLLAMA_BASE_URL") or cfg.base_url).rstrip("/")
        self.model = os.getenv("DOCGEN_MODEL") or cfg.model
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE") or cfg.temperature)
        self.embedding_model = os.getenv("DOCGEN_EMBED_MODEL") or cfg.embedding_model
        self.timeout = int(os.getenv("DOCGEN_TIMEOUT") or cfg.timeout_seconds)
        
        # Auto-adjust timeout based on model size
        if "14b" in self.model.lower() or "13b" in self.model.lower():
            self.timeout = max(self.timeout, 300)
            logger.info(f"Auto-adjusted timeout to {self.timeout}s for model: {self.model}")
        elif "30b" in self.model.lower() or "22b" in self.model.lower() or "20b" in self.model.lower():
            self.timeout = max(self.timeout, 480)
            logger.info(f"Auto-adjusted timeout to {self.timeout}s for large model: {self.model}")

    def generate(
        self,
        *,
        system: str = "",
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: int = 5,  # Increased from 3 to 5
    ) -> str:
        final_prompt = f"{system.strip()}\n\n{prompt.strip()}" if system else prompt.strip()
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": final_prompt,
            "stream": False,
            "options": {"temperature": float(self.temperature if temperature is None else temperature)},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = int(max_tokens)

        for attempt in range(max_retries):
            try:
                req = Request(
                    f"{self.base}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                logger.info(f"LLM request attempt {attempt + 1}/{max_retries} (timeout: {self.timeout}s, model: {self.model})")
                with urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                return data.get("response", "")

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                        continue
                    raise RuntimeError(f"Rate limit exceeded after {max_retries} attempts") from e
                elif 400 <= e.code < 500:
                    raise RuntimeError(f"HTTP {e.code}: {e.reason}") from e
                elif 500 <= e.code < 600:
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        logger.warning(f"Server error {e.code}, retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue
                    raise RuntimeError(f"Server error after {max_retries} attempts") from e

            except urllib.error.URLError as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Connection error, retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                raise RuntimeError(f"Failed to connect to Ollama after {max_retries} attempts") from e

            except (TimeoutError, ConnectionResetError, OSError) as e:
                # OSError covers socket.timeout and other socket issues
                error_type = type(e).__name__
                if attempt < max_retries - 1:
                    wait_time = 10 * (2 ** attempt)  # 10s, 20s, 40s, 80s, 160s
                    logger.warning(f"{error_type} on attempt {attempt + 1}/{max_retries}, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                suggestion = self._get_timeout_suggestion()
                raise RuntimeError(
                    f"Timeout after {max_retries} attempts with {self.timeout}s timeout.\n"
                    f"Model: {self.model}\n{suggestion}"
                ) from e

            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise RuntimeError(f"Failed to decode Ollama response: {e}") from e

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"Unexpected error, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                    continue
                raise RuntimeError(f"Failed after {max_retries} attempts: {e}") from e

        raise RuntimeError("Unknown error in LLM request")

    def _get_timeout_suggestion(self) -> str:
        """Provide helpful suggestions for timeout issues."""
        suggestions = []
        
        if "14b" in self.model.lower() or "13b" in self.model.lower():
            suggestions.append("SUGGESTION: Set DOCGEN_TIMEOUT=600 or switch to qwen2.5-coder:7b")
        elif "30b" in self.model.lower() or "22b" in self.model.lower() or "20b" in self.model.lower():
            suggestions.append("SUGGESTION: Large models need DOCGEN_TIMEOUT=900 or use smaller model")
        else:
            suggestions.append("SUGGESTION: Increase DOCGEN_TIMEOUT environment variable")
        
        suggestions.append("ALSO CHECK: Is Ollama running? (ollama serve)")
        suggestions.append("ALSO CHECK: GPU memory available? (nvidia-smi)")
        
        return "\n".join(suggestions)

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


class OllamaClient:
    def __init__(self, config: Dict[str, Any]):
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model = config.get("model", "qwen2.5-coder:7b")
        self.temperature = config.get("temperature", 0.2)
        self.timeout = config.get("timeout", 300)  # Increased to 5 minutes for 14B+ models
        self.max_retries = config.get("max_retries", 5)
        self.retry_delay = config.get("retry_delay", 10)  # Increased base delay
        self.options = config.get("options", {})
        
        # Auto-adjust timeout based on model size
        if "14b" in self.model.lower() or "13b" in self.model.lower():
            self.timeout = max(self.timeout, 300)  # At least 5 minutes
            logger.info(f"Auto-adjusted timeout to {self.timeout}s for model: {self.model}")
        elif "30b" in self.model.lower() or "22b" in self.model.lower() or "20b" in self.model.lower():
            self.timeout = max(self.timeout, 480)  # At least 8 minutes
            logger.info(f"Auto-adjusted timeout to {self.timeout}s for large model: {self.model}")

    def generate(self, system: str = "", prompt: str = "", **kwargs) -> str:
        """Generate text using Ollama API with retry logic."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                **self.options
            }
        }

        max_retries = self.max_retries
        for attempt in range(max_retries):
            try:
                req = Request(
                    f"{self.base_url}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )

                logger.info(f"LLM request attempt {attempt + 1}/{max_retries} (timeout: {self.timeout}s)")

                with urlopen(req, timeout=self.timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    response_text = result.get("response", "")

                    if not response_text:
                        logger.warning("Empty response from LLM")
                        if attempt < max_retries - 1:
                            time.sleep(self.retry_delay)
                            continue

                    return response_text

            except (TimeoutError, OSError) as e:
                # OSError covers socket timeout issues
                error_msg = str(e)
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}: {error_msg}")
                if attempt < max_retries - 1:
                    # Exponential backoff with jitter
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {wait_time}s... (Model: {self.model}, Timeout: {self.timeout}s)")
                    time.sleep(wait_time)
                else:
                    suggestion = self._get_timeout_suggestion()
                    raise RuntimeError(
                        f"Timeout after {max_retries} attempts with {self.timeout}s timeout.\n"
                        f"Model: {self.model}\n{suggestion}"
                    ) from e

            except urllib.error.HTTPError as e:
                logger.error(f"HTTP error on attempt {attempt + 1}/{max_retries}: {e.code} - {e.reason}")
                if e.code >= 500 and attempt < max_retries - 1:
                    # Server errors - retry with backoff
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Server error, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"HTTP {e.code}: {e.reason}") from e

            except Exception as e:
                logger.error(f"LLM generation error on attempt {attempt + 1}: {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Unexpected error, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

    def _get_timeout_suggestion(self) -> str:
        """Provide helpful suggestions for timeout issues."""
        suggestions = []
        
        if "14b" in self.model.lower() or "13b" in self.model.lower():
            suggestions.append("SUGGESTION: Try increasing timeout to 400-600s in config.yaml")
            suggestions.append("OR: Switch to faster model: qwen2.5-coder:7b or deepseek-r1:8b")
        elif "30b" in self.model.lower() or "22b" in self.model.lower() or "20b" in self.model.lower():
            suggestions.append("SUGGESTION: Large models need 600-900s timeout")
            suggestions.append("OR: Use smaller model for business docs, keep large for code analysis")
        else:
            suggestions.append("SUGGESTION: Increase timeout in config.yaml")
        
        suggestions.append("ALSO CHECK: Is Ollama running? (ollama serve)")
        suggestions.append("ALSO CHECK: GPU memory available? (nvidia-smi or Task Manager)")
        
        return "\n".join(suggestions)
