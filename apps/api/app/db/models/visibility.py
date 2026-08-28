"""
Visibility module: connect a website's repo, scan it, find SEO/GEO/AI-
visibility opportunities, and turn approved ones into a branch + PR for a
human to review and merge. Nothing here ever writes to a repo's default
branch or merges anything — see app/actions/git_executor.py.
"""
import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import (
    ConfidenceLabel,
    OpportunityCoverage,
    OptimizationMode,
    RiskLevel,
    VisibilityCoverageStatus,
    WebsiteChangeStatus,
    WebsiteOpportunityStatus,
)


class Website(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "websites"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(500))
    repository_owner: Mapped[str] = mapped_column(String(200), default="")
    repository_name: Mapped[str] = mapped_column(String(200), default="")
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    deployment_platform: Mapped[str] = mapped_column(String(50), default="")  # vercel, render, netlify, unknown
    framework: Mapped[str] = mapped_column(String(50), default="")  # nextjs, react, static_html, unknown
    framework_confidence: Mapped[ConfidenceLabel] = mapped_column(
        Enum(ConfidenceLabel, native_enum=False, length=20), default=ConfidenceLabel.UNKNOWN
    )


class WebsiteScan(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "website_scans"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
    started_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Each leaf value in raw_result is stored as {"value": ..., "confidence": "verified|estimated|unknown"}
    raw_result: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary_scores: Mapped[dict] = mapped_column(JSONB, default=dict)  # seo, geo, technical, content, brand_clarity, overall
    error: Mapped[str] = mapped_column(Text, default="")


class SEOIssue(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "seo_issues"

    website_scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("website_scans.id", ondelete="CASCADE"), index=True)
    issue_type: Mapped[str] = mapped_column(String(100))
    impact: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high
    evidence: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, resolved, dismissed


class VisibilityQuestion(Base, UUIDPKMixin, TimestampMixin):
    """A customer-style question used to self-assess GEO/AI-visibility
    coverage against the site's own content (§12) — not a query against a
    live external AI platform."""

    __tablename__ = "visibility_questions"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(100), default="")
    coverage_status: Mapped[VisibilityCoverageStatus] = mapped_column(
        Enum(VisibilityCoverageStatus, native_enum=False, length=20), default=VisibilityCoverageStatus.NOT_DETECTED
    )
    evidence_snippet: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(1000), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))


class ProductTruth(Base, UUIDPKMixin, TimestampMixin):
    """The founder-approved facts about a product — every AI-proposed
    website change is checked against this (§7-8)."""

    __tablename__ = "product_truth"

    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), unique=True, index=True)
    definition: Mapped[str] = mapped_column(Text, default="")
    target_customer: Mapped[str] = mapped_column(Text, default="")
    problem: Mapped[str] = mapped_column(Text, default="")
    solution: Mapped[str] = mapped_column(Text, default="")
    core_features: Mapped[list] = mapped_column(JSONB, default=list)
    positioning: Mapped[str] = mapped_column(Text, default="")
    approved_claims: Mapped[list] = mapped_column(JSONB, default=list)
    forbidden_claims: Mapped[list] = mapped_column(JSONB, default=list)
    brand_voice: Mapped[str] = mapped_column(Text, default="")
    competitors: Mapped[list] = mapped_column(JSONB, default=list)
    pricing: Mapped[str] = mapped_column(Text, default="")
    differentiators: Mapped[list] = mapped_column(JSONB, default=list)


class DesignConstitution(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "design_constitution"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), unique=True, index=True)
    typography: Mapped[str] = mapped_column(Text, default="")
    colors: Mapped[str] = mapped_column(Text, default="")
    logo_rules: Mapped[str] = mapped_column(Text, default="")
    spacing: Mapped[str] = mapped_column(Text, default="")
    component_system: Mapped[str] = mapped_column(Text, default="")
    navigation: Mapped[str] = mapped_column(Text, default="")
    layout: Mapped[str] = mapped_column(Text, default="")
    animation: Mapped[str] = mapped_column(Text, default="")
    responsive_rules: Mapped[str] = mapped_column(Text, default="")
    glassmorphism_rules: Mapped[str] = mapped_column(Text, default="")


class ProtectedPath(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "protected_paths"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), index=True)
    path_pattern: Mapped[str] = mapped_column(String(500))  # e.g. "components/navigation/**"
    label: Mapped[str] = mapped_column(String(200), default="")


class WebsiteGuardrails(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "website_guardrails"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), unique=True, index=True)
    protect_product_meaning: Mapped[bool] = mapped_column(default=True)
    protect_brand_voice: Mapped[bool] = mapped_column(default=True)
    protect_visual_design: Mapped[bool] = mapped_column(default=True)
    require_approval_content: Mapped[bool] = mapped_column(default=True)
    require_approval_code: Mapped[bool] = mapped_column(default=True)
    require_approval_production: Mapped[bool] = mapped_column(default=True)
    block_unsupported_claims: Mapped[bool] = mapped_column(default=True)
    run_build_checks: Mapped[bool] = mapped_column(default=True)
    run_visual_checks: Mapped[bool] = mapped_column(default=True)


class WebsiteOpportunity(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "website_opportunities"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True
    )  # mirrored into the existing unified opportunity feed
    title: Mapped[str] = mapped_column(String(400))
    description: Mapped[str] = mapped_column(Text, default="")
    target_path: Mapped[str] = mapped_column(String(500), default="")
    current_coverage: Mapped[OpportunityCoverage] = mapped_column(
        Enum(OpportunityCoverage, native_enum=False, length=20), default=OpportunityCoverage.LOW
    )
    product_fit_score: Mapped[float] = mapped_column(Float, default=0.0)
    impact: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[WebsiteOpportunityStatus] = mapped_column(
        Enum(WebsiteOpportunityStatus, native_enum=False, length=20), default=WebsiteOpportunityStatus.OPEN
    )


class WebsiteChange(Base, UUIDPKMixin, TimestampMixin):
    """One proposed (and possibly executed) modification. Tracks the full
    SCAN->PROPOSE->VALIDATE->BRANCH->PR lifecycle and never records a merge
    performed by Reach itself — merges always happen on GitHub, by a human."""

    __tablename__ = "website_changes"

    website_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("websites.id", ondelete="CASCADE"), index=True)
    website_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("website_opportunities.id", ondelete="SET NULL"), nullable=True
    )
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel, native_enum=False, length=20), default=RiskLevel.LOW)
    mode: Mapped[OptimizationMode] = mapped_column(
        Enum(OptimizationMode, native_enum=False, length=20), default=OptimizationMode.PROPOSE
    )
    status: Mapped[WebsiteChangeStatus] = mapped_column(
        Enum(WebsiteChangeStatus, native_enum=False, length=20), default=WebsiteChangeStatus.DRAFTED
    )
    branch_name: Mapped[str] = mapped_column(String(300), default="")
    base_branch: Mapped[str] = mapped_column(String(100), default="")
    commit_sha: Mapped[str] = mapped_column(String(100), default="")
    pr_number: Mapped[int | None] = mapped_column(nullable=True)
    pr_url: Mapped[str] = mapped_column(String(500), default="")
    files_changed: Mapped[list] = mapped_column(JSONB, default=list)  # [{path, before, after}]
    semantic_diff: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
