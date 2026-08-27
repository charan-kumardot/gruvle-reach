import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import CompanyFitCategory, EvidenceStatus, PipelineStage


class Company(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "companies"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    website: Mapped[str] = mapped_column(String(500), default="")
    industry: Mapped[str] = mapped_column(String(200), default="")
    country: Mapped[str] = mapped_column(String(100), default="")
    employee_estimate: Mapped[str] = mapped_column(String(50), default="")  # e.g. "20-200" — a range, never a fabricated exact number
    funding_stage: Mapped[str] = mapped_column(String(100), default="")
    funding_amount: Mapped[str] = mapped_column(String(100), default="")
    funding_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    technology_signals: Mapped[list] = mapped_column(JSONB, default=list)
    growth_signals: Mapped[list] = mapped_column(JSONB, default=list)
    potential_pain: Mapped[str] = mapped_column(Text, default="")
    icp_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    icp_fit_category: Mapped[CompanyFitCategory] = mapped_column(
        Enum(CompanyFitCategory, native_enum=False, length=20), default=CompanyFitCategory.LOW_PRIORITY
    )
    icp_fit_factors: Mapped[dict] = mapped_column(JSONB, default=dict)
    manual_score_override: Mapped[float | None] = mapped_column(nullable=True)
    evidence_ids: Mapped[list] = mapped_column(JSONB, default=list)
    source_urls: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus, native_enum=False, length=20), default=EvidenceStatus.HYPOTHESIS
    )
    pipeline_stage: Mapped[PipelineStage] = mapped_column(
        Enum(PipelineStage, native_enum=False, length=20), default=PipelineStage.PROSPECT
    )


class CompanySignal(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "company_signals"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    signal_type: Mapped[str] = mapped_column(String(100))  # technology_adoption, hiring, expansion, ...
    description: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    detected_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class CompanyTrigger(Base, UUIDPKMixin, TimestampMixin):
    """A reason-to-act-now for a company (§13)."""

    __tablename__ = "company_triggers"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    trigger_type: Mapped[str] = mapped_column(String(100))  # funding, launch, hiring, exec_hire, ...
    description: Mapped[str] = mapped_column(Text)
    trigger_date: Mapped[dt.date | None] = mapped_column(nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    product_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    why_it_matters: Mapped[str] = mapped_column(Text, default="")


class Contact(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "contacts"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(200), default="")  # e.g. "CTO" — role hypothesis, not necessarily a named individual
    public_profile_url: Mapped[str] = mapped_column(String(500), default="")
    email: Mapped[str] = mapped_column(String(320), default="")
    source: Mapped[str] = mapped_column(String(200), default="")
    confidence: Mapped[EvidenceStatus] = mapped_column(
        Enum(EvidenceStatus, native_enum=False, length=20), default=EvidenceStatus.HYPOTHESIS
    )
    pipeline_stage: Mapped[PipelineStage] = mapped_column(
        Enum(PipelineStage, native_enum=False, length=20), default=PipelineStage.PROSPECT
    )


class ContactSource(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "contact_sources"

    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), index=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(50), default="webpage")
    retrieved_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
