"""
Scheduled-job trigger endpoints — replace Celery beat (see CLAUDE.md).
Render's free plan won't run a `type: worker` service, so instead of a
long-running beat process, an external scheduler (GitHub Actions cron) calls
these endpoints on a schedule with a shared secret. Each job runs in a
background thread so the triggering request returns immediately rather than
blocking for a potentially slow scan across every workspace/product.
"""
import logging
import threading
from typing import Annotated, Callable

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import require_cron_secret
from app.workers import tasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cron", tags=["cron"])

# Names match the original Celery `beat_schedule` keys 1:1 so the schedule
# documented in CLAUDE.md and the GitHub Actions workflow stay easy to
# cross-reference against this mapping.
_JOBS: dict[str, Callable[[], int]] = {
    "daily-founder-brief": tasks.generate_daily_briefs_for_all_workspaces,
    "competitor-scan": tasks.scan_all_competitors,
    "weekly-market-brief": tasks.generate_weekly_market_briefs,
    "autonomous-customer-discovery": tasks.discover_customers_for_all_products,
    "autonomous-investor-discovery": tasks.discover_investors_for_all_products,
    "weekly-marketing-discovery": tasks.discover_marketing_opportunities_for_all_products,
    "daily-content-planning": tasks.plan_and_generate_daily_content,
    "content-quality-sweep": tasks.run_content_quality_scan,
    "publish-due-content": tasks.publish_due_content,
    "weekly-content-learning": tasks.run_content_learning,
}


def _run_job(job_name: str, task_fn: Callable[[], int]) -> None:
    try:
        result = task_fn()
        logger.info("cron job %s completed: %s", job_name, result)
    except Exception:  # noqa: BLE001 — a failed scheduled run must never crash the thread silently
        logger.exception("cron job %s failed", job_name)


@router.post("/{job_name}")
def trigger_cron_job(job_name: str, _: Annotated[None, Depends(require_cron_secret)]):
    task_fn = _JOBS.get(job_name)
    if task_fn is None:
        raise HTTPException(status_code=404, detail=f"Unknown cron job: {job_name}. Known jobs: {sorted(_JOBS)}")

    threading.Thread(target=_run_job, args=(job_name, task_fn), daemon=True).start()
    return {"status": "started", "job": job_name}
