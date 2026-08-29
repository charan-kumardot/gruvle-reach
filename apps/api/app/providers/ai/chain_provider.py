from app.providers.ai.base import AIGenerationResult, AIProvider, AIProviderError


class ChainAIProvider(AIProvider):
    """Tries each provider in order; on unconfigured/failing (AIProviderError
    — covers HTTP errors, rate limits, quota exhaustion, timeouts), moves to
    the next. Used for AI_PROVIDER=chain: an explicit priority order across
    several providers rather than picking just one, so one provider's outage
    or free-tier quota running out doesn't stop the app from working."""

    def __init__(self, providers: list[AIProvider]):
        if not providers:
            raise ValueError("ChainAIProvider needs at least one provider")
        self._providers = providers
        self.name = " -> ".join(p.name for p in providers)

    def configured(self) -> bool:
        return any(p.configured() for p in self._providers)

    def generate_json(self, *, system_prompt: str, user_prompt: str, schema_hint: str) -> AIGenerationResult:
        return self._call("generate_json", system_prompt=system_prompt, user_prompt=user_prompt, schema_hint=schema_hint)

    def generate_text(self, *, system_prompt: str, user_prompt: str) -> AIGenerationResult:
        return self._call("generate_text", system_prompt=system_prompt, user_prompt=user_prompt)

    def _call(self, method: str, **kwargs) -> AIGenerationResult:
        last_exc: AIProviderError | None = None
        for provider in self._providers:
            if not provider.configured():
                continue
            try:
                return getattr(provider, method)(**kwargs)
            except AIProviderError as exc:
                last_exc = exc
                continue
        raise last_exc or AIProviderError(f"No configured provider in chain: {self.name}")
