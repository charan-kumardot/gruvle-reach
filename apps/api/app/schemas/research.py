import uuid

from pydantic import BaseModel

from app.db.models.enums import ResearchSourceType


class ResearchSourceCreateRequest(BaseModel):
    url: str
    name: str = ""
    source_type: ResearchSourceType = ResearchSourceType.USER_SUBMITTED


class ResearchSourceResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    url: str
    name: str
    source_type: ResearchSourceType
    is_active: bool

    model_config = {"from_attributes": True}


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    claim: str
    evidence_snippet: str
    source_url: str
    source_type: str
    confidence: float
    status: str
    related_entity_type: str
    related_entity_id: uuid.UUID | None

    model_config = {"from_attributes": True}
