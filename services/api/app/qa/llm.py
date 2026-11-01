"""Provider-independent LLM interface with schema-validated structured outputs.

Providers (FINAUDIT_LLM_PROVIDER):
  * "anthropic" — Claude Messages API via the official `anthropic` SDK, JSON-schema structured output
                  (`output_config.format`), adaptive thinking with configurable effort, and server-side
                  refusal fallback on models that support it.
  * "openai"    — any OpenAI-compatible /chat/completions endpoint with `response_format: json_schema`
                  (OpenAI, vLLM, Ollama, LM Studio, ...).
  * "none"      — no LLM configured: QA endpoints answer 503 `llm_unavailable` (never a fake answer).
Credentials are read server-side from the env var *named* by FINAUDIT_LLM_API_KEY_ENV; they are never
accepted from requests, logged, or returned.  The model id is always configuration, never hard-coded.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

from app.config import Settings

# Models documented to accept the server-side refusal fallback (`fallbacks: "default"`).
_FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")


class LLMError(RuntimeError):
    code = "llm_error"


class LLMUnavailable(LLMError):
    code = "llm_unavailable"


class LLMRefusal(LLMError):
    code = "llm_refused"


class LLMOutputInvalid(LLMError):
    code = "llm_output_invalid"


@dataclass
class ImagePart:
    png: bytes


@dataclass
class LLMResult:
    data: dict
    model: str
    provider: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: float
    stop_reason: str | None = None
    notes: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    provider: str
    model: str

    def generate_json(self, system: str, parts: list[str | ImagePart], schema: dict, schema_name: str) -> LLMResult: ...


def _api_key(s: Settings) -> str | None:
    return os.environ.get(s.llm_api_key_env) or None


class AnthropicProvider:
    provider = "anthropic"

    def __init__(self, s: Settings) -> None:
        if not s.llm_model:
            raise LLMUnavailable("FINAUDIT_LLM_MODEL is not set")
        key = _api_key(s)
        if not key:
            raise LLMUnavailable(f"no API key in ${s.llm_api_key_env}")
        import anthropic

        # Explicit key and base URL: never inherit ambient credentials or ANTHROPIC_BASE_URL.
        self._client = anthropic.Anthropic(api_key=key, base_url=s.llm_base_url or "https://api.anthropic.com",
                                           timeout=s.llm_timeout_s, max_retries=2)
        self._anthropic = anthropic
        self.model = s.llm_model
        self.max_tokens = s.llm_max_output_tokens
        self.effort = s.llm_effort
        self.fallback = s.llm_refusal_fallback and self.model in _FALLBACK_MODELS

    def generate_json(self, system: str, parts: list[str | ImagePart], schema: dict, schema_name: str) -> LLMResult:
        a = self._anthropic
        content = []
        for p in parts:
            if isinstance(p, ImagePart):
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                            "data": base64.standard_b64encode(p.png).decode()}})
            else:
                content.append({"type": "text", "text": p})
        output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
        if self.effort:
            output_config["effort"] = self.effort
        kwargs: dict = {"model": self.model, "max_tokens": self.max_tokens, "system": system,
                        "messages": [{"role": "user", "content": content}], "output_config": output_config}
        if self.fallback:
            kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        t = time.perf_counter()
        try:
            resp = self._client.beta.messages.create(**kwargs)
        except (a.AuthenticationError, a.PermissionDeniedError) as exc:
            raise LLMUnavailable(f"LLM credentials rejected: {exc.message}") from exc
        except a.NotFoundError as exc:
            raise LLMUnavailable(f"LLM model or endpoint not found: {exc.message}") from exc
        except a.RateLimitError as exc:
            raise LLMUnavailable("LLM rate limited (after SDK retries)") from exc
        except a.BadRequestError as exc:
            raise LLMError(f"LLM rejected the request: {exc.message}") from exc
        except a.APIStatusError as exc:
            raise LLMUnavailable(f"LLM API error {exc.status_code}") from exc
        except a.APIConnectionError as exc:
            raise LLMUnavailable(f"LLM API unreachable: {exc}") from exc
        latency = (time.perf_counter() - t) * 1000
        if resp.stop_reason == "refusal":
            cat = getattr(resp.stop_details, "category", None) if resp.stop_details else None
            raise LLMRefusal(f"model declined the request (category={cat})")
        if resp.stop_reason == "max_tokens":
            raise LLMOutputInvalid("model output truncated at max_tokens")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if text is None:
            raise LLMOutputInvalid("no text block in model response")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMOutputInvalid(f"model output is not valid JSON: {exc}") from exc
        notes = [f"served by {resp.model}"] if resp.model != self.model else []
        return LLMResult(data=data, model=resp.model, provider=self.provider, input_tokens=resp.usage.input_tokens,
                         output_tokens=resp.usage.output_tokens, latency_ms=latency, stop_reason=resp.stop_reason,
                         notes=notes)


class OpenAICompatibleProvider:
    provider = "openai"

    def __init__(self, s: Settings) -> None:
        if not s.llm_model or not s.llm_base_url:
            raise LLMUnavailable("FINAUDIT_LLM_MODEL and FINAUDIT_LLM_BASE_URL are required for provider=openai")
        import httpx

        key = _api_key(s)
        self._client = httpx.Client(base_url=s.llm_base_url.rstrip("/"), timeout=s.llm_timeout_s,
                                    headers={"Authorization": f"Bearer {key}"} if key else {})
        self.model, self.max_tokens, self.temperature = s.llm_model, s.llm_max_output_tokens, s.llm_temperature

    def generate_json(self, system: str, parts: list[str | ImagePart], schema: dict, schema_name: str) -> LLMResult:
        import httpx

        content = []
        for p in parts:
            if isinstance(p, ImagePart):
                url = "data:image/png;base64," + base64.standard_b64encode(p.png).decode()
                content.append({"type": "image_url", "image_url": {"url": url}})
            else:
                content.append({"type": "text", "text": p})
        body = {"model": self.model, "max_tokens": self.max_tokens, "temperature": self.temperature,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}],
                "response_format": {"type": "json_schema",
                                    "json_schema": {"name": schema_name, "schema": schema, "strict": True}}}
        t = time.perf_counter()
        try:
            r = self._client.post("/chat/completions", json=body)
        except httpx.HTTPError as exc:
            raise LLMUnavailable(f"LLM endpoint unreachable: {exc}") from exc
        if r.status_code in (401, 403, 404, 429) or r.status_code >= 500:
            raise LLMUnavailable(f"LLM endpoint returned {r.status_code}")
        if r.status_code >= 400:
            raise LLMError(f"LLM rejected the request ({r.status_code}): {r.text[:300]}")
        latency = (time.perf_counter() - t) * 1000
        j = r.json()
        choice = j["choices"][0]
        msg = choice["message"]
        if msg.get("refusal"):
            raise LLMRefusal(f"model declined: {msg['refusal'][:200]}")
        if choice.get("finish_reason") == "length":
            raise LLMOutputInvalid("model output truncated")
        try:
            data = json.loads(msg.get("content") or "")
        except json.JSONDecodeError as exc:
            raise LLMOutputInvalid(f"model output is not valid JSON: {exc}") from exc
        u = j.get("usage") or {}
        return LLMResult(data=data, model=j.get("model", self.model), provider=self.provider,
                         input_tokens=u.get("prompt_tokens"), output_tokens=u.get("completion_tokens"),
                         latency_ms=latency, stop_reason=choice.get("finish_reason"))


def get_llm(s: Settings) -> LLMProvider:
    if s.llm_provider == "anthropic":
        return AnthropicProvider(s)
    if s.llm_provider == "openai":
        return OpenAICompatibleProvider(s)
    raise LLMUnavailable("no LLM provider configured (FINAUDIT_LLM_PROVIDER=none)")


def cost_usd(s: Settings, input_tokens: int | None, output_tokens: int | None) -> float | None:
    """Cost from *configured* prices only; None when prices or token counts are unknown."""
    if s.llm_price_input_per_mtok is None or s.llm_price_output_per_mtok is None:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    return round(input_tokens / 1e6 * s.llm_price_input_per_mtok + output_tokens / 1e6 * s.llm_price_output_per_mtok, 6)
