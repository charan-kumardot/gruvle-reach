import httpx

from app.providers.search.base import SearchProvider, SearchResult


class TavilyProvider(SearchProvider):
    """Tavily — a purpose-built search API for AI agents, authenticated via
    a real API key rather than scraped HTML. Doesn't hit the cloud-IP
    fingerprinting/CAPTCHA blocking that self-hosted SearxNG runs into from
    Render's IP range (see CLAUDE.md)."""

    name = "tavily"

    def __init__(self, api_key: str):
        self._api_key = api_key

    def configured(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        if not self.configured():
            return []
        try:
            resp = httpx.post(
                "https://api.tavily.com/search",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"query": query, "max_results": max_results},
                timeout=30,
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
                    published_at=item.get("published_date"),
                )
            )
        return results
