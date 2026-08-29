import time

import httpx

from app.providers.ai.base import AIGenerationResult, AIProvider, AIProviderError
from app.providers.ai.utils import extract_json, request_with_retry

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(AIProvider):
    """Google Gemini via the Generative Language API (v1beta) — auth is an
    API key in the query string, not a bearer token, and the request/response
    shape (contents/systemInstruction/parts, usageMetadata) differs from the
    OpenAI-chat-completions shape the other providers share, so this doesn't
    reuse `_OpenAIChatCompatibleProvider`."""

    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    def configured(self) -> bool:
        return bool(self._api_key and self._model)

    def _generate(self, *, system_prompt: str, user_prompt: str, json_mode: bool) -> AIGenerationResult:
        if not self.configured():
            raise AIProviderError("gemini provider is not configured (missing API key or model)")

        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
        }
        if json_mode:
            payload["generationConfig"] = {"responseMimeType": "application/json"}

        def _post() -> httpx.Response:
            r = httpx.post(
                f"{_API_BASE}/{self._model}:generateContent",
                # Header, not `?key=` query param — httpx's default request
                # logging prints the full URL including query params, which
                # would otherwise leak the API key into Render's logs.
                headers={"x-goog-api-key": self._api_key},
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            return r

        started = time.perf_counter()
        try:
            resp = request_with_retry(_post)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"gemini request failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        data = resp.json()
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError) as exc:
            raise AIProviderError(f"gemini response had no usable content: {data}") from exc
        # Thinking-capable models can include reasoning-trace parts alongside
        # the actual answer — only the non-thought parts are the real output.
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        usage = data.get("usageMetadata", {})
        raw_json = extract_json(text) if json_mode else None
        return AIGenerationResult(
            text=text,
            raw_json=raw_json,
            provider=self.name,
            model=self._model,
            tokens_used=usage.get("totalTokenCount", 0),
            latency_ms=latency_ms,
        )

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_hint: str) -> AIGenerationResult:
        full_system = f"{system_prompt}\n\nRespond ONLY with a JSON object matching this shape:\n{schema_hint}"
        return self._generate(system_prompt=full_system, user_prompt=user_prompt, json_mode=True)

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        return self._generate(system_prompt=system_prompt, user_prompt=user_prompt, json_mode=False)
