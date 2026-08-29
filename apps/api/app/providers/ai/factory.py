from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.ai.base import AIProvider
from app.providers.ai.chain_provider import ChainAIProvider
from app.providers.ai.gemini_provider import GeminiProvider
from app.providers.ai.ollama_provider import OllamaProvider
from app.providers.ai.openai_compatible_provider import (
    CerebrasProvider,
    GroqProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
)


def build_ai_provider(settings: Settings) -> AIProvider:
    if settings.ai_provider == "chain":
        # Explicit priority order, not just "pick one provider": Groq and
        # OpenRouter's free models first (separate quota pools, both real
        # cloud APIs), then Cerebras, then Gemini (a very tight free daily
        # cap — save it), then local Ollama as a last resort (inert in
        # production; there's no local daemon to reach on Render, but
        # harmless to include for local dev). Each tier is skipped if
        # unconfigured/cooling down and falls through to the next on any
        # AIProviderError (HTTP error, rate limit, quota exhaustion, timeout)
        # — see chain_provider.py for the cooldown mechanism.
        return ChainAIProvider([
            GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model),
            OpenRouterProvider(api_key=settings.openrouter_api_key, model=settings.openrouter_model),
            CerebrasProvider(api_key=settings.cerebras_api_key, model=settings.cerebras_model),
            GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model),
            OllamaProvider(settings),
        ])
    if settings.ai_provider == "gemini":
        return GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    if settings.ai_provider == "cerebras":
        return CerebrasProvider(api_key=settings.cerebras_api_key, model=settings.cerebras_model)
    if settings.ai_provider == "openrouter":
        return OpenRouterProvider(api_key=settings.openrouter_api_key, model=settings.openrouter_model)
    if settings.ai_provider == "groq":
        return GroqProvider(api_key=settings.groq_api_key, model=settings.groq_model)
    if settings.ai_provider == "openai_compatible":
        return OpenAICompatibleProvider(
            base_url=settings.openai_compatible_base_url,
            api_key=settings.openai_compatible_api_key,
            model=settings.openai_compatible_model,
        )
    return OllamaProvider(settings)


@lru_cache
def get_ai_provider() -> AIProvider:
    return build_ai_provider(get_settings())
