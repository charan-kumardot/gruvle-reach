"""
SSRF-safe HTTP fetcher (§43). Every research/evidence/competitor-watch/
brand-monitor feature routes through this — nothing else in the app is
allowed to make an outbound request to a URL supplied by research data or
another user, except through here.

Defenses:
- Resolve DNS ourselves and reject private/loopback/link-local/multicast/
  reserved ranges and the cloud metadata address before connecting.
- Re-validate on every redirect hop (redirects are not followed automatically
  by httpx's transport — we do it manually so each hop is re-checked).
- Hard timeout and a response-size cap enforced while streaming, not just
  after the fact.
- Only http/https schemes.
"""
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

MAX_REDIRECTS = 5
TIMEOUT_SECONDS = 15.0
MAX_RESPONSE_BYTES = 3 * 1024 * 1024  # 3 MB
BLOCKED_PORTS = {22, 23, 25, 3306, 5432, 6379, 11211}

_METADATA_IPS = {
    ipaddress.ip_address("169.254.169.254"),  # AWS/GCP/Azure metadata
    ipaddress.ip_address("100.100.100.200"),  # Alibaba Cloud metadata
}


class SSRFBlockedError(RuntimeError):
    pass


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    truncated: bool


@dataclass
class BinaryFetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    content: bytes
    truncated: bool


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip in _METADATA_IPS:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_host(hostname: str, port: int | None) -> None:
    if port is not None and port in BLOCKED_PORTS:
        raise SSRFBlockedError(f"Blocked port: {port}")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise SSRFBlockedError(f"DNS resolution failed for {hostname}") from exc

    for info in infos:
        raw_ip = info[4][0]
        ip = ipaddress.ip_address(raw_ip)
        if _is_blocked_ip(ip):
            raise SSRFBlockedError(f"Blocked address for {hostname}: {raw_ip}")


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SSRFBlockedError(f"Blocked scheme: {parsed.scheme}")
    if not parsed.hostname:
        raise SSRFBlockedError("URL has no hostname")
    if parsed.hostname.lower() in ("localhost", "metadata", "metadata.google.internal"):
        raise SSRFBlockedError(f"Blocked hostname: {parsed.hostname}")
    _validate_host(parsed.hostname, parsed.port)


def safe_fetch(url: str, *, max_bytes: int = MAX_RESPONSE_BYTES, timeout: float = TIMEOUT_SECONDS) -> FetchResult:
    """Fetch a URL with SSRF protection, manual redirect validation, and a
    hard cap on response size enforced while streaming."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        _validate_url(current_url)

        with httpx.Client(follow_redirects=False, timeout=timeout) as client:
            with client.stream("GET", current_url, headers={"User-Agent": "GruvleReachResearchBot/1.0"}) as resp:
                if resp.is_redirect:
                    next_url = resp.headers.get("location")
                    if not next_url:
                        raise SSRFBlockedError("Redirect with no Location header")
                    current_url = httpx.URL(current_url).join(next_url).human_repr()
                    continue

                content_type = resp.headers.get("content-type", "")
                chunks: list[bytes] = []
                total = 0
                truncated = False
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        truncated = True
                        break
                    chunks.append(chunk)

                body = b"".join(chunks)
                text = body.decode(resp.encoding or "utf-8", errors="replace")
                return FetchResult(
                    url=url,
                    final_url=str(resp.url),
                    status_code=resp.status_code,
                    content_type=content_type,
                    text=text,
                    truncated=truncated,
                )

    raise SSRFBlockedError("Too many redirects")


def safe_fetch_binary(url: str, *, max_bytes: int = MAX_RESPONSE_BYTES, timeout: float = TIMEOUT_SECONDS) -> BinaryFetchResult:
    """Same SSRF protections/redirect re-validation/streaming size cap as
    safe_fetch, but returns raw bytes instead of decoding as text — for
    downloading binary content (images) where UTF-8 decoding would corrupt
    the data. Used to fetch web-search-sourced photos for video scene
    backgrounds; never used for anything HTML/text."""
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        _validate_url(current_url)

        with httpx.Client(follow_redirects=False, timeout=timeout) as client:
            with client.stream("GET", current_url, headers={"User-Agent": "GruvleReachResearchBot/1.0"}) as resp:
                if resp.is_redirect:
                    next_url = resp.headers.get("location")
                    if not next_url:
                        raise SSRFBlockedError("Redirect with no Location header")
                    current_url = httpx.URL(current_url).join(next_url).human_repr()
                    continue

                content_type = resp.headers.get("content-type", "")
                chunks: list[bytes] = []
                total = 0
                truncated = False
                for chunk in resp.iter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        truncated = True
                        break
                    chunks.append(chunk)

                return BinaryFetchResult(
                    url=url,
                    final_url=str(resp.url),
                    status_code=resp.status_code,
                    content_type=content_type,
                    content=b"".join(chunks),
                    truncated=truncated,
                )

    raise SSRFBlockedError("Too many redirects")
