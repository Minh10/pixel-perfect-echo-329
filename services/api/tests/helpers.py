"""Shared test doubles."""

from __future__ import annotations

import hashlib
import re

import numpy as np


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder.  A *test double*: no semantics beyond token overlap."""

    id = "test-hash-64"
    dim = 64

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, np.float32)
        for tok in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % self.dim] += 1.0  # noqa: S324 - not security
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


class ScriptedLLM:
    """LLM test double: returns pre-written plans in order and records the prompts it received.
    Used to test validation/calculation logic deterministically; it is not a model."""

    provider = "scripted"
    model = "scripted-test-double"

    def __init__(self, responses: list[dict | Exception]) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate_json(self, system, parts, schema, schema_name):
        from app.qa.llm import LLMResult

        self.prompts.append("".join(p for p in parts if isinstance(p, str)))
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return LLMResult(data=r, model=self.model, provider=self.provider, input_tokens=100, output_tokens=50,
                         latency_ms=1.0)
