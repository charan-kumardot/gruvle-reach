import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.competitor_agent import CompetitorAgent
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.competitor import Competitor, CompetitorChange
from app.db.models.enums import OrgRole
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.schemas.competitor import CompetitorChangeResponse, CompetitorCreateRequest, CompetitorResponse

router = APIRouter(prefix="/workspaces/{workspace_id}/competitors", tags=["competitors"])


@router.get("", response_model=list[CompetitorResponse])
def list_competitors(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(Competitor).where(Competitor.workspace_id == ctx.workspace_id)).scalars().all()


@router.post("", response_model=CompetitorResponse, status_code=201)
def create_competitor(
    payload: CompetitorCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    competitor = Competitor(workspace_id=ctx.workspace_id, **payload.model_dump())
    db.add(competitor)
    db.commit()
    db.refresh(competitor)
    return competitor


@router.post("/{competitor_id}/scan", response_model=CompetitorChangeResponse | None)
def scan_competitor(
    competitor_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    competitor = db.get(Competitor, competitor_id)
    if competitor is None or competitor.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Competitor not found")

    agent = CompetitorAgent(db, get_ai_provider())
    change = agent.scan(competitor)
    db.commit()
    if change:
        db.refresh(change)
    return change


@router.get("/{competitor_id}/changes", response_model=list[CompetitorChangeResponse])
def list_changes(competitor_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    competitor = db.get(Competitor, competitor_id)
    if competitor is None or competitor.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return db.execute(select(CompetitorChange).where(CompetitorChange.competitor_id == competitor_id).order_by(CompetitorChange.detected_at.desc())).scalars().all()
