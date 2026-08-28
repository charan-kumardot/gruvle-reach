from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.search.base import SearchProvider
from app.providers.search.manual_provider import ManualURLProvider
from app.providers.search.rss_provider import RSSProvider
from app.providers.search.searxng_provider import SearxNGProvider
from app.providers.search.tavily_provider import TavilyProvider


def build_search_provider(settings: Settings, *, feed_urls: list[str] | None = None, manual_urls: list[str] | None = None) -> SearchProvider:
    if settings.search_provider == "tavily":
        return TavilyProvider(settings.tavily_api_key)
    if settings.search_provider == "rss":
        return RSSProvider(feed_urls or [])
    if settings.search_provider == "manual":
        return ManualURLProvider(manual_urls or [])
    return SearxNGProvider(settings.searxng_base_url)


@lru_cache
def get_search_provider() -> SearchProvider:
    return build_search_provider(get_settings())
