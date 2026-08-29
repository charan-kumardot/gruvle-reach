import threading
import time

from app.providers.ai.base import AIGenerationResult, AIProvider, AIProviderError

_COOLDOWN_SECONDS = 60.0


class ChainAIProvider(AIProvider):
    """Tries each provider in order; on unconfigured/failing (AIProviderError
    — covers HTTP errors, rate limits, quota exhaustion, timeouts), moves to
    the next. Used for AI_PROVIDER=chain: an explicit priority order across
    several providers rather than picking just one, so one provider's outage
    or free-tier quota running out doesn't stop the app from working.

    A provider that just failed is skipped for a short cooldown rather than
    retried from scratch on every subsequent call — without this, a bulk
    operation (discovery agents can make hundreds of classification calls)
    re-attempts an already-known-rate-limited/quota-exhausted tier (plus its
    own internal retry-with-backoff, see utils.py::request_with_retry) on
    every single call, turning what should be a fast fallback into ~20-30s
    of wasted retries per call. Cooldown state is process-lifetime (this is
    a singleton via get_ai_provider()'s lru_cache), which doubles as a
    self-protective backoff against a provider under load."""

    def __init__(self, providers: list[AIProvider]):
        if not providers:
            raise ValueError("ChainAIProvider needs at least one provider")
        self._providers = providers
        self.name = " -> ".join(p.name for p in providers)
        self._cooldown_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def configured(self) -> bool:
        return any(p.configured() for p in self._providers)

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_hint: str) -> AIGenerationResult:
        return self._call("generate_json", system_prompt=system_prompt, user_prompt=user_prompt, schema_hint=schema_hint)

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        return self._call("generate_text", system_prompt=system_prompt, user_prompt=user_prompt)

    def _call(self, method: str, **kwargs) -> AIGenerationResult:
        now = time.monotonic()
        last_exc: AIProviderError | None = None
        for provider in self._providers:
            if not provider.configured():
                continue
            with self._lock:
                cooling_down = self._cooldown_until.get(provider.name, 0.0) > now
            if cooling_down:
                continue
            try:
                return getattr(provider, method)(**kwargs)
            except AIProviderError as exc:
                last_exc = exc
                with self._lock:
                    self._cooldown_until[provider.name] = time.monotonic() + _COOLDOWN_SECONDS
                continue
        raise last_exc or AIProviderError(f"No configured (or all cooling down) provider in chain: {self.name}")
