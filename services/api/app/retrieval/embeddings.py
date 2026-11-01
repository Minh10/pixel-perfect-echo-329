"""Provider-independent text embedders.

Backends (FINAUDIT_EMBEDDER):
  * "onnx"                  local ONNX sentence encoder + tokenizer.json (default: all-MiniLM-L6-v2,
                            fetched by `python -m app.retrieval.fetch_models`). Mean pooling + L2 norm.
  * "wordllama"             WordLlama static embeddings (weights bundled in the PyPI wheel; weaker).
  * "openai"                any OpenAI-compatible /v1/embeddings endpoint (OpenAI, vLLM, Ollama, TEI...).
  * "sentence-transformers" a SentenceTransformer model name/path (needs the package + weights).
  * "none"                  dense retrieval disabled.
Every embedder exposes a stable `id` that is stored with vectors, so vectors from different models are
never mixed (the Qdrant collection name includes it).
"""

from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from app.config import Settings


class EmbedderUnavailable(RuntimeError):
    pass


class Embedder(Protocol):
    id: str
    dim: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


def _l2(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return (x / np.clip(n, 1e-12, None)).astype(np.float32)


@dataclass
class OnnxSentenceEmbedder:
    model_dir: Path
    max_length: int = 256
    batch_size: int = 32
    query_prefix: str = ""
    document_prefix: str = ""
    num_threads: int = 4

    def __post_init__(self) -> None:
        model, tok = self.model_dir / "model.onnx", self.model_dir / "tokenizer.json"
        if not model.exists() or not tok.exists():
            raise EmbedderUnavailable(
                f"ONNX embedder files not found in {self.model_dir} (need model.onnx + tokenizer.json). "
                "Run: python -m app.retrieval.fetch_models"
            )
        import onnxruntime as ort
        from tokenizers import Tokenizer

        so = ort.SessionOptions()
        so.intra_op_num_threads = self.num_threads
        self._sess = ort.InferenceSession(str(model), sess_options=so, providers=["CPUExecutionProvider"])
        self._inputs = {i.name for i in self._sess.get_inputs()}
        self._tok = Tokenizer.from_file(str(tok))
        self._tok.enable_truncation(max_length=self.max_length)
        self._tok.enable_padding(pad_id=0, pad_token="[PAD]")
        self._lock = threading.Lock()
        digest = hashlib.sha256(model.read_bytes()).hexdigest()[:12]
        self.dim = int(self._sess.get_outputs()[0].shape[-1])
        self.id = f"onnx-{self.model_dir.name}-{digest}"

    def _encode(self, texts: list[str]) -> np.ndarray:
        out: list[np.ndarray] = []
        for i in range(0, len(texts), self.batch_size):
            enc = self._tok.encode_batch(texts[i:i + self.batch_size])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feeds = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feeds["token_type_ids"] = np.zeros_like(ids)
            with self._lock:
                hidden = self._sess.run(None, feeds)[0]
            m = mask[..., None].astype(np.float32)
            out.append((hidden * m).sum(1) / np.clip(m.sum(1), 1e-9, None))  # mean pooling
        return _l2(np.vstack(out)) if out else np.zeros((0, self.dim), np.float32)

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return self._encode([self.document_prefix + t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._encode([self.query_prefix + text])[0]


class WordLlamaEmbedder:
    def __init__(self, dim: int = 256) -> None:
        try:
            import wordllama
            from wordllama import WordLlama
        except ImportError as exc:
            raise EmbedderUnavailable("wordllama package not installed") from exc
        pkg = Path(wordllama.__file__).parent
        try:  # weights + tokenizer config ship inside the wheel; never download
            self._wl = WordLlama.load(dim=dim, cache_dir=pkg, disable_download=True)
        except Exception as exc:
            raise EmbedderUnavailable(f"WordLlama could not load bundled weights: {exc}") from exc
        self.dim = dim
        self.id = f"wordllama-l2supercat-{dim}"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _l2(np.asarray(self._wl.embed(texts), dtype=np.float32)) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]


class OpenAICompatibleEmbedder:
    def __init__(self, base_url: str, model: str, api_key: str | None, dim: int | None, batch_size: int = 64) -> None:
        import httpx

        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=60,
                                    headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
        self.model, self.batch_size = model, batch_size
        self.id = f"openai-{model.replace('/', '_')}"
        self.dim = dim or len(self._call(["dimension probe"])[0])

    def _call(self, texts: list[str]) -> list[list[float]]:
        try:
            r = self._client.post("/embeddings", json={"model": self.model, "input": texts})
            r.raise_for_status()
        except Exception as exc:
            raise EmbedderUnavailable(f"embedding endpoint failed: {exc}") from exc
        data = sorted(r.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        vecs: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            vecs += self._call(texts[i:i + self.batch_size])
        return _l2(np.asarray(vecs, dtype=np.float32)) if vecs else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([text])[0]


class SentenceTransformersEmbedder:
    def __init__(self, model: str, query_prefix: str = "", document_prefix: str = "") -> None:
        try:
            from sentence_transformers import SentenceTransformer

            self._m = SentenceTransformer(model, device="cpu")
        except Exception as exc:
            raise EmbedderUnavailable(f"sentence-transformers model {model!r} unavailable: {exc}") from exc
        self.query_prefix, self.document_prefix = query_prefix, document_prefix
        self.dim = int(self._m.get_sentence_embedding_dimension())
        self.id = f"st-{model.replace('/', '_')}"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _l2(np.asarray(self._m.encode([self.document_prefix + t for t in texts]), dtype=np.float32))

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([self.query_prefix + text])[0]


_cache: dict[tuple, Embedder] = {}
_cache_lock = threading.Lock()


def get_embedder(s: Settings, name: str | None = None) -> Embedder | None:
    """Return the configured embedder (cached per process), None if disabled.  Raises EmbedderUnavailable."""
    backend = name or s.embedder
    if backend == "none":
        return None
    key = (backend, str(s.embedder_model_path), s.embedder_model, s.embedder_base_url)
    with _cache_lock:
        if key in _cache:
            return _cache[key]
        if backend == "onnx":
            emb: Embedder = OnnxSentenceEmbedder(s.embedder_model_path, max_length=s.embedder_max_length,
                                                 query_prefix=s.embedder_query_prefix,
                                                 document_prefix=s.embedder_document_prefix)
        elif backend == "wordllama":
            emb = WordLlamaEmbedder()
        elif backend == "openai":
            if not s.embedder_base_url or not s.embedder_model:
                raise EmbedderUnavailable("FINAUDIT_EMBEDDER_BASE_URL and FINAUDIT_EMBEDDER_MODEL are required")
            emb = OpenAICompatibleEmbedder(s.embedder_base_url, s.embedder_model,
                                           os.environ.get(s.embedder_api_key_env), s.embedder_dim)
        elif backend == "sentence-transformers":
            emb = SentenceTransformersEmbedder(s.embedder_model or "", s.embedder_query_prefix, s.embedder_document_prefix)
        else:
            raise EmbedderUnavailable(f"unknown embedder backend {backend!r}")
        _cache[key] = emb
        return emb
