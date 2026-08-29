import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.research_agent import ResearchAgent
from app.agents.research_orchestrator import derive_queries, ensure_profile_and_icps
from app.agents.trigger_agent import TriggerAgent
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.company import Company, CompanySignal, CompanyTrigger, Contact
from app.db.models.enums import OrgRole
from app.db.models.product import ICPProfile, Product
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.search.factory import get_search_provider
from app.schemas.company import (
    CompanyDiscoverRequest,
    CompanyResponse,
    CompanyUpdateRequest,
    ContactCreateRequest,
    ContactResponse,
    TriggerResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/companies", tags=["companies"])


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID | None = None,
    min_score: float = 0,
):
    stmt = select(Company).where(Company.workspace_id == ctx.workspace_id, Company.icp_fit_score >= min_score)
    if product_id:
        stmt = stmt.where(Company.product_id == product_id)
    return db.execute(stmt.order_by(Company.icp_fit_score.desc())).scalars().all()


@router.post("/discover", response_model=list[CompanyResponse])
def discover_companies(
    payload: CompanyDiscoverRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
):
    queries = list(payload.queries)
    if payload.icp_id:
        icp = db.get(ICPProfile, payload.icp_id)
        if icp and icp.product_id == product_id:
            criteria = icp.criteria or {}
            industries = criteria.get("industries", [])
            tech = criteria.get("technology_stack", [])
            queries.append(f"{' '.join(industries[:2])} companies using {' '.join(tech[:2])}".strip())

    if not queries:
        raise HTTPException(status_code=400, detail="Provide at least one search query or a valid icp_id")

    agent = ResearchAgent(db, get_ai_provider(), get_search_provider())
    companies = agent.discover_companies(
        workspace_id=ctx.workspace_id,
        product_id=product_id,
        queries=queries,
        max_results_per_query=payload.max_results_per_query,
    )

    trigger_agent = TriggerAgent(db)
    for company in companies:
        signals = db.execute(select(CompanySignal).where(CompanySignal.company_id == company.id)).scalars().all()
        trigger_agent.detect_triggers(company, signals)

    db.commit()
    for c in companies:
        db.refresh(c)
    return companies


@router.post("/discover-auto", response_model=list[CompanyResponse])
def discover_companies_auto(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
):
    """Zero-input company discovery (§6, §8, §22) — no query required.
    Ensures product understanding + ICPs exist, derives a broad set of
    queries from them (spanning industries and company-size tiers), and
    runs the same ResearchAgent pipeline as the manual /discover route.
    Safe to call repeatedly — discovery already dedupes by URL and by
    recent evidence, so re-running only adds new companies."""
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")

    ai_provider = get_ai_provider()
    profile, icps = ensure_profile_and_icps(db, product=product, ai_provider=ai_provider)
    queries = derive_queries(product, profile, icps)
    if not queries:
        raise HTTPException(status_code=503, detail="Could not derive any research queries — AI provider may be unavailable")

    agent = ResearchAgent(db, ai_provider, get_search_provider())
    companies = agent.discover_companies(workspace_id=ctx.workspace_id, product_id=product_id, queries=queries)

    trigger_agent = TriggerAgent(db)
    for company in companies:
        signals = db.execute(select(CompanySignal).where(CompanySignal.company_id == company.id)).scalars().all()
        trigger_agent.detect_triggers(company, signals)

    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="company_discovery_run", resource_type="product", resource_id=str(product_id),
        metadata={"discovered_count": len(companies), "queries_used": len(queries)},
    )

    db.commit()
    for c in companies:
        db.refresh(c)
    return companies


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    company = db.get(Company, company_id)
    if company is None or company.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    company = db.get(Company, company_id)
    if company is None or company.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}", status_code=204)
def delete_company(
    company_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    company = db.get(Company, company_id)
    if company is None or company.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Company not found")
    db.delete(company)
    db.commit()


@router.get("/{company_id}/triggers", response_model=list[TriggerResponse])
def list_triggers(company_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    company = db.get(Company, company_id)
    if company is None or company.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Company not found")
    return db.execute(select(CompanyTrigger).where(CompanyTrigger.company_id == company_id).order_by(CompanyTrigger.relevance_score.desc())).scalars().all()


@router.get("/{company_id}/contacts", response_model=list[ContactResponse])
def list_contacts(company_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    company = db.get(Company, company_id)
    if company is None or company.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Company not found")
    return db.execute(select(Contact).where(Contact.company_id == company_id)).scalars().all()


@router.post("/{company_id}/contacts", response_model=ContactResponse, status_code=201)
def create_contact(
    company_id: uuid.UUID,
    payload: ContactCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    company = db.get(Company, company_id)
    if company is None or company.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Company not found")
    contact = Contact(workspace_id=ctx.workspace_id, company_id=company_id, **payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact
