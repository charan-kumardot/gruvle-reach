import datetime as dt
import uuid

from pydantic import BaseModel


class CompetitorCreateRequest(BaseModel):
    product_id: uuid.UUID
    name: str
    website: str = ""
    notes: str = ""


class CompetitorResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    name: str
    website: str
    notes: str
    last_scanned_at: dt.datetime | None

    model_config = {"from_attributes": True}


class CompetitorChangeResponse(BaseModel):
    id: uuid.UUID
    competitor_id: uuid.UUID
    change_type: str
    description: str
    detected_at: dt.datetime
    source_url: str
    potential_impact: str
    recommended_response: str

    model_config = {"from_attributes": True}
