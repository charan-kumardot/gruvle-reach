import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import ActionCategory, ActionStatus


class Action(Base, UUIDPKMixin, TimestampMixin):
    """A recommended, evidence-backed next step surfaced in the Action Center / Daily Brief."""

    __tablename__ = "actions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(400))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[ActionCategory] = mapped_column(Enum(ActionCategory, native_enum=False, length=20))
    why: Mapped[str] = mapped_column(Text, default="")
    impact: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high
    effort: Mapped[str] = mapped_column(String(20), default="low")
    evidence_ids: Mapped[list] = mapped_column(JSONB, default=list)
    expected_value_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[ActionStatus] = mapped_column(Enum(ActionStatus, native_enum=False, length=20), default=ActionStatus.UPCOMING)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    related_entity_type: Mapped[str] = mapped_column(String(50), default="")
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    deadline: Mapped[dt.date | None] = mapped_column(nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class ActionRun(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "action_runs"

    action_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("actions.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, approved, executed, failed, rejected
    executed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    executed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
