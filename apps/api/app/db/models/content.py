import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import ContentStatus


class Content(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "content"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    idea: Mapped[str] = mapped_column(Text)
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, native_enum=False, length=20), default=ContentStatus.IDEA)
    source_idea_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content.id", ondelete="SET NULL"), nullable=True)

    variants: Mapped[list["ContentVariant"]] = relationship(back_populates="content", foreign_keys="ContentVariant.content_id")


class ContentVariant(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "content_variants"

    content_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content.id", ondelete="CASCADE"), index=True)
    content: Mapped["Content"] = relationship(back_populates="variants", foreign_keys=[content_id])
    channel: Mapped[str] = mapped_column(String(50))  # linkedin, x, instagram, youtube_shorts, blog, newsletter, reddit, product_hunt
    body: Mapped[str] = mapped_column(Text, default="")
    media_refs: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, native_enum=False, length=20), default=ContentStatus.DRAFT)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    performance: Mapped[dict] = mapped_column(JSONB, default=dict)
