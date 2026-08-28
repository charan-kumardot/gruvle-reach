import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import VideoStatus


class VideoGenerateRequest(BaseModel):
    content_variant_id: uuid.UUID | None = None
    idea: str | None = None
    product_id: uuid.UUID | None = None
    aspect_ratio: str = "9:16"


class VideoBrandKitResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID | None
    primary_color: str
    secondary_color: str
    background_color: str
    text_color: str
    font_family: str
    logo_url: str
    product_screenshot_url: str

    model_config = {"from_attributes": True}


class VideoResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    content_variant_id: uuid.UUID | None
    script: dict = {}
    aspect_ratio: str
    duration_seconds: float
    has_voiceover: bool
    storage_url: str
    status: VideoStatus
    render_log: str = ""
    rendered_at: dt.datetime | None = None

    model_config = {"from_attributes": True}
