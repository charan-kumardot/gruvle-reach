import datetime as dt
import uuid

from pydantic import BaseModel


class CampaignCreateRequest(BaseModel):
    product_id: uuid.UUID
    name: str
    goal: str = ""
    audience_description: str = ""
    channels: list[str] = []
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class CampaignResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    name: str
    goal: str
    audience_description: str
    status: str
    start_date: dt.date | None
    end_date: dt.date | None

    model_config = {"from_attributes": True}


class CampaignUpdateRequest(BaseModel):
    name: str | None = None
    goal: str | None = None
    audience_description: str | None = None
    status: str | None = None  # planned, active, completed, paused
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class CampaignGenerateContentRequest(BaseModel):
    count: int = 5


class CampaignMetricCreateRequest(BaseModel):
    channel: str = ""
    metric_date: dt.date
    reach: int = 0
    visitors: int = 0
    signups: int = 0
    conversions: int = 0
    responses: int = 0
    meetings: int = 0
    attribution: str = "unknown"
    source_detail: str = ""


class CampaignMetricResponse(CampaignMetricCreateRequest):
    id: uuid.UUID
    campaign_id: uuid.UUID

    model_config = {"from_attributes": True}
