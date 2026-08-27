import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.investor_agent import InvestorAgent
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.enums import OrgRole
from app.db.models.investor import Investor, InvestorInteraction, InvestorMatch
from app.db.models.product import Product
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.schemas.investor import (
    InvestorCreateRequest,
    InvestorInteractionResponse,
    InvestorInteractionUpdateRequest,
    InvestorMatchRequest,
    InvestorMatchResponse,
    InvestorResponse,
)

router = APIRouter(tags=["investors"])


@router.get("/investors", response_model=list[InvestorResponse])
def list_investors(db: Annotated[Session, Depends(get_db)], sector: str | None = None):
    stmt = select(Investor)
    rows = db.execute(stmt).scalars().all()
    if sector:
        rows = [r for r in rows if sector.lower() in [s.lower() for s in r.sector]]
    return rows


@router.post("/investors", response_model=InvestorResponse, status_code=201)
def create_investor(payload: InvestorCreateRequest, db: Annotated[Session, Depends(get_db)]):
    investor = Investor(**payload.model_dump())
    db.add(investor)
    db.commit()
    db.refresh(investor)
    return investor


@router.post("/workspaces/{workspace_id}/products/{product_id}/investor-matches", response_model=list[InvestorMatchResponse])
def compute_investor_matches(
    product_id: uuid.UUID,
    payload: InvestorMatchRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    product = db.get(Product, product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")

    agent = InvestorAgent(db, get_ai_provider())
    investors = db.execute(select(Investor)).scalars().all()
    matches = []
    for investor in investors:
        result = agent.match(product=product, stage=payload.stage, investor=investor)
        if result["fit_score"] < 40:
            continue
        match = InvestorMatch(
            workspace_id=ctx.workspace_id,
            product_id=product_id,
            investor_id=investor.id,
            fit_score=result["fit_score"],
            reasons=result["reasons"],
            factors=result["factors"],
        )
        db.add(match)
        matches.append(match)
    db.commit()
    for m in matches:
        db.refresh(m)
    matches.sort(key=lambda m: m.fit_score, reverse=True)
    return matches


@router.get("/workspaces/{workspace_id}/products/{product_id}/investor-matches", response_model=list[InvestorMatchResponse])
def list_investor_matches(
    product_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
):
    return db.execute(
        select(InvestorMatch)
        .where(InvestorMatch.workspace_id == ctx.workspace_id, InvestorMatch.product_id == product_id)
        .order_by(InvestorMatch.fit_score.desc())
    ).scalars().all()


@router.get("/workspaces/{workspace_id}/investor-pipeline", response_model=list[InvestorInteractionResponse])
def list_investor_pipeline(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(InvestorInteraction).where(InvestorInteraction.workspace_id == ctx.workspace_id)).scalars().all()


@router.post("/workspaces/{workspace_id}/investors/{investor_id}/pipeline", response_model=InvestorInteractionResponse, status_code=201)
def upsert_pipeline_entry(
    investor_id: uuid.UUID,
    product_id: uuid.UUID,
    payload: InvestorInteractionUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    entry = db.execute(
        select(InvestorInteraction).where(
            InvestorInteraction.workspace_id == ctx.workspace_id,
            InvestorInteraction.investor_id == investor_id,
            InvestorInteraction.product_id == product_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        entry = InvestorInteraction(workspace_id=ctx.workspace_id, investor_id=investor_id, product_id=product_id)
        db.add(entry)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    if payload.notes is not None or payload.stage is not None:
        entry.last_contact_at = dt.datetime.now(dt.timezone.utc)

    db.commit()
    db.refresh(entry)
    return entry
