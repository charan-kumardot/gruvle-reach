from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.brand_agent import BrandAgent
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.brand import BrandMention
from app.db.models.enums import OrgRole
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.search.factory import get_search_provider
from app.schemas.brand import BrandMentionResponse, BrandScanRequest

router = APIRouter(prefix="/workspaces/{workspace_id}/brand", tags=["brand"])


@router.get("/mentions", response_model=list[BrandMentionResponse])
def list_mentions(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(
        select(BrandMention).where(BrandMention.workspace_id == ctx.workspace_id).order_by(BrandMention.relevance_score.desc())
    ).scalars().all()


@router.post("/scan", response_model=list[BrandMentionResponse])
def scan_brand_mentions(
    payload: BrandScanRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    agent = BrandAgent(db, get_ai_provider(), get_search_provider())
    mentions = agent.scan_mentions(workspace_id=ctx.workspace_id, product_id=payload.product_id, keywords=payload.keywords)
    db.commit()
    for m in mentions:
        db.refresh(m)
    return mentions
