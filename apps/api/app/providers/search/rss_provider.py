import feedparser

from app.providers.search.base import SearchProvider, SearchResult


class RSSProvider(SearchProvider):
    """Reads one or more RSS/Atom feed URLs and treats the query as a
    substring filter over entry titles/summaries. Free, no API key —
    useful for monitoring specific known sources (a competitor's blog,
    a newsletter, an accelerator's announcements page)."""

    name = "rss"

    def __init__(self, feed_urls: list[str]):
        self._feed_urls = feed_urls

    def configured(self) -> bool:
        return len(self._feed_urls) > 0

    def search(self, query: str, *, max_results: int = 10) -> list[SearchResult]:
        query_lower = query.lower()
        results: list[SearchResult] = []
        for feed_url in self._feed_urls:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries:
                haystack = f"{entry.get('title', '')} {entry.get('summary', '')}".lower()
                if query_lower and query_lower not in haystack:
                    continue
                results.append(
                    SearchResult(
                        title=entry.get("title", ""),
                        url=entry.get("link", ""),
                        snippet=entry.get("summary", "")[:500],
                        source_type="rss",
                        published_at=entry.get("published"),
                    )
                )
                if len(results) >= max_results:
                    return results
        return results
