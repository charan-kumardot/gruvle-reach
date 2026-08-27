import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import OpportunityType


class OpportunityCreateRequest(BaseModel):
    product_id: uuid.UUID
    type: OpportunityType
    title: str
    description: str = ""
    audience: str = ""
    reach_estimate: str = ""
    submission_method: str = ""
    cost: str = ""
    deadline: dt.date | None = None
    promotion_rules: str = ""


class OpportunityResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    type: OpportunityType
    title: str
    description: str
    status: str
    audience: str
    reach_estimate: str
    submission_method: str
    cost: str
    deadline: dt.date | None
    promotion_rules: str

    model_config = {"from_attributes": True}


class OpportunityScoreRequest(BaseModel):
    relevance: float = 50
    urgency: float = 50
    audience_quality: float = 50
    reachability: float = 50
    effort: float = 30
    expected_value: float = 50
    evidence_quality: float = 50


class OpportunityScoreResponse(BaseModel):
    id: uuid.UUID
    opportunity_id: uuid.UUID
    relevance: float
    urgency: float
    audience_quality: float
    reachability: float
    effort: float
    expected_value: float
    evidence_quality: float
    total_score: float

    model_config = {"from_attributes": True}
