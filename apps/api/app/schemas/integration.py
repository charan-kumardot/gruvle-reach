import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import IntegrationProviderType, IntegrationStatus


class IntegrationCatalogEntry(BaseModel):
    provider_name: str
    provider_type: IntegrationProviderType
    configured: bool  # app-level: does this deployment have OAuth/API credentials at all
    connected: bool  # workspace-level: has this workspace completed connecting it
    capabilities: dict
    notes: str = ""


class IntegrationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    provider_type: IntegrationProviderType
    provider_name: str
    status: IntegrationStatus
    capabilities: list
    scopes: list
    connected_at: dt.datetime | None

    model_config = {"from_attributes": True}
