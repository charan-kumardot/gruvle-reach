"""
Shared idea->script->render->upload pipeline used by the /videos router and
the daily-video Celery task.

Split into a fast, request-safe half (create_pending_video) and the actual
work (render_video_into_row) so the HTTP router can return immediately and
do the AI/FFmpeg/upload work in a background thread with its own DB
session — Render's free-tier CPU is slow enough for this chain that doing
it inline in the request routinely exceeded the platform's proxy timeout
and 502'd, even though the work itself was correct (observed live against
production). generate_video_for_idea composes both halves for callers that
are already off the request path (the Celery task) and can block safely.
"""
import datetime as dt
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.video_agent import VideoAgent, compose_scenes
from app.db.models.content import ContentVariant
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


STALE_RENDER_MINUTES = 5


def mark_stale_renders_failed(db: Session, *, workspace_id: uuid.UUID | None = None) -> int:
    """Safety net for a background render thread that never reaches a
    terminal state — observed live against Render's free tier, where the
    container can restart mid-render (deploy, OOM, the platform's own
    instance cycling) and silently kill the thread doing the work, leaving
    the row stuck at RENDERING forever with no error ever recorded. Called
    opportunistically from the GET /videos routes so a poller naturally
    self-heals a stuck row into an honest FAILED state instead of polling
    indefinitely against a row that will never change."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=STALE_RENDER_MINUTES)
    stmt = select(Video).where(Video.status == VideoStatus.RENDERING, Video.updated_at < cutoff)
    if workspace_id is not None:
        stmt = stmt.where(Video.workspace_id == workspace_id)
    stale = db.execute(stmt).scalars().all()
    for video in stale:
        video.status = VideoStatus.FAILED
        video.render_log = (
            f"Render did not complete within {STALE_RENDER_MINUTES} minutes — the server likely "
            "restarted mid-render. Try generating again."
        )
    if stale:
        db.commit()
    return len(stale)


VIDEO_RETENTION_DAYS = 30
_OPPORTUNISTIC_CLEANUP_INTERVAL = dt.timedelta(hours=6)
_last_opportunistic_cleanup: dt.datetime | None = None


def cleanup_old_videos(db: Session, *, older_than_days: int = VIDEO_RETENTION_DAYS) -> int:
    """Deletes both the DB row and its Supabase Storage object for any
    Video older than the retention window — generated videos are short-
    form review assets, not a long-term archive, and Storage isn't free
    past its tier's cap. Runs across all workspaces (a plain scheduled
    sweep, same shape as the other cleanup/discovery Celery tasks)."""
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=older_than_days)
    old_videos = db.execute(select(Video).where(Video.created_at < cutoff)).scalars().all()
    if not old_videos:
        return 0

    storage = get_storage_provider()
    for video in old_videos:
        if video.storage_url:
            storage.delete(path=f"videos/{video.id}.mp4")
        db.delete(video)
    db.commit()
    return len(old_videos)


def maybe_cleanup_old_videos(db: Session) -> int:
    """Opportunistic trigger for the same cleanup, called from the GET
    /videos routes — a plain scheduled Celery task also exists
    (app.workers.tasks.cleanup_old_videos_task) for when a worker service
    is available, but nothing schedules it today (see video_pipeline.py's
    module docstring / the commit that added mark_stale_renders_failed),
    so this keeps retention actually happening in the meantime. Throttled
    in-process so a busy Video Library doesn't run a delete sweep on every
    page load."""
    global _last_opportunistic_cleanup
    now = dt.datetime.now(dt.timezone.utc)
    if _last_opportunistic_cleanup is not None and now - _last_opportunistic_cleanup < _OPPORTUNISTIC_CLEANUP_INTERVAL:
        return 0
    _last_opportunistic_cleanup = now
    return cleanup_old_videos(db)


def create_pending_video(
    db: Session, *, workspace_id: uuid.UUID, product_id: uuid.UUID,
    content_variant_id: uuid.UUID | None, aspect_ratio: str,
) -> Video:
    """Fast, cheap insert only — no AI call, no rendering. Commits so the
    row is visible to a separate DB session (a background thread, or a
    client polling GET /videos/{id}) immediately."""
    video = Video(
        workspace_id=workspace_id, product_id=product_id, content_variant_id=content_variant_id,
        aspect_ratio=aspect_ratio, status=VideoStatus.RENDERING,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def render_video_into_row(
    db: Session, *, video_id: uuid.UUID, idea: str, brand: BrandBrain | None, truth: ProductTruth | None, cta_hint: str = "",
) -> None:
    """Does the actual AI script call + FFmpeg render + upload, updating
    the given (already-created) Video row in place at each stage so a
    poller sees it transition RENDERING -> READY/FAILED. Safe to call from
    a background thread with its own Session — never touches a session
    that might be closed by the caller's request lifecycle."""
    video = db.get(Video, video_id)
    if video is None:
        return

    agent = VideoAgent(db, get_ai_provider())
    script = agent.write_script(idea=idea, brand=brand, truth=truth, cta_hint=cta_hint)
    if script is None:
        video.status = VideoStatus.FAILED
        video.render_log = "AI script generation failed or returned an unparseable response"
        db.commit()
        return

    scenes = compose_scenes(script)
    video.script = script
    if not scenes:
        video.status = VideoStatus.FAILED
        video.render_log = "Generated script had no usable scenes"
        db.commit()
        return

    kit = get_or_create_brand_kit(db, workspace_id=video.workspace_id, product_id=video.product_id)
    video.brand_kit_snapshot = {
        "primary_color": kit.primary_color, "secondary_color": kit.secondary_color,
        "background_color": kit.background_color, "text_color": kit.text_color, "font_family": kit.font_family,
    }
    db.commit()

    video_provider = get_video_provider()
    render = video_provider.render(scenes, brand_kit=kit, aspect_ratio=video.aspect_ratio)

    if not render.success:
        video.status = VideoStatus.FAILED
        video.render_log = (render.error + "\n" + render.render_log)[:4000]
        db.commit()
        return

    storage = get_storage_provider()
    data = Path(render.local_path).read_bytes()
    upload = storage.upload(path=f"videos/{video.id}.mp4", data=data, content_type="video/mp4")
    if render.workdir:
        shutil.rmtree(render.workdir, ignore_errors=True)

    if not upload.success:
        video.status = VideoStatus.FAILED
        video.render_log = (render.render_log + "\nUpload failed: " + upload.error)[:4000]
        db.commit()
        return

    video.status = VideoStatus.READY
    video.storage_url = upload.url
    video.duration_seconds = render.duration_seconds
    video.has_voiceover = render.has_voiceover
    video.render_log = render.render_log[:4000]
    video.rendered_at = dt.datetime.now(dt.timezone.utc)

    if video.content_variant_id is not None:
        variant = db.get(ContentVariant, video.content_variant_id)
        if variant is not None:
            variant.video_id = video.id
            variant.media_refs = [upload.url]

    db.commit()


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
) -> Video:
    """Synchronous convenience wrapper (create + render in one call) for
    callers already off the HTTP request path — currently the daily-video
    Celery task, which can block safely. The HTTP router uses
    create_pending_video + render_video_into_row directly so it can return
    before the render finishes (see module docstring)."""
    video = create_pending_video(
        db, workspace_id=workspace_id, product_id=product_id,
        content_variant_id=content_variant_id, aspect_ratio=aspect_ratio,
    )
    render_video_into_row(db, video_id=video.id, idea=idea, brand=brand, truth=truth, cta_hint=cta_hint)
    db.refresh(video)
    return video
