import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import InvestorStage


class Investor(Base, UUIDPKMixin, TimestampMixin):
    """Global reference directory — public investor/fund data, shared across workspaces."""

    __tablename__ = "investors"

    fund_name: Mapped[str] = mapped_column(String(300), default="")
    investor_name: Mapped[str] = mapped_column(String(300), default="")
    investor_type: Mapped[str] = mapped_column(String(100), default="")  # vc, angel, accelerator, corporate_vc, government, grant
    website: Mapped[str] = mapped_column(String(500), default="")
    stage: Mapped[list] = mapped_column(JSONB, default=list)
    geography: Mapped[list] = mapped_column(JSONB, default=list)
    sector: Mapped[list] = mapped_column(JSONB, default=list)
    thesis: Mapped[str] = mapped_column(Text, default="")
    portfolio: Mapped[list] = mapped_column(JSONB, default=list)
    recent_investments: Mapped[list] = mapped_column(JSONB, default=list)
    check_size_min: Mapped[str] = mapped_column(String(50), default="")
    check_size_max: Mapped[str] = mapped_column(String(50), default="")
    partner: Mapped[str] = mapped_column(String(200), default="")
    contact_channel: Mapped[str] = mapped_column(String(300), default="")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    is_demo: Mapped[bool] = mapped_column(default=False)


class InvestorMatch(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "investor_matches"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    investor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investors.id", ondelete="CASCADE"), index=True)
    fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    reasons: Mapped[list] = mapped_column(JSONB, default=list)  # [{reason, evidence_id}]
    factors: Mapped[dict] = mapped_column(JSONB, default=dict)  # sector_fit, stage_fit, geography, portfolio_relevance, recent_activity, check_size


class InvestorInteraction(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "investor_interactions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    investor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("investors.id", ondelete="CASCADE"), index=True)
    stage: Mapped[InvestorStage] = mapped_column(Enum(InvestorStage, native_enum=False, length=20), default=InvestorStage.DISCOVERED)
    notes: Mapped[str] = mapped_column(Text, default="")
    next_action: Mapped[str] = mapped_column(String(500), default="")
    next_action_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    last_contact_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
