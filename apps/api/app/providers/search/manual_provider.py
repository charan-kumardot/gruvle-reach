from app.providers.search.base import SearchProvider, SearchResult


class ManualURLProvider(SearchProvider):
    """No search at all — the founder or admin supplies exact source URLs to
    research (research_sources table). Always 'configured': the research
    engine simply fetches whatever the user pasted in via the fetcher, and
    this provider exists so the SearchProvider interface stays uniform even
    when no automated search backend is available."""

    name = "manual"

    def __init__(self, urls: list[str]):
        self._urls = urls

    def configured(self) -> bool:
        return True

    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        return [
            SearchResult(title=url, url=url, snippet="", source_type="user_submitted")
            for url in self._urls[:max_results]
        ]
