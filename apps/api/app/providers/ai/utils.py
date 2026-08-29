import json
import re
import time
from typing import Callable

import httpx


def extract_json(text: str) -> dict | None:
    """Best-effort JSON extraction from an LLM response that may wrap the
    object in markdown fences or surrounding prose."""
    text = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
    candidate = fence_match.group(1) if fence_match else text

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def request_with_retry(fn: Callable[[], httpx.Response], *, max_retries: int = 2, base_delay: float = 2.0) -> httpx.Response:
    """Retry a request on 429 with a short backoff, honoring a `Retry-After`
    header when present. Free-tier AI providers (Gemini, Groq) commonly cap
    requests per minute, not per day — the discovery agents' bulk
    classification calls hit that ceiling easily, and without a short retry
    every call made after the limit trips permanently fails (skipped as
    "not a company/investor/etc.") instead of succeeding a few seconds
    later once the window resets. `fn` must both make the request and call
    `raise_for_status()` so a 429 actually raises here to be caught."""
    last_exc: httpx.HTTPStatusError | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 429 or attempt == max_retries:
                raise
            retry_after = exc.response.headers.get("retry-after")
            delay = float(retry_after) if retry_after else base_delay * (attempt + 1)
            time.sleep(min(delay, 10.0))
            last_exc = exc
    raise last_exc  # pragma: no cover — loop above always returns or raises
