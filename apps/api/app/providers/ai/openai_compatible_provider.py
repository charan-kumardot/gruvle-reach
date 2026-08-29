import time

import httpx

from app.providers.ai.base import AIGenerationResult, AIProvider, AIProviderError
from app.providers.ai.utils import extract_json, request_with_retry


class _OpenAIChatCompatibleProvider(AIProvider):
    """Shared implementation for any OpenAI chat-completions-compatible
    endpoint (Groq, together.ai, local vLLM/llama.cpp servers, etc.)."""

    def __init__(self, *, name: str, base_url: str, api_key: str, model: str):
        self.name = name
        self._base_url = base_url.rstrip("/") if base_url else ""
        self._api_key = api_key
        self._model = model

    def configured(self) -> bool:
        return bool(self._base_url and self._api_key and self._model)

    def _chat(self, *, system_prompt: str, user_prompt: str, json_mode: bool) -> AIGenerationResult:
        if not self.configured():
            raise AIProviderError(f"{self.name} provider is not configured (missing base URL, API key, or model)")

        payload: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        def _post() -> httpx.Response:
            r = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            return r

        started = time.perf_counter()
        try:
            resp = request_with_retry(_post)
        except httpx.HTTPError as exc:
            raise AIProviderError(f"{self.name} request failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        raw_json = extract_json(text) if json_mode else None
        return AIGenerationResult(
            text=text,
            raw_json=raw_json,
            provider=self.name,
            model=self._model,
            tokens_used=usage.get("total_tokens", 0),
            latency_ms=latency_ms,
        )

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_hint: str) -> AIGenerationResult:
        full_system = f"{system_prompt}\n\nRespond ONLY with a JSON object matching this shape:\n{schema_hint}"
        return self._chat(system_prompt=full_system, user_prompt=user_prompt, json_mode=True)

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        return self._chat(system_prompt=system_prompt, user_prompt=user_prompt, json_mode=False)


class GroqProvider(_OpenAIChatCompatibleProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(
            name="groq", base_url="https://api.groq.com/openai/v1", api_key=api_key, model=model
        )


class OpenAICompatibleProvider(_OpenAIChatCompatibleProvider):
    def __init__(self, base_url: str, api_key: str, model: str):
        super().__init__(name="openai_compatible", base_url=base_url, api_key=api_key, model=model)


class CerebrasProvider(_OpenAIChatCompatibleProvider):
    def __init__(self, api_key: str, model: str):
        super().__init__(name="cerebras", base_url="https://api.cerebras.ai/v1", api_key=api_key, model=model)


class OpenRouterProvider(_OpenAIChatCompatibleProvider):
    """OpenRouter — an aggregator with several genuinely free models (":free"
    suffix). Those route through a shared upstream community pool, so they
    can be independently rate-limited from Groq/Cerebras/Gemini — a
    different quota to fall back to, not the same one under another name."""

    def __init__(self, api_key: str, model: str):
        super().__init__(name="openrouter", base_url="https://openrouter.ai/api/v1", api_key=api_key, model=model)
