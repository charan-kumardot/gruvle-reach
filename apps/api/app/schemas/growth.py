import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import LearningInsightStatus


class ResearchRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID | None
    run_type: str
    status: str
    query: str
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    result_summary: dict
    error: str

    model_config = {"from_attributes": True}


class LearningInsightResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    dimension: str
    hypothesis: str
    sample_size: int
    result_summary: dict
    confidence: float
    status: LearningInsightStatus

    model_config = {"from_attributes": True}
