"""
Research Orchestrator (§6, §8) — the founder does not type a search query.
This chains what already exists: ProductUnderstandingAgent ->
ICPAgent -> the search_queries the ICP agent already generates ->
ResearchAgent.discover_companies -> TriggerAgent, tracked as one
ResearchRun row (a model that already existed but was never wired to
anything real until now).
"""
import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.icp_agent import ICPAgent
from app.agents.product_understanding_agent import ProductUnderstandingAgent
from app.agents.research_agent import ResearchAgent
from app.agents.trigger_agent import TriggerAgent
from app.db.models.company import Company, CompanySignal
from app.db.models.enums import ICPStatus
from app.db.models.product import ICPProfile, Product, ProductProfile
from app.db.models.research import ResearchRun
from app.providers.ai.base import AIProvider
from app.providers.search.base import SearchProvider


# No geography is ever hardcoded here — queries stay global by default.
# Crossed with each ICP's industries to surface companies across the full
# size spectrum, not just whichever tier a generic query happens to favor.
_SIZE_TIERS = ["early-stage startups", "small and mid-sized businesses", "mid-market companies", "large enterprises"]

QUERY_CAP = 14


def derive_queries(product: Product, profile: ProductProfile | None, icps: list[ICPProfile]) -> list[str]:
    """Pure function over already-stored data — no AI call. The ICP agent
    already produces search_queries; the ICP criteria (industries + tech
    stack) give a second, more targeted set, crossed with company-size
    tiers so discovery isn't biased toward one size of company.
    De-duplicated, capped."""
    queries: list[str] = []

    if profile and profile.search_queries:
        queries.extend(profile.search_queries)

    for icp in icps:
        criteria = icp.criteria or {}
        industries = criteria.get("industries", [])
        tech = criteria.get("technology_stack", [])
        if not industries and not tech:
            continue
        industry_part = " ".join(industries[:2])
        tech_part = "using " + " ".join(tech[:2]) if tech else ""
        queries.append(" ".join(p for p in [industry_part, "companies", tech_part] if p).strip())
        for tier in _SIZE_TIERS:
            queries.append(" ".join(p for p in [tier, industry_part, "companies", tech_part] if p).strip())

    if product.category:
        for tier in _SIZE_TIERS:
            queries.append(f"{tier} in {product.category} {' '.join(product.target_markets[:2])}".strip())

    if not queries and product.category:
        queries.append(f"{product.category} companies {' '.join(product.target_markets[:2])}".strip())

    seen: set[str] = set()
    deduped = []
    for q in queries:
        q = q.strip()
        if q and q.lower() not in seen:
            seen.add(q.lower())
            deduped.append(q)
    return deduped[:QUERY_CAP]


def ensure_profile_and_icps(
    db: Session, *, product: Product, ai_provider: AIProvider
) -> tuple[ProductProfile | None, list[ICPProfile]]:
    """Ensure a ProductProfile and at least one ICPProfile exist for
    `product`, generating them via AI if missing. Reuses existing
    profile/ICP rows if already present rather than re-generating (also
    research-memory-friendly). Shared by the autonomous discovery pipeline
    and the zero-input "Discover companies" API route."""
    profile = db.execute(
        select(ProductProfile).where(ProductProfile.product_id == product.id).order_by(ProductProfile.created_at.desc())
    ).scalars().first()
    if profile is None:
        profile_output = ProductUnderstandingAgent(db, ai_provider).run(product)
        if profile_output:
            profile = ProductProfile(
                product_id=product.id,
                product_category=profile_output.get("product_category", ""),
                primary_problem=profile_output.get("primary_problem", ""),
                primary_buyer=profile_output.get("primary_buyer", ""),
                secondary_buyers=profile_output.get("secondary_buyers", []),
                target_industries=profile_output.get("target_industries", []),
                use_cases=profile_output.get("use_cases", []),
                competitive_categories=profile_output.get("competitive_categories", []),
                keywords=profile_output.get("keywords", []),
                search_queries=profile_output.get("search_queries", []),
                raw_ai_output=profile_output,
            )
            db.add(profile)
            db.flush()

    icps = db.execute(select(ICPProfile).where(ICPProfile.product_id == product.id)).scalars().all()
    if not icps:
        icp_output = ICPAgent(db, ai_provider).run(product, profile)
        if icp_output and icp_output.get("icps"):
            for icp_data in icp_output["icps"]:
                icp = ICPProfile(
                    product_id=product.id, name=icp_data.get("name", "Untitled ICP"),
                    criteria=icp_data.get("criteria", {}), score=float(icp_data.get("score", 0)),
                    factors=icp_data.get("factors", {}), status=ICPStatus.AI_HYPOTHESIS, created_by="ai",
                )
                db.add(icp)
                icps.append(icp)
            db.flush()

    return profile, icps


def run_autonomous_discovery(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    product: Product,
    ai_provider: AIProvider,
    search_provider: SearchProvider,
    max_results_per_query: int = 15,
) -> ResearchRun:
    """Zero-input pipeline: ensure product understanding exists -> ensure at
    least one ICP exists -> derive queries from them -> discover companies
    -> detect triggers."""
    run = ResearchRun(
        workspace_id=workspace_id, product_id=product.id, run_type="autonomous_discovery",
        status="running", query="", started_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(run)
    db.flush()

    try:
        profile, icps = ensure_profile_and_icps(db, product=product, ai_provider=ai_provider)
        queries = derive_queries(product, profile, icps)
        if not queries:
            run.status = "failed"
            run.error = "Could not derive any research queries — AI provider may be unavailable"
            run.completed_at = dt.datetime.now(dt.timezone.utc)
            db.flush()
            return run

        research_agent = ResearchAgent(db, ai_provider, search_provider)
        companies = research_agent.discover_companies(
            workspace_id=workspace_id, product_id=product.id, queries=queries,
            max_results_per_query=max_results_per_query,
        )

        trigger_agent = TriggerAgent(db)
        trigger_count = 0
        for company in companies:
            signals = db.execute(select(CompanySignal).where(CompanySignal.company_id == company.id)).scalars().all()
            trigger_count += len(trigger_agent.detect_triggers(company, signals))

        run.status = "completed"
        run.query = "; ".join(queries)
        run.result_summary = {
            "queries_used": queries,
            "companies_discovered": len(companies),
            "triggers_detected": trigger_count,
            "icp_count": len(icps),
        }
        run.completed_at = dt.datetime.now(dt.timezone.utc)
        db.flush()
        return run

    except Exception as exc:  # noqa: BLE001 — always leave a clean, inspectable run record
        run.status = "failed"
        run.error = str(exc)[:2000]
        run.completed_at = dt.datetime.now(dt.timezone.utc)
        db.flush()
        raise
