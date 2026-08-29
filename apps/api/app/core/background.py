"""
Shared helper for the async-thread pattern (see CLAUDE.md: "Long-running
work on a free-tier web dyno needs the async-thread pattern"). Render's free
web service has a request timeout and can silently kill in-flight
synchronous work — anything that might run longer than a few seconds
(discovery agents scanning dozens of queries, scheduled jobs) must return
fast and do the real work in a background thread with its own DB session,
never the request-scoped one (which closes when the request returns).
"""
import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)


def run_in_background(fn: Callable[[], None], *, label: str) -> None:
    """Runs `fn` in a daemon thread, logging completion/failure. `fn` must
    open and close its own DB session (e.g. `app.db.session.SessionLocal()`)
    and must not reference any ORM object loaded on the caller's
    request-scoped session — pass plain IDs into the closure instead and
    re-fetch inside `fn`."""

    def _wrapped() -> None:
        try:
            fn()
            logger.info("background task %s completed", label)
        except Exception:  # noqa: BLE001 — a background task must never crash silently or take the thread down uncaught
            logger.exception("background task %s failed", label)

    threading.Thread(target=_wrapped, daemon=True).start()
