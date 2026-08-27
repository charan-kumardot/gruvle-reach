import uuid

from pydantic import BaseModel, Field

from app.db.models.enums import ICPStatus


class ProductCreateRequest(BaseModel):
    name: str
    website: str = ""
    description: str = ""
    category: str = ""
    target_markets: list[str] = Field(default_factory=list)
    target_countries: list[str] = Field(default_factory=list)
    pricing: str = ""
    business_model: str = ""
    stage: str = ""
    competitors: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    brand_voice: str = ""
    cta: str = ""


class ProductUpdateRequest(BaseModel):
    name: str | None = None
    website: str | None = None
    description: str | None = None
    category: str | None = None
    target_markets: list[str] | None = None
    target_countries: list[str] | None = None
    pricing: str | None = None
    business_model: str | None = None
    stage: str | None = None
    competitors: list[str] | None = None
    differentiators: list[str] | None = None
    brand_voice: str | None = None
    cta: str | None = None
    launch_status: str | None = None


class ProductResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    website: str
    description: str
    category: str
    target_markets: list
    target_countries: list
    pricing: str
    business_model: str
    stage: str
    competitors: list
    differentiators: list
    brand_voice: str
    cta: str
    launch_status: str
    is_demo: bool

    model_config = {"from_attributes": True}


class ProductProfileResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_category: str
    primary_problem: str
    primary_buyer: str
    secondary_buyers: list
    target_industries: list
    use_cases: list
    competitive_categories: list
    keywords: list
    search_queries: list

    model_config = {"from_attributes": True}


class ICPProfileResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    criteria: dict
    score: float
    factors: dict
    status: ICPStatus
    created_by: str

    model_config = {"from_attributes": True}


class ICPUpdateRequest(BaseModel):
    name: str | None = None
    criteria: dict | None = None
    status: ICPStatus | None = None


class BrandBrainRequest(BaseModel):
    voice: str = ""
    tone: str = ""
    positioning: str = ""
    key_messages: list[str] = Field(default_factory=list)
    words_to_use: list[str] = Field(default_factory=list)
    words_to_avoid: list[str] = Field(default_factory=list)
    claims: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    founder_story: str = ""
    product_facts: list[str] = Field(default_factory=list)


class BrandBrainResponse(BrandBrainRequest):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID | None

    model_config = {"from_attributes": True}
