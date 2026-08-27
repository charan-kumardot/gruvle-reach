import datetime as dt
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.models.enums import IntegrationProviderType, IntegrationStatus


class Integration(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "integrations"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    provider_type: Mapped[IntegrationProviderType] = mapped_column(Enum(IntegrationProviderType, native_enum=False, length=20))
    provider_name: Mapped[str] = mapped_column(String(100))  # resend, smtp, searxng, linkedin, x, instagram, product_hunt, slack
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus, native_enum=False, length=20), default=IntegrationStatus.NOT_CONFIGURED
    )
    capabilities: Mapped[list] = mapped_column(JSONB, default=list)
    scopes: Mapped[list] = mapped_column(JSONB, default=list)  # granted OAuth scopes, for permission transparency
    connected_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    connected_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntegrationCredential(Base, UUIDPKMixin, TimestampMixin):
    """Encrypted-at-rest secret payload for an integration. Never logged, never sent to AI."""

    __tablename__ = "integration_credentials"

    integration_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    encrypted_payload: Mapped[str] = mapped_column(String(4000))
