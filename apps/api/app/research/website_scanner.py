"""
Website scanner (visibility spec §6). Every finding is tagged VERIFIED
(directly observed in a real HTTP response), ESTIMATED (inferred from a
weak proxy signal or a small sample), or UNKNOWN (not measurable without
infrastructure this build doesn't have, e.g. a real Lighthouse run) — never
claimed as a hard metric we can't actually back up.

Routes every fetch through the existing SSRF-safe fetcher — a scanned
website is exactly the kind of "URL that came from a user" that fetcher
exists to protect.
"""
import re
import time
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from app.db.models.enums import ConfidenceLabel
from app.research.fetcher import SSRFBlockedError, safe_fetch

MAX_SAMPLED_LINKS = 8
MAX_SITEMAP_URLS = 5


def _field(value: Any, confidence: ConfidenceLabel) -> dict:
    return {"value": value, "confidence": confidence.value}


def _safe_get_text(url: str, max_bytes: int = 1_500_000) -> tuple[str | None, str | None, float]:
    """Returns (text, final_url, latency_ms) or (None, None, 0) on failure."""
    started = time.perf_counter()
    try:
        result = safe_fetch(url, max_bytes=max_bytes)
    except (SSRFBlockedError, Exception):
        return None, None, 0.0
    latency_ms = (time.perf_counter() - started) * 1000
    if result.status_code >= 400:
        return None, None, latency_ms
    return result.text, result.final_url, latency_ms


