import threading
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.content_pipeline import get_brand, get_truth
from app.agents.video_pipeline import (
    create_pending_video,
    get_or_create_brand_kit,
    mark_stale_renders_failed,
    maybe_cleanup_old_videos,
    render_video_into_row,
)
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import OrgRole
from app.db.models.video import Video
from app.db.session import SessionLocal, get_db
from app.providers.storage.factory import get_storage_provider
from app.schemas.video import VideoBrandKitResponse, VideoGenerateRequest, VideoResponse

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["videos"])

_MAX_SCREENSHOT_BYTES = 8 * 1024 * 1024
_ALLOWED_SCREENSHOT_TYPES = {"image/png", "image/jpeg", "image/webp"}


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


@router.get("/videos/brand-kit", response_model=VideoBrandKitResponse)
def get_video_brand_kit(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
):
    return get_or_create_brand_kit(db, workspace_id=ctx.workspace_id, product_id=product_id)


@router.post("/videos/brand-kit/screenshot", response_model=VideoBrandKitResponse)
async def upload_product_screenshot(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
):
    """A founder-supplied screenshot of the real product — composited into
    a premium browser-window mockup for the product/solution video scenes
    (scene_renderer.py). The reliable, always-accurate source of "real"
    visual content, unlike AI generation (paid, currently quota-exhausted)
    or web image search (tried and rejected — too unreliable/irrelevant
    for a product marketing video; see app/providers/image/factory.py)."""
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_SCREENSHOT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {content_type}. Use PNG, JPEG, or WebP.")

    data = await file.read(_MAX_SCREENSHOT_BYTES + 1)
    if len(data) > _MAX_SCREENSHOT_BYTES:
        raise HTTPException(status_code=400, detail="Screenshot must be under 8 MB")
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")

    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[content_type]
    storage = get_storage_provider()
    upload = storage.upload(path=f"screenshots/{ctx.workspace_id}/{product_id}.{extension}", data=data, content_type=content_type)
    if not upload.success:
        raise HTTPException(status_code=502, detail=f"Could not store screenshot: {upload.error}")

    kit = get_or_create_brand_kit(db, workspace_id=ctx.workspace_id, product_id=product_id)
    kit.product_screenshot_url = upload.url
    db.commit()
    db.refresh(kit)
    return kit


@router.get("/videos", response_model=list[VideoResponse])
def list_videos(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    mark_stale_renders_failed(db, workspace_id=ctx.workspace_id)
    maybe_cleanup_old_videos(db)
    return db.execute(select(Video).where(Video.workspace_id == ctx.workspace_id).order_by(Video.created_at.desc())).scalars().all()


@router.get("/videos/{video_id}", response_model=VideoResponse)
def get_video(video_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    video = db.get(Video, video_id)
    if video is None or video.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Video not found")
    if video.status.value == "rendering":
        mark_stale_renders_failed(db, workspace_id=ctx.workspace_id)
        db.refresh(video)
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
