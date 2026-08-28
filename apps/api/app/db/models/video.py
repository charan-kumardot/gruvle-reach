import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import VideoStatus


class VideoBrandKit(Base, UUIDPKMixin, TimestampMixin):
    """Deterministic rendering inputs for the template video pipeline.
    Ships with built-in defaults so video generation works with zero setup —
    distinct from the Visibility module's DesignConstitution, which stores
    free-text prose for an AI diff prompt, not hex codes/font paths."""

    __tablename__ = "video_brand_kits"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=True, index=True)
    primary_color: Mapped[str] = mapped_column(String(7), default="#6366F1")
    secondary_color: Mapped[str] = mapped_column(String(7), default="#8B5CF6")
    background_color: Mapped[str] = mapped_column(String(7), default="#0F172A")
    text_color: Mapped[str] = mapped_column(String(7), default="#F8FAFC")
    font_family: Mapped[str] = mapped_column(String(100), default="Inter")
    logo_url: Mapped[str] = mapped_column(String(500), default="")
    # A founder-supplied screenshot of the real product, composited into a
    # premium browser-window mockup for the product/solution scenes
    # (scene_renderer.py) — the reliable, always-accurate alternative to
    # AI-generated or web-searched imagery (see app/providers/image/
    # factory.py for why neither of those is the default).
    product_screenshot_url: Mapped[str] = mapped_column(String(500), default="")


class Video(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "videos"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    content_variant_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_variants.id", ondelete="SET NULL"), nullable=True)
    script: Mapped[dict] = mapped_column(JSONB, default=dict)  # {hook, problem, insight, solution, product, cta}
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="9:16")  # 9:16 | 1:1 | 16:9
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    has_voiceover: Mapped[bool] = mapped_column(default=False)
    storage_url: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[VideoStatus] = mapped_column(Enum(VideoStatus, native_enum=False, length=20), default=VideoStatus.SCRIPT_READY)
    render_log: Mapped[str] = mapped_column(Text, default="")
    brand_kit_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    rendered_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