def scan_website(url: str) -> dict:
    result: dict[str, dict] = {}

    html, final_url, latency_ms = _safe_get_text(url)
    if html is None:
        result["fetch_error"] = _field(True, ConfidenceLabel.VERIFIED)
        return result

    parsed_final = urlparse(final_url or url)
    origin = f"{parsed_final.scheme}://{parsed_final.netloc}"

    soup = BeautifulSoup(html, "html.parser")

    result["https"] = _field(parsed_final.scheme == "https", ConfidenceLabel.VERIFIED)
    result["redirected"] = _field(bool(final_url and final_url != url), ConfidenceLabel.VERIFIED)
    result["fetch_latency_ms"] = _field(round(latency_ms, 1), ConfidenceLabel.ESTIMATED)
    result["page_size_bytes"] = _field(len(html.encode("utf-8")), ConfidenceLabel.VERIFIED)

    title_tag = soup.find("title")
    result["title"] = _field(title_tag.get_text(strip=True) if title_tag else None, ConfidenceLabel.VERIFIED)

    meta_desc = soup.find("meta", attrs={"name": "description"})
    result["meta_description"] = _field(
        meta_desc.get("content", "").strip() if meta_desc else None, ConfidenceLabel.VERIFIED
    )

    canonical = soup.find("link", attrs={"rel": "canonical"})
    result["canonical_url"] = _field(canonical.get("href") if canonical else None, ConfidenceLabel.VERIFIED)

    robots_meta = soup.find("meta", attrs={"name": "robots"})
    robots_content = (robots_meta.get("content", "") if robots_meta else "").lower()
    result["indexable"] = _field("noindex" not in robots_content, ConfidenceLabel.VERIFIED)

    headings = {
        level: [h.get_text(strip=True) for h in soup.find_all(level)]
        for level in ("h1", "h2", "h3")
    }
    result["headings"] = _field(headings, ConfidenceLabel.VERIFIED)
    result["h1_count"] = _field(len(headings["h1"]), ConfidenceLabel.VERIFIED)

    result["viewport_meta_present"] = _field(soup.find("meta", attrs={"name": "viewport"}) is not None, ConfidenceLabel.VERIFIED)
    result["mobile_friendly"] = _field(
        soup.find("meta", attrs={"name": "viewport"}) is not None, ConfidenceLabel.ESTIMATED
    )

    og_tags = {m.get("property", ""): m.get("content", "") for m in soup.find_all("meta", property=re.compile(r"^og:"))}
    result["open_graph"] = _field(og_tags, ConfidenceLabel.VERIFIED if og_tags else ConfidenceLabel.VERIFIED)

    twitter_tags = {m.get("name", ""): m.get("content", "") for m in soup.find_all("meta", attrs={"name": re.compile(r"^twitter:")})}
    result["twitter_card"] = _field(twitter_tags, ConfidenceLabel.VERIFIED)

    structured_data = [s.string for s in soup.find_all("script", attrs={"type": "application/ld+json"}) if s.string]
    result["structured_data_present"] = _field(len(structured_data) > 0, ConfidenceLabel.VERIFIED)
    result["structured_data_blocks"] = _field(len(structured_data), ConfidenceLabel.VERIFIED)

    images = soup.find_all("img")
    missing_alt = [img.get("src", "") for img in images if not img.get("alt", "").strip()]
    result["image_count"] = _field(len(images), ConfidenceLabel.VERIFIED)
    result["images_missing_alt"] = _field(len(missing_alt), ConfidenceLabel.VERIFIED)

    all_links = soup.find_all("a", href=True)
    internal_links, external_links = [], []
    for a in all_links:
        href = a["href"]
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(final_url or url, href)
        if urlparse(absolute).netloc == parsed_final.netloc:
            internal_links.append(absolute)
        else:
            external_links.append(absolute)
    result["internal_link_count"] = _field(len(internal_links), ConfidenceLabel.VERIFIED)
    result["external_link_count"] = _field(len(external_links), ConfidenceLabel.VERIFIED)

    # Sample a handful of internal links to check for broken links (404s).
    # This is a SAMPLE, not exhaustive — always ESTIMATED, never claimed complete.
    broken = []
    for link in internal_links[:MAX_SAMPLED_LINKS]:
        try:
            sub = safe_fetch(link, max_bytes=50_000)
            if sub.status_code >= 400:
                broken.append({"url": link, "status": sub.status_code})
        except (SSRFBlockedError, Exception):
            continue
    result["broken_links_sample"] = _field(broken, ConfidenceLabel.ESTIMATED)

    # robots.txt
    robots_text, _, _ = _safe_get_text(urljoin(origin, "/robots.txt"), max_bytes=100_000)
    result["robots_txt_present"] = _field(robots_text is not None, ConfidenceLabel.VERIFIED)
    if robots_text:
        result["robots_txt_disallows_root"] = _field(
            bool(re.search(r"^Disallow:\s*/\s*$", robots_text, re.MULTILINE | re.IGNORECASE)), ConfidenceLabel.VERIFIED
        )

    # sitemap.xml
    sitemap_text, _, _ = _safe_get_text(urljoin(origin, "/sitemap.xml"), max_bytes=2_000_000)
    result["sitemap_present"] = _field(sitemap_text is not None, ConfidenceLabel.VERIFIED)

    if sitemap_text:
        sitemap_urls = _parse_sitemap_urls(sitemap_text)[:MAX_SITEMAP_URLS]
        titles_seen: dict[str, list[str]] = {}
        for sm_url in sitemap_urls:
            page_html, _, _ = _safe_get_text(sm_url, max_bytes=800_000)
            if not page_html:
                continue
            page_title_tag = BeautifulSoup(page_html, "html.parser").find("title")
            page_title = page_title_tag.get_text(strip=True) if page_title_tag else ""
            if page_title:
                titles_seen.setdefault(page_title, []).append(sm_url)
        duplicates = {t: urls for t, urls in titles_seen.items() if len(urls) > 1}
        result["duplicate_titles_sample"] = _field(duplicates, ConfidenceLabel.ESTIMATED)
        result["sitemap_sampled_url_count"] = _field(len(sitemap_urls), ConfidenceLabel.VERIFIED)

    result["page_speed_lighthouse_score"] = _field(None, ConfidenceLabel.UNKNOWN)
    result["duplicate_content_full_site"] = _field(None, ConfidenceLabel.UNKNOWN)

    return result


def detect_framework(url: str) -> tuple[str, ConfidenceLabel]:
    """Best-effort framework detection from the rendered homepage response —
    never claimed as certain (§2: 'do not assume a specific framework')."""
    html, _, _ = _safe_get_text(url)
    if html is None:
        return "unknown", ConfidenceLabel.UNKNOWN

    if "/_next/static" in html or "__NEXT_DATA__" in html:
        return "nextjs", ConfidenceLabel.ESTIMATED
    if 'id="root"' in html and ("react" in html.lower() or "reactdom" in html.lower()):
        return "react", ConfidenceLabel.ESTIMATED
    if "<!doctype html>" in html.lower() and "<script" not in html.lower():
        return "static_html", ConfidenceLabel.ESTIMATED
    return "unknown", ConfidenceLabel.UNKNOWN


def _parse_sitemap_urls(sitemap_text: str) -> list[str]:
    try:
        root = ElementTree.fromstring(sitemap_text)
    except ElementTree.ParseError:
        return []
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [loc.text.strip() for loc in root.findall(".//sm:loc", ns) if loc.text]
    if not locs:
        locs = [loc.text.strip() for loc in root.findall(".//loc") if loc.text]
    return locs
