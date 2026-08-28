"""
Shared idea->script->render->upload pipeline used by the /videos router and
the daily-video Celery task — factored out so the task doesn't duplicate
the router's rendering logic.
"""
import datetime as dt
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.video_agent import VideoAgent, compose_scenes
from app.db.models.enums import VideoStatus
from app.db.models.product import BrandBrain
from app.db.models.video import Video, VideoBrandKit
from app.db.models.visibility import ProductTruth
from app.providers.ai.factory import get_ai_provider
from app.providers.storage.factory import get_storage_provider
from app.providers.video.factory import get_video_provider


def get_or_create_brand_kit(db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID) -> VideoBrandKit:
    kit = db.execute(
        select(VideoBrandKit).where(VideoBrandKit.workspace_id == workspace_id, VideoBrandKit.product_id == product_id)
    ).scalars().first()
    if kit is None:
        kit = VideoBrandKit(workspace_id=workspace_id, product_id=product_id)
        db.add(kit)
        db.flush()
    return kit


def generate_video_for_idea(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    product_id: uuid.UUID,
    idea: str,
    brand: BrandBrain | None,
    truth: ProductTruth | None,
    cta_hint: str = "",
    content_variant_id: uuid.UUID | None = None,
    aspect_ratio: str = "9:16",
) -> Video | None:
    """Returns a Video row (status READY or FAILED) or None if script
    generation itself failed (AI unavailable) — a None return means "try
    again later," a FAILED row means "rendering was attempted and failed,"
    kept distinct so the caller/UI can tell them apart."""
    agent = VideoAgent(db, get_ai_provider())
    script = agent.write_script(idea=idea, brand=brand, truth=truth, cta_hint=cta_hint)
    if script is None:
        return None

    scenes = compose_scenes(script)
    if not scenes:
        return None

    kit = get_or_create_brand_kit(db, workspace_id=workspace_id, product_id=product_id)

    video = Video(
        workspace_id=workspace_id, product_id=product_id, content_variant_id=content_variant_id,
        script=script, aspect_ratio=aspect_ratio, status=VideoStatus.RENDERING,
        brand_kit_snapshot={
            "primary_color": kit.primary_color, "secondary_color": kit.secondary_color,
            "background_color": kit.background_color, "text_color": kit.text_color, "font_family": kit.font_family,
        },
    )
    db.add(video)
    db.flush()

    video_provider = get_video_provider()
    render = video_provider.render(scenes, brand_kit=kit, aspect_ratio=aspect_ratio)

    if not render.success:
        video.status = VideoStatus.FAILED
        video.render_log = (render.error + "\n" + render.render_log)[:4000]
        db.flush()
        return video

    storage = get_storage_provider()
    data = Path(render.local_path).read_bytes()
    upload = storage.upload(path=f"videos/{video.id}.mp4", data=data, content_type="video/mp4")
    if render.workdir:
        shutil.rmtree(render.workdir, ignore_errors=True)

    if not upload.success:
        video.status = VideoStatus.FAILED
        video.render_log = (render.render_log + "\nUpload failed: " + upload.error)[:4000]
        db.flush()
        return video

    video.status = VideoStatus.READY
    video.storage_url = upload.url
    video.duration_seconds = render.duration_seconds
    video.has_voiceover = render.has_voiceover
    video.render_log = render.render_log[:4000]
    video.rendered_at = dt.datetime.now(dt.timezone.utc)
    db.flush()
    return video
