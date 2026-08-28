"""
Real, web-sourced photos for video scene backgrounds — free (reuses the
already-deployed SearxNG instance, no new signup/quota), and avoids
Hugging Face's paid-credit wall entirely. Implements the same ImageProvider
interface as HuggingFaceImageProvider so scene_renderer.py doesn't need to
know which kind of image it got.

Licensing note: this pulls from whatever SearxNG's image search surfaces
(Bing/etc. under the hood) — the "stock photo" query bias below nudges
results toward stock-photo sites, but this is best-effort, not a
guarantee of a permissive license the way a dedicated stock-photo API
(Pexels/Unsplash/Pixabay) with an API key would be. Content still goes
through the existing human-approval gate before anything publishes.
"""
import httpx

from app.providers.image.base import ImageGenerationResult, ImageProvider
from app.research.fetcher import SSRFBlockedError, safe_fetch_binary

_SKIP_CONTENT_TYPES = {"image/svg+xml", "image/gif"}
_MIN_IMAGE_BYTES = 8_000  # filters out icons/favicons that slipped through
_MAX_CANDIDATES = 8
_STOPWORDS = {"the", "and", "for", "with", "photo", "stock", "modern", "professional", "high", "quality"}


def _significant_words(text: str) -> set[str]:
    return {w for w in text.lower().split() if len(w) > 3 and w not in _STOPWORDS}


def _is_relevant(query_words: set[str], item: dict) -> bool:
    """A general web image index can return something with zero actual
    relation to the query (observed live: a query for 'software engineer
    laptop office' returned a My Little Pony comic cover) — require at
    least one meaningful query word to actually appear in the result's own
    title/description before trusting it as a candidate. Cheap (no extra
    request) and catches the worst mismatches."""
    if not query_words:
        return True
    result_words = _significant_words(f"{item.get('title', '')} {item.get('content', '')}")
    return bool(query_words & result_words)


class SearchSourcedImageProvider(ImageProvider):
    name = "search"

    def __init__(self, searxng_base_url: str):
        self._base_url = searxng_base_url.rstrip("/") if searxng_base_url else ""

    def configured(self) -> bool:
        return bool(self._base_url)

    def generate(self, *, prompt: str, negative_prompt: str = "", width: int = 1024, height: int = 1024) -> ImageGenerationResult:
        if not self.configured():
            return ImageGenerationResult(success=False, error="Search provider not configured")

        query = f"{prompt} stock photo"
        try:
            resp = httpx.get(
                f"{self._base_url}/search",
                params={"q": query, "format": "json", "categories": "images"},
                headers={"User-Agent": "GruvleReachResearchBot/1.0"},
                timeout=20,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ImageGenerationResult(success=False, error=f"Image search failed: {exc}")

        query_words = _significant_words(prompt)
        results = resp.json().get("results", [])[:_MAX_CANDIDATES]
        for item in results:
            image_url = item.get("img_src") or item.get("thumbnail_src")
            if not image_url:
                continue
            if not _is_relevant(query_words, item):
                continue
            try:
                fetched = safe_fetch_binary(image_url, max_bytes=5 * 1024 * 1024)
            except SSRFBlockedError:
                continue
            except Exception:  # noqa: BLE001 — one bad candidate shouldn't stop the search
                continue

            if fetched.status_code != 200:
                continue
            content_type = fetched.content_type.split(";")[0].strip().lower()
            if content_type in _SKIP_CONTENT_TYPES or not content_type.startswith("image/"):
                continue
            if len(fetched.content) < _MIN_IMAGE_BYTES:
                continue

            return ImageGenerationResult(success=True, image_bytes=fetched.content, content_type=content_type)

        return ImageGenerationResult(success=False, error=f"No usable photo found for '{query}'")
