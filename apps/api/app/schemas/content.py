import uuid

from pydantic import BaseModel

from app.db.models.enums import ContentStatus


class ContentIdeaCreateRequest(BaseModel):
    product_id: uuid.UUID
    idea: str
    channels: list[str] = ["linkedin", "x"]
    source_idea_id: uuid.UUID | None = None


class ContentVariantResponse(BaseModel):
    id: uuid.UUID
    content_id: uuid.UUID
    channel: str
    body: str
    status: ContentStatus

    model_config = {"from_attributes": True}


class ContentResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    idea: str
    status: ContentStatus
    source_idea_id: uuid.UUID | None
    variants: list[ContentVariantResponse] = []

    model_config = {"from_attributes": True}


class ContentVariantUpdateRequest(BaseModel):
    body: str | None = None
    status: ContentStatus | None = None
