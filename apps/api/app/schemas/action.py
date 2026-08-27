import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import ActionCategory, ActionStatus


class ActionResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    title: str
    description: str
    category: ActionCategory
    why: str
    impact: str
    effort: str
    evidence_ids: list
    expected_value_score: float
    status: ActionStatus
    requires_approval: bool
    related_entity_type: str
    related_entity_id: uuid.UUID | None
    deadline: dt.date | None

    model_config = {"from_attributes": True}


class ActionStatusUpdateRequest(BaseModel):
    status: ActionStatus
