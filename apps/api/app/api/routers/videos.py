import threading
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.content_pipeline import get_brand, get_truth
from app.agents.video_pipeline import create_pending_video, render_video_into_row
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import OrgRole
from app.db.models.video import Video
from app.db.session import SessionLocal, get_db
from app.schemas.video import VideoGenerateRequest, VideoResponse

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["videos"])


def _render_in_background(*, video_id: uuid.UUID, idea: str, workspace_id: uuid.UUID, product_id: uuid.UUID, cta_hint: str) -> None:
    """Runs off the request thread with its own DB session — Render's
    free-tier CPU makes the AI+FFmpeg+upload chain slow enough that doing
    it inline in the request routinely exceeded the platform's proxy
    timeout (observed live against production), even though the work
    itself completes correctly. The route returns a RENDERING row
    immediately; the frontend polls GET /videos/{id} (or the Video Library
    list, which already polls while any row is RENDERING)."""
    db = SessionLocal()
    try:
        brand = get_brand(db, workspace_id, product_id)
        truth = get_truth(db, product_id)
        render_video_into_row(db, video_id=video_id, idea=idea, brand=brand, truth=truth, cta_hint=cta_hint)
    finally:
        db.close()


@router.get("/videos", response_model=list[VideoResponse])
def list_videos(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(Video).where(Video.workspace_id == ctx.workspace_id).order_by(Video.created_at.desc())).scalars().all()


@router.get("/videos/{video_id}", response_model=VideoResponse)
def get_video(video_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    video = db.get(Video, video_id)
    if video is None or video.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@router.post("/videos/generate", response_model=VideoResponse, status_code=202)
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

    # Fast, synchronous part only — the row is created and committed so a
    # poller can see it immediately; the AI script call, FFmpeg render, and
    # storage upload all happen in the background thread below.
    video = create_pending_video(
        db, workspace_id=ctx.workspace_id, product_id=product_id,
        content_variant_id=variant.id if variant else None, aspect_ratio=payload.aspect_ratio,
    )

    thread = threading.Thread(
        target=_render_in_background,
        kwargs={"video_id": video.id, "idea": idea, "workspace_id": ctx.workspace_id, "product_id": product_id, "cta_hint": cta_hint},
        daemon=True,
    )
    thread.start()

    return video
