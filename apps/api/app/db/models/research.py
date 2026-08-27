import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import EvidenceStatus, ResearchSourceType


class ResearchSource(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_sources"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(1000))
    name: Mapped[str] = mapped_column(String(300), default="")
    source_type: Mapped[ResearchSourceType] = mapped_column(Enum(ResearchSourceType, native_enum=False, length=30))
    added_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class ResearchRun(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "research_runs"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    run_type: Mapped[str] = mapped_column(String(50))  # icp, company_discovery, investor_discovery, competitor_scan, brand_scan, market_brief
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
    query: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")


class Evidence(Base, UUIDPKMixin, TimestampMixin):
    """The single evidence ledger every claim in the system points back to (§44)."""

    __tablename__ = "evidence"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    claim: Mapped[str] = mapped_column(Text)
    evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    source_type: Mapped[str] = mapped_column(String(50), default="webpage")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[EvidenceStatus] = mapped_column(Enum(EvidenceStatus, native_enum=False, length=20), default=EvidenceStatus.HYPOTHESIS)
    related_entity_type: Mapped[str] = mapped_column(String(50), default="")
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    retrieved_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(String(128), default="")
