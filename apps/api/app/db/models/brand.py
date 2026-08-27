import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import MentionCategory


class BrandMention(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "brand_mentions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    keyword: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(50), default="webpage")
    excerpt: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[MentionCategory] = mapped_column(Enum(MentionCategory, native_enum=False, length=30), default=MentionCategory.NEUTRAL)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    recommended_action: Mapped[str] = mapped_column(Text, default="")
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
