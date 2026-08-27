import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import OutreachMessageStatus, PipelineStage


class Outreach(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "outreach"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(30))  # company, investor, contact
    target_id: Mapped[uuid.UUID] = mapped_column(index=True)
    channel: Mapped[str] = mapped_column(String(30), default="email")  # email, linkedin, x, manual
    status: Mapped[PipelineStage] = mapped_column(Enum(PipelineStage, native_enum=False, length=20), default=PipelineStage.PROSPECT)
    next_follow_up_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["OutreachMessage"]] = relationship(back_populates="outreach")


class OutreachMessage(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "outreach_messages"

    outreach_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach.id", ondelete="CASCADE"), index=True)
    outreach: Mapped["Outreach"] = relationship(back_populates="messages")
    draft_body: Mapped[str] = mapped_column(Text)
    personalization_evidence: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[OutreachMessageStatus] = mapped_column(
        Enum(OutreachMessageStatus, native_enum=False, length=20), default=OutreachMessageStatus.DRAFTED
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OutreachEvent(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "outreach_events"

    outreach_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outreach.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(30))  # sent, opened, replied, bounced
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    event_metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
