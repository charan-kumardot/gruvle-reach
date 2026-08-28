import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.content_pipeline import get_brand, get_truth
from app.agents.video_pipeline import generate_video_for_idea
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import OrgRole
from app.db.models.video import Video
from app.db.session import get_db
from app.schemas.video import VideoGenerateRequest, VideoResponse

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["videos"])


@router.get("/videos", response_model=list[VideoResponse])
def list_videos(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(Video).where(Video.workspace_id == ctx.workspace_id).order_by(Video.created_at.desc())).scalars().all()


@router.get("/videos/{video_id}", response_model=VideoResponse)
def get_video(video_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    video = db.get(Video, video_id)
    if video is None or video.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/videos/generate", response_model=VideoResponse)
def generate_video(
    payload: VideoGenerateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    variant: ContentVariant | None = None
    idea = payload.idea
    product_id = payload.product_id
    cta_hint = ""

    if payload.content_variant_id:
        variant = db.get(ContentVariant, payload.content_variant_id)
        if variant is None:
            raise HTTPException(status_code=404, detail="Content variant not found")
        content = db.get(Content, variant.content_id)
        if content is None or content.workspace_id != ctx.workspace_id:
            raise HTTPException(status_code=404, detail="Content variant not found")
        idea = content.idea
        product_id = content.product_id
        cta_hint = variant.cta

    if not idea or not product_id:
        raise HTTPException(status_code=400, detail="Provide either content_variant_id or both idea and product_id")

    brand = get_brand(db, ctx.workspace_id, product_id)
    truth = get_truth(db, product_id)

    video = generate_video_for_idea(
        db, workspace_id=ctx.workspace_id, product_id=product_id, idea=idea, brand=brand, truth=truth,
        cta_hint=cta_hint, content_variant_id=variant.id if variant else None, aspect_ratio=payload.aspect_ratio,
    )
    if video is None:
        raise HTTPException(status_code=503, detail="AI provider unavailable or returned an unparseable response.")

    if variant is not None and video.storage_url:
        variant.video_id = video.id
        variant.media_refs = [video.storage_url]

    db.commit()
    db.refresh(video)
    return video
