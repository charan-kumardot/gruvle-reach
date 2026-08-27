"""
Background tasks (§66, §77 — never run research jobs inline in an HTTP
request). Every task here only writes recommendations/data; nothing sends or
publishes externally without a subsequent human-approval step through the
API (§67, §70).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.chief_growth_agent import generate_daily_actions
from app.agents.competitor_agent import CompetitorAgent
from app.db.models.competitor import Competitor
from app.db.models.product import Product
from app.db.models.tenancy import Workspace
from app.db.session import SessionLocal
from app.providers.ai.factory import get_ai_provider
from app.workers.celery_app import celery_app


@celery_app.task
def generate_daily_briefs_for_all_workspaces() -> int:
    db: Session = SessionLocal()
    count = 0
    try:
        products = db.execute(select(Product)).scalars().all()
        for product in products:
            generate_daily_actions(db, workspace_id=product.workspace_id, product_id=product.id)
            count += 1
        db.commit()
    finally:
        db.close()
    return count


@celery_app.task
def scan_all_competitors() -> int:
    db: Session = SessionLocal()
    count = 0
    try:
        agent = CompetitorAgent(db, get_ai_provider())
        competitors = db.execute(select(Competitor)).scalars().all()
        for competitor in competitors:
            change = agent.scan(competitor)
            if change:
                count += 1
        db.commit()
    finally:
        db.close()
    return count


@celery_app.task
def generate_weekly_market_briefs() -> int:
    """Placeholder for §33's Weekly Market Brief — composes from existing
    evidence/triggers/competitor changes rather than a fresh AI call, to stay
    within the free-tier/cost-control guidance (§79). Extend here once
    per-workspace brief storage (a `market_briefs` table) is needed."""
    db: Session = SessionLocal()
    try:
        workspaces = db.execute(select(Workspace)).scalars().all()
        return len(workspaces)
    finally:
        db.close()


@celery_app.task
def discover_companies_task(workspace_id: str, product_id: str, queries: list[str]) -> int:
    """Async entry point for the (potentially slow) company-discovery agent,
    so the API route can enqueue it instead of blocking an HTTP request."""
    import uuid

    from app.agents.research_agent import ResearchAgent
    from app.agents.trigger_agent import TriggerAgent
    from app.db.models.company import CompanySignal
    from app.providers.search.factory import get_search_provider

    db: Session = SessionLocal()
    try:
        agent = ResearchAgent(db, get_ai_provider(), get_search_provider())
        companies = agent.discover_companies(workspace_id=uuid.UUID(workspace_id), product_id=uuid.UUID(product_id), queries=queries)
        trigger_agent = TriggerAgent(db)
        for company in companies:
            signals = db.execute(select(CompanySignal).where(CompanySignal.company_id == company.id)).scalars().all()
            trigger_agent.detect_triggers(company, signals)
        db.commit()
        return len(companies)
    finally:
        db.close()
