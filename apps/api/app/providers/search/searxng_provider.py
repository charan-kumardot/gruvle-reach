import httpx

from app.providers.search.base import SearchProvider, SearchResult


class SearxNGProvider(SearchProvider):
    """Free, open-source, self-hosted metasearch — the default search backend.
    No API key required. Point SEARXNG_BASE_URL at your own instance
    (docker-compose brings one up locally)."""

    name = "searxng"

    def __init__(self, base_url: str):
        self._base_url = base_url.rstrip("/") if base_url else ""

    def configured(self) -> bool:
        return bool(self._base_url)

    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        if not self.configured():
            return []
        try:
            resp = httpx.get(
                f"{self._base_url}/search",
                params={"q": query, "format": "json"},
                timeout=20,
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return []

        data = resp.json()
        results = []
        for item in data.get("results", [])[:max_results]:
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source_type="webpage",
                    published_at=item.get("publishedDate"),
                )
            )
        return results
