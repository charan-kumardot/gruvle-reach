import uuid

from pydantic import BaseModel

from app.db.models.enums import OutreachMessageStatus, PipelineStage


class OutreachDraftRequest(BaseModel):
    product_id: uuid.UUID
    target_type: str  # company | investor | contact
    target_id: uuid.UUID
    channel: str = "email"
    trigger_id: uuid.UUID | None = None


class OutreachMessageResponse(BaseModel):
    id: uuid.UUID
    outreach_id: uuid.UUID
    draft_body: str
    personalization_evidence: list
    status: OutreachMessageStatus

    model_config = {"from_attributes": True}


class OutreachResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    target_type: str
    target_id: uuid.UUID
    channel: str
    status: PipelineStage
    messages: list[OutreachMessageResponse] = []

    model_config = {"from_attributes": True}


class OutreachSendRequest(BaseModel):
    to_email: str
    subject: str
