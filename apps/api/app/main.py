import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers import (
    actions,
    analytics,
    auth,
    brand,
    campaigns,
    companies,
    competitors,
    content,
    cron,
    growth,
    integrations,
    investors,
    opportunities,
    orgs,
    outreach,
    products,
    research,
    settings as settings_router,
    visibility,
)
from app.core.config import get_settings

# Uncaught scheduled-job outcomes (see app/api/routers/cron.py) are logged at
# INFO — without a root config, they're silently swallowed since no handler
# is attached by default, which would make Render's logs useless for
# confirming a cron trigger actually ran (see CLAUDE.md).
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()

app = FastAPI(
    title="Gruvle Reach API",
    description="Founder Growth OS — discovers customers, investors, and growth opportunities and turns them into an evidence-backed, human-approved action plan.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    auth.router,
    orgs.router,
    products.router,
    companies.router,
    investors.router,
    opportunities.router,
    campaigns.router,
    content.router,
    outreach.router,
    competitors.router,
    brand.router,
    research.router,
    growth.router,
    cron.router,
    actions.router,
    analytics.router,
    integrations.router,
    settings_router.router,
    visibility.router,
):
    app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    from sqlalchemy import text

    from app.db.session import engine

    checks = {"database": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001
        pass
    overall_ok = checks["database"]
    return {"status": "ok" if overall_ok else "degraded", "checks": checks}
