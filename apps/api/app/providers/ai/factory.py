from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.ai.base import AIProvider
from app.providers.ai.ollama_provider import OllamaProvider
from app.providers.ai.openai_compatible_provider import GroqProvider, OpenAICompatibleProvider


def build_ai_provider(settings: Settings) -> AIProvider:
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
