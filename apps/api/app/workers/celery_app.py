from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("gruvle_reach", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# §66 automation schedule. Every task here only ever *recommends* — nothing
# scheduled sends/publishes without a human approval step (§67).
celery_app.conf.beat_schedule = {
    "daily-founder-brief": {
        "task": "app.workers.tasks.generate_daily_briefs_for_all_workspaces",
        "schedule": crontab(hour=7, minute=0),
    },
    "competitor-scan": {
        "task": "app.workers.tasks.scan_all_competitors",
        "schedule": crontab(hour=6, minute=0),
    },
    "weekly-market-brief": {
        "task": "app.workers.tasks.generate_weekly_market_briefs",
        "schedule": crontab(day_of_week=1, hour=6, minute=30),
    },
}

celery_app.autodiscover_tasks(["app.workers"])
