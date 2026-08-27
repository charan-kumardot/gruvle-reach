import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import OpportunityType


class Opportunity(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "opportunities"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    type: Mapped[OpportunityType] = mapped_column(Enum(OpportunityType, native_enum=False, length=20), index=True)
    title: Mapped[str] = mapped_column(String(400))
    description: Mapped[str] = mapped_column(Text, default="")
    related_entity_type: Mapped[str] = mapped_column(String(50), default="")  # company, investor, content, competitor, ...
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")  # open, actioned, dismissed
    audience: Mapped[str] = mapped_column(String(500), default="")
    reach_estimate: Mapped[str] = mapped_column(String(200), default="")
    submission_method: Mapped[str] = mapped_column(String(300), default="")
    cost: Mapped[str] = mapped_column(String(200), default="")
    deadline: Mapped[dt.date | None] = mapped_column(nullable=True)
    promotion_rules: Mapped[str] = mapped_column(Text, default="")


class OpportunitySource(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "opportunity_sources"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(50), default="webpage")
    retrieved_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)


class OpportunityScore(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "opportunity_scores"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    relevance: Mapped[float] = mapped_column(Float, default=0.0)
    urgency: Mapped[float] = mapped_column(Float, default=0.0)
    audience_quality: Mapped[float] = mapped_column(Float, default=0.0)
    reachability: Mapped[float] = mapped_column(Float, default=0.0)
    effort: Mapped[float] = mapped_column(Float, default=0.0)
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_quality: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
