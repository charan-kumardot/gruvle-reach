import datetime as dt
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class Competitor(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "competitors"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    website: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    last_scanned_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_content_hash: Mapped[str] = mapped_column(String(128), default="")


class CompetitorChange(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "competitor_changes"

    competitor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    change_type: Mapped[str] = mapped_column(String(100))  # pricing, feature, launch, funding, hiring, content, press
    description: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    potential_impact: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high
    evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    recommended_response: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(128), default="")
