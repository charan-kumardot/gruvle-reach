import uuid

from sqlalchemy import Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import ICPStatus


class Product(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "products"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    website: Mapped[str] = mapped_column(String(500), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(200), default="")
    target_markets: Mapped[list] = mapped_column(JSONB, default=list)
    target_countries: Mapped[list] = mapped_column(JSONB, default=list)
    pricing: Mapped[str] = mapped_column(String(500), default="")
    business_model: Mapped[str] = mapped_column(String(200), default="")
    stage: Mapped[str] = mapped_column(String(100), default="")
    competitors: Mapped[list] = mapped_column(JSONB, default=list)
    differentiators: Mapped[list] = mapped_column(JSONB, default=list)
    brand_voice: Mapped[str] = mapped_column(Text, default="")
    key_messages: Mapped[list] = mapped_column(JSONB, default=list)
    cta: Mapped[str] = mapped_column(String(500), default="")
    social_accounts: Mapped[dict] = mapped_column(JSONB, default=dict)
    launch_status: Mapped[str] = mapped_column(String(100), default="not_launched")
    is_demo: Mapped[bool] = mapped_column(default=False)


class ProductProfile(Base, UUIDPKMixin, TimestampMixin):
    """AI's structured understanding of a product (§8)."""

    __tablename__ = "product_profiles"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    product_category: Mapped[str] = mapped_column(String(200), default="")
    primary_problem: Mapped[str] = mapped_column(Text, default="")
    primary_buyer: Mapped[str] = mapped_column(String(300), default="")
    secondary_buyers: Mapped[list] = mapped_column(JSONB, default=list)
    target_industries: Mapped[list] = mapped_column(JSONB, default=list)
    use_cases: Mapped[list] = mapped_column(JSONB, default=list)
    competitive_categories: Mapped[list] = mapped_column(JSONB, default=list)
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    search_queries: Mapped[list] = mapped_column(JSONB, default=list)
    raw_ai_output: Mapped[dict] = mapped_column(JSONB, default=dict)
    ai_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ai_runs.id", ondelete="SET NULL"), nullable=True)


class ICPProfile(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "icp_profiles"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    criteria: Mapped[dict] = mapped_column(JSONB, default=dict)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    factors: Mapped[dict] = mapped_column(JSONB, default=dict)  # pain, ability_to_pay, reachability, product_fit, urgency, market_size, competition
    status: Mapped[ICPStatus] = mapped_column(Enum(ICPStatus, native_enum=False, length=30), default=ICPStatus.AI_HYPOTHESIS)
    evidence_ids: Mapped[list] = mapped_column(JSONB, default=list)
    created_by: Mapped[str] = mapped_column(String(20), default="ai")  # ai | founder


class AudienceSegment(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "audience_segments"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    icp_profile_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("icp_profiles.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    industries: Mapped[list] = mapped_column(JSONB, default=list)
    company_size_min: Mapped[int | None] = mapped_column(nullable=True)
    company_size_max: Mapped[int | None] = mapped_column(nullable=True)
    job_roles: Mapped[list] = mapped_column(JSONB, default=list)
    geographies: Mapped[list] = mapped_column(JSONB, default=list)
    tech_stack: Mapped[list] = mapped_column(JSONB, default=list)
    funding_stages: Mapped[list] = mapped_column(JSONB, default=list)
    business_models: Mapped[list] = mapped_column(JSONB, default=list)


class BrandBrain(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "brand_brain"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), nullable=True)
    voice: Mapped[str] = mapped_column(String(300), default="")
    tone: Mapped[str] = mapped_column(String(300), default="")
    positioning: Mapped[str] = mapped_column(Text, default="")
    key_messages: Mapped[list] = mapped_column(JSONB, default=list)
    words_to_use: Mapped[list] = mapped_column(JSONB, default=list)
    words_to_avoid: Mapped[list] = mapped_column(JSONB, default=list)
    claims: Mapped[list] = mapped_column(JSONB, default=list)
    proof_points: Mapped[list] = mapped_column(JSONB, default=list)
    founder_story: Mapped[str] = mapped_column(Text, default="")
    product_facts: Mapped[list] = mapped_column(JSONB, default=list)
