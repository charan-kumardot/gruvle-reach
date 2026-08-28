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
    # §22 autonomous discovery — scan/recommend only, never sends/publishes.
    "autonomous-customer-discovery": {
        "task": "app.workers.tasks.discover_customers_for_all_products",
        "schedule": crontab(hour=5, minute=0),
    },
    "autonomous-investor-discovery": {
        "task": "app.workers.tasks.discover_investors_for_all_products",
        "schedule": crontab(hour=5, minute=30),
    },
    "weekly-marketing-discovery": {
        "task": "app.workers.tasks.discover_marketing_opportunities_for_all_products",
        "schedule": crontab(day_of_week=3, hour=6, minute=0),
    },
    # §2-22 Autonomous Daily Content & Promotion Engine — bounded (MAX_DAILY_
    # CONTENT_ITEMS, MAX_DAILY_VIDEOS), default human-approval-required
    # before anything publishes (§19).
    "daily-content-planning": {
        "task": "app.workers.tasks.plan_and_generate_daily_content",
        "schedule": crontab(hour=8, minute=0),
    },
    "daily-video-generation": {
        "task": "app.workers.tasks.generate_daily_videos",
        "schedule": crontab(hour=8, minute=30),  # after planning, so READY variants exist to attach to
    },
    "content-quality-sweep": {
        "task": "app.workers.tasks.run_content_quality_scan",
        "schedule": crontab(minute=0),  # hourly
    },
    "publish-due-content": {
        "task": "app.workers.tasks.publish_due_content",
        "schedule": crontab(minute="*/15"),
    },
    "weekly-content-learning": {
        "task": "app.workers.tasks.run_content_learning",
        "schedule": crontab(day_of_week=5, hour=6, minute=0),
    },
    "daily-video-cleanup": {
        "task": "app.workers.tasks.cleanup_old_videos_task",
        "schedule": crontab(hour=4, minute=0),
    },
}

celery_app.autodiscover_tasks(["app.workers"])
