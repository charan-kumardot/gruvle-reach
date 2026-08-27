import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import MentionCategory


class BrandScanRequest(BaseModel):
    product_id: uuid.UUID
    keywords: list[str]


class BrandMentionResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    keyword: str
    source_url: str
    excerpt: str
    category: MentionCategory
    relevance_score: float
    recommended_action: str
    detected_at: dt.datetime

    model_config = {"from_attributes": True}
