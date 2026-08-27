import time

import httpx

from app.core.config import Settings
from app.providers.ai.base import AIGenerationResult, AIProvider, AIProviderError
from app.providers.ai.utils import extract_json


class OllamaProvider(AIProvider):
    """Default, free, fully local AI provider — talks to a local Ollama daemon."""

    name = "ollama"

    def __init__(self, settings: Settings):
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model

    def configured(self) -> bool:
        return bool(self._base_url and self._model)

    def _chat(self, *, system_prompt: str, user_prompt: str, json_mode: bool) -> AIGenerationResult:
        if not self.configured():
            raise AIProviderError("Ollama is not configured (OLLAMA_BASE_URL/OLLAMA_MODEL)")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"

        started = time.perf_counter()
        try:
            resp = httpx.post(f"{self._base_url}/api/chat", json=payload, timeout=120)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Ollama request failed: {exc}") from exc
        latency_ms = (time.perf_counter() - started) * 1000

        data = resp.json()
        text = data.get("message", {}).get("content", "")
        raw_json = extract_json(text) if json_mode else None
        return AIGenerationResult(
            text=text,
            raw_json=raw_json,
            provider=self.name,
            model=self._model,
            tokens_used=data.get("eval_count", 0) + data.get("prompt_eval_count", 0),
            latency_ms=latency_ms,
        )

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_hint: str) -> AIGenerationResult:
        full_system = f"{system_prompt}\n\nRespond ONLY with a JSON object matching this shape:\n{schema_hint}"
        return self._chat(system_prompt=full_system, user_prompt=user_prompt, json_mode=True)

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        return self._chat(system_prompt=system_prompt, user_prompt=user_prompt, json_mode=False)
