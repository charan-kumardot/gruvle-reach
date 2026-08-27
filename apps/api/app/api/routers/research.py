import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.enums import OrgRole
from app.db.models.research import Evidence, ResearchSource
from app.db.session import get_db
from app.schemas.research import EvidenceResponse, ResearchSourceCreateRequest, ResearchSourceResponse

router = APIRouter(prefix="/workspaces/{workspace_id}/research", tags=["research"])


@router.get("/sources", response_model=list[ResearchSourceResponse])
def list_sources(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(ResearchSource).where(ResearchSource.workspace_id == ctx.workspace_id)).scalars().all()


@router.post("/sources", response_model=ResearchSourceResponse, status_code=201)
def add_source(
    payload: ResearchSourceCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    source = ResearchSource(workspace_id=ctx.workspace_id, added_by=ctx.user.id, **payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    source = db.get(ResearchSource, source_id)
    if source is None or source.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Research source not found")
    db.delete(source)
    db.commit()


@router.get("/evidence", response_model=list[EvidenceResponse])
def list_evidence(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
):
    stmt = select(Evidence).where(Evidence.workspace_id == ctx.workspace_id)
    if related_entity_type:
        stmt = stmt.where(Evidence.related_entity_type == related_entity_type)
    if related_entity_id:
        stmt = stmt.where(Evidence.related_entity_id == related_entity_id)
    return db.execute(stmt.order_by(Evidence.created_at.desc())).scalars().all()
