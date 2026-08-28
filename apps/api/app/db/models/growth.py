"""Autonomous growth engine: the Learning Engine's output (§24). Everything
else new in this pass (autonomous research orchestration, investor
discovery, marketing discovery) writes into tables that already existed
(Company, Investor, Opportunity, ResearchRun) — this is the one genuinely
new table."""
import uuid

from sqlalchemy import Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import LearningInsightStatus


class LearningInsight(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "learning_insights"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    dimension: Mapped[str] = mapped_column(String(50))  # industry, company_size, trigger_type, channel, investor_sector
    hypothesis: Mapped[str] = mapped_column(Text)  # human-readable, e.g. "AI SaaS companies reply 3.2x more often"
    sample_size: Mapped[int] = mapped_column(Integer)
    result_summary: Mapped[dict] = mapped_column(JSONB, default=dict)  # {group, rate, baseline_rate, lift, ...}
    confidence: Mapped[float] = mapped_column(Float, default=0.3)
    status: Mapped[LearningInsightStatus] = mapped_column(
        Enum(LearningInsightStatus, native_enum=False, length=20), default=LearningInsightStatus.PENDING
    )
