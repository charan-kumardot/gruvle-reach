import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import ContentStatus


class ContentIdeaCreateRequest(BaseModel):
    product_id: uuid.UUID
    idea: str
    channels: list[str] = ["linkedin", "x"]
    source_idea_id: uuid.UUID | None = None
    content_type: str = "educational"


class ContentVariantResponse(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID
    channel: str
    body: str
    status: ContentStatus
    media_refs: list = []
    performance: dict = {}
    approved_by: uuid.UUID | None = None
    approved_at: dt.datetime | None = None
    published_at: dt.datetime | None = None
    platform_format: str = "post"
    cta: str = ""
    scheduled_at: dt.datetime | None = None
    rejected_reason: str = ""
    quality_flags: dict = {}

    model_config = {"from_attributes": True}


class ContentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    idea: str
    status: ContentStatus
    source_idea_id: uuid.UUID | None
    content_type: str = "educational"
    origin: str = "manual"
    campaign_id: uuid.UUID | None = None
    variants: list[ContentVariantResponse] = []

    model_config = {"from_attributes": True}


class ContentVariantUpdateRequest(BaseModel):
    body: str | None = None
    status: ContentStatus | None = None


class ContentVariantScheduleRequest(BaseModel):
    scheduled_at: dt.datetime


class ContentVariantRejectRequest(BaseModel):
    reason: str = ""


class PlanTodayRequest(BaseModel):
    product_id: uuid.UUID
