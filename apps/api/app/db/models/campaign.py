import datetime as dt
import uuid

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class Campaign(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaigns"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300))
    goal: Mapped[str] = mapped_column(String(500), default="")
    audience_description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="planned")  # planned, active, completed, paused
    start_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)


class CampaignChannel(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_channels"

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(100))  # linkedin, x, product_hunt, reddit, communities, email
    status: Mapped[str] = mapped_column(String(30), default="planned")


class CampaignMetric(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "campaign_metrics"

    campaign_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(100), default="")
    metric_date: Mapped[dt.date] = mapped_column(Date)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    visitors: Mapped[int] = mapped_column(Integer, default=0)
    signups: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    responses: Mapped[int] = mapped_column(Integer, default=0)
    meetings: Mapped[int] = mapped_column(Integer, default=0)
    attribution: Mapped[str] = mapped_column(String(20), default="unknown")  # known, estimated, unknown
    source_detail: Mapped[str] = mapped_column(String(200), default="")
