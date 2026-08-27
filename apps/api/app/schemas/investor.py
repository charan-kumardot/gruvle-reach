import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import InvestorStage


class InvestorResponse(BaseModel):
    id: uuid.UUID
    fund_name: str
    investor_name: str
    investor_type: str
    website: str
    stage: list
    geography: list
    sector: list
    thesis: str
    portfolio: list
    recent_investments: list
    check_size_min: str
    check_size_max: str
    partner: str
    contact_channel: str
    source_url: str
    confidence: float
    is_demo: bool

    model_config = {"from_attributes": True}


class InvestorCreateRequest(BaseModel):
    fund_name: str = ""
    investor_name: str = ""
    investor_type: str = ""
    website: str = ""
    stage: list[str] = []
    geography: list[str] = []
    sector: list[str] = []
    thesis: str = ""
    portfolio: list[str] = []
    recent_investments: list[str] = []
    check_size_min: str = ""
    check_size_max: str = ""
    partner: str = ""
    contact_channel: str = ""
    source_url: str = ""
    confidence: float = 0.5


class InvestorMatchResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    investor_id: uuid.UUID
    fit_score: float
    reasons: list
    factors: dict

    model_config = {"from_attributes": True}


class InvestorMatchRequest(BaseModel):
    stage: str = ""


class InvestorInteractionResponse(BaseModel):
    id: uuid.UUID
    investor_id: uuid.UUID
    product_id: uuid.UUID
    stage: InvestorStage
    notes: str
    next_action: str
    next_action_date: dt.date | None
    last_contact_at: dt.datetime | None

    model_config = {"from_attributes": True}


class InvestorInteractionUpdateRequest(BaseModel):
    stage: InvestorStage | None = None
    notes: str | None = None
    next_action: str | None = None
    next_action_date: dt.date | None = None
