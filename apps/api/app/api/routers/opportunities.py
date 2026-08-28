import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.marketing_discovery_agent import MarketingDiscoveryAgent
from app.agents.scoring import score_opportunity
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.enums import OpportunityType, OrgRole
from app.db.models.opportunity import Opportunity, OpportunityScore
from app.db.models.product import Product, ProductProfile
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.search.factory import get_search_provider
from app.schemas.opportunity import (
    OpportunityCreateRequest,
    OpportunityResponse,
    OpportunityScoreRequest,
    OpportunityScoreResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityResponse])
def list_opportunities(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    type: OpportunityType | None = None,
    status: str | None = None,
):
    stmt = select(Opportunity).where(Opportunity.workspace_id == ctx.workspace_id)
    if type:
        stmt = stmt.where(Opportunity.type == type)
    if status:
        stmt = stmt.where(Opportunity.status == status)
    return db.execute(stmt.order_by(Opportunity.created_at.desc())).scalars().all()


@router.post("", response_model=OpportunityResponse, status_code=201)
def create_opportunity(
    payload: OpportunityCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    opp = Opportunity(workspace_id=ctx.workspace_id, **payload.model_dump())
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


@router.patch("/{opportunity_id}/status", response_model=OpportunityResponse)
def update_status(
    opportunity_id: uuid.UUID,
    new_status: str,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    opp = db.get(Opportunity, opportunity_id)
    if opp is None or opp.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opp.status = new_status
    db.commit()
    db.refresh(opp)
    return opp


@router.post("/{opportunity_id}/score", response_model=OpportunityScoreResponse)
def score_opportunity_endpoint(
    opportunity_id: uuid.UUID,
    payload: OpportunityScoreRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    opp = db.get(Opportunity, opportunity_id)
    if opp is None or opp.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    factors = payload.model_dump()
    total = score_opportunity(factors)
    score = OpportunityScore(opportunity_id=opportunity_id, **factors, total_score=total, computed_at=dt.datetime.now(dt.timezone.utc))
    db.add(score)
    db.commit()
    db.refresh(score)
    return score


@router.post("/discover-marketing", response_model=list[OpportunityResponse])
def discover_marketing_opportunities(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
):
    """Autonomous marketing opportunity discovery (§25) — communities,
    newsletters, podcasts, launch platforms — no query required."""
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")
    profile = db.execute(
        select(ProductProfile).where(ProductProfile.product_id == product_id).order_by(ProductProfile.created_at.desc())
    ).scalars().first()

    agent = MarketingDiscoveryAgent(db, get_ai_provider(), get_search_provider())
    discovered = agent.discover_opportunities(workspace_id=ctx.workspace_id, product=product, profile=profile)

    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="marketing_discovery_run", resource_type="product", resource_id=str(product_id),
        metadata={"discovered_count": len(discovered)},
    )
    db.commit()
    for opp in discovered:
        db.refresh(opp)
    return discovered
