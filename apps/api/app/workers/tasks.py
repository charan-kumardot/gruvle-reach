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


@celery_app.task
def discover_customers_for_all_products() -> int:
    """§22 daily autonomous customer discovery — zero-input, derives its own
    queries per product via the research orchestrator."""
    from app.agents.research_orchestrator import run_autonomous_discovery
    from app.providers.search.factory import get_search_provider

    db: Session = SessionLocal()
    count = 0
    try:
        products = db.execute(select(Product)).scalars().all()
        ai_provider = get_ai_provider()
        search_provider = get_search_provider()
        for product in products:
            try:
                run_autonomous_discovery(
                    db, workspace_id=product.workspace_id, product=product,
                    ai_provider=ai_provider, search_provider=search_provider,
                )
                count += 1
            except Exception:  # noqa: BLE001 — one product's failure shouldn't stop the rest
                db.rollback()
                continue
        db.commit()
    finally:
        db.close()
    return count


@celery_app.task
def discover_investors_for_all_products() -> int:
    """§22 daily autonomous investor discovery."""
    from app.agents.investor_discovery_agent import InvestorDiscoveryAgent
    from app.db.models.product import ProductProfile
    from app.providers.search.factory import get_search_provider

    db: Session = SessionLocal()
    total = 0
    try:
        products = db.execute(select(Product)).scalars().all()
        ai_provider = get_ai_provider()
        search_provider = get_search_provider()
        for product in products:
            profile = db.execute(
                select(ProductProfile).where(ProductProfile.product_id == product.id).order_by(ProductProfile.created_at.desc())
            ).scalars().first()
            agent = InvestorDiscoveryAgent(db, ai_provider, search_provider)
            try:
                discovered = agent.discover_investors(workspace_id=product.workspace_id, product=product, profile=profile)
                total += len(discovered)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                continue
    finally:
        db.close()
    return total


@celery_app.task
def plan_and_generate_daily_content() -> int:
    """§2-4 daily content planning — zero-input, bounded (MAX_DAILY_CONTENT_ITEMS),
    mix-balanced. Reactive/competitive ideas land APPROVAL_REQUIRED and are
    never auto-scheduled (§5, §7)."""
    from app.agents.content_pipeline import generate_and_gate_variants, get_brand, get_truth
    from app.agents.content_strategy_agent import AUTONOMOUS_CHANNELS, plan_daily_content
    from app.db.models.content import Content
    from app.db.models.opportunity import Opportunity

    db: Session = SessionLocal()
    total = 0
    try:
        products = db.execute(select(Product)).scalars().all()
        for product in products:
            try:
                brand = get_brand(db, product.workspace_id, product.id)
                truth = get_truth(db, product.id)
                ideas = plan_daily_content(db, workspace_id=product.workspace_id, product_id=product.id, brand=brand)
                for idea in ideas:
                    content = Content(
                        workspace_id=product.workspace_id, product_id=product.id, idea=idea["idea"],
                        content_type=idea["content_type"], origin=idea["origin"],
                    )
                    db.add(content)
                    db.flush()
                    generate_and_gate_variants(
                        db, content=content, brand=brand, truth=truth,
                        channels=AUTONOMOUS_CHANNELS, cta_hint=idea["cta_hint"],
                    )
                    if idea.get("source_opportunity_id"):
                        opportunity = db.get(Opportunity, idea["source_opportunity_id"])
                        if opportunity is not None:
                            opportunity.status = "actioned"
                    total += 1
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                continue
    finally:
        db.close()
    return total


@celery_app.task
def run_content_quality_scan() -> int:
    """§28-29 hourly safety net — re-gates any DRAFT/READY variant still
    sitting there after a couple of hours, covering the regenerate/manual-
    idea paths that don't go through the daily planning task."""
    import datetime as dt

    from app.agents.content_pipeline import get_brand, get_truth
    from app.agents.content_quality_gate import run_quality_gate
    from app.db.models.content import Content, ContentVariant
    from app.db.models.enums import ContentStatus

    db: Session = SessionLocal()
    count = 0
    try:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
        rows = db.execute(
            select(ContentVariant, Content)
            .join(Content, Content.id == ContentVariant.content_id)
            .where(ContentVariant.status.in_([ContentStatus.DRAFT, ContentStatus.READY]), ContentVariant.created_at <= cutoff)
        ).all()
        for variant, content in rows:
            try:
                brand = get_brand(db, content.workspace_id, content.product_id)
                truth = get_truth(db, content.product_id)
                gate_result = run_quality_gate(db, variant=variant, content=content, brand=brand, truth=truth, ai_provider=get_ai_provider())
                variant.status = ContentStatus.READY if gate_result.passed else ContentStatus.FAILED
                variant.quality_flags = (
                    {"warnings": gate_result.warnings} if gate_result.passed else {"blocking_reasons": gate_result.blocking_reasons}
                )
                count += 1
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                continue
    finally:
        db.close()
    return count


@celery_app.task
def publish_due_content() -> int:
    """§18-20 — publishes SCHEDULED content whose scheduled_at has passed.
    A channel that isn't connected leaves the variant SCHEDULED and just
    logs it — never silently dropped; connecting the platform later still
    finds it queued."""
    import datetime as dt
    import logging

    from app.actions import content_executor
    from app.db.models.content import Content, ContentVariant
    from app.db.models.enums import ContentStatus, IntegrationStatus, OrgRole
    from app.db.models.integration import Integration
    from app.db.models.tenancy import Workspace
    from app.providers.social.factory import get_social_access_token_for_workspace, get_social_providers

    logger = logging.getLogger(__name__)
    db: Session = SessionLocal()
    count = 0
    try:
        now = dt.datetime.now(dt.timezone.utc)
        due = db.execute(
            select(ContentVariant, Content)
            .join(Content, Content.id == ContentVariant.content_id)
            .where(ContentVariant.status == ContentStatus.SCHEDULED, ContentVariant.scheduled_at <= now)
        ).all()
        social_providers = get_social_providers()
        for variant, content in due:
            try:
                integration = db.execute(
                    select(Integration).where(
                        Integration.workspace_id == content.workspace_id,
                        Integration.provider_name == variant.channel,
                        Integration.status == IntegrationStatus.CONNECTED,
                    )
                ).scalar_one_or_none()
                if integration is None:
                    logger.info("Scheduled content variant %s waiting — %s not connected", variant.id, variant.channel)
                    continue

                social_provider = social_providers.get(variant.channel)
                if social_provider is None:
                    continue
                access_token = get_social_access_token_for_workspace(db, content.workspace_id, variant.channel)
                workspace = db.get(Workspace, content.workspace_id)

                content_executor.publish_content_variant(
                    db, variant=variant, content=content, approver_role=OrgRole.OWNER, approver_id=integration.connected_by,
                    organization_id=workspace.organization_id, workspace_id=content.workspace_id,
                    social_provider=social_provider, access_token=access_token,
                )
                count += 1
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                continue
    finally:
        db.close()
    return count


@celery_app.task
def run_content_learning() -> int:
    """§22 weekly content-performance learning."""
    from app.agents.learning_agent import run_content_learning_analysis

    db: Session = SessionLocal()
    total = 0
    try:
        products = db.execute(select(Product)).scalars().all()
        for product in products:
            try:
                insights = run_content_learning_analysis(db, workspace_id=product.workspace_id, product_id=product.id)
                total += len(insights)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                continue
    finally:
        db.close()
    return total


@celery_app.task
def discover_marketing_opportunities_for_all_products() -> int:
    """§22 weekly autonomous marketing-opportunity discovery."""
    from app.agents.marketing_discovery_agent import MarketingDiscoveryAgent
    from app.db.models.product import ProductProfile
    from app.providers.search.factory import get_search_provider

    db: Session = SessionLocal()
    total = 0
    try:
        products = db.execute(select(Product)).scalars().all()
        ai_provider = get_ai_provider()
        search_provider = get_search_provider()
        for product in products:
            profile = db.execute(
                select(ProductProfile).where(ProductProfile.product_id == product.id).order_by(ProductProfile.created_at.desc())
            ).scalars().first()
            agent = MarketingDiscoveryAgent(db, ai_provider, search_provider)
            try:
                discovered = agent.discover_opportunities(workspace_id=product.workspace_id, product=product, profile=profile)
                total += len(discovered)
                db.commit()
            except Exception:  # noqa: BLE001
                db.rollback()
                continue
    finally:
        db.close()
    return total
