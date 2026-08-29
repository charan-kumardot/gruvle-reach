import datetime as dt
import uuid

from pydantic import BaseModel

from app.db.models.enums import CompanyFitCategory, EvidenceStatus, PipelineStage


class CompanyResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    name: str
    website: str
    industry: str
    country: str
    employee_estimate: str
    funding_stage: str
    funding_amount: str
    technology_signals: list
    growth_signals: list
    potential_pain: str
    icp_fit_score: float
    icp_fit_category: CompanyFitCategory
    manual_score_override: float | None
    evidence_ids: list
    source_urls: list
    confidence: EvidenceStatus
    pipeline_stage: PipelineStage

    model_config = {"from_attributes": True}


class CompanyDiscoverRequest(BaseModel):
    icp_id: uuid.UUID | None = None
    queries: list[str] = []
    max_results_per_query: int = 15


class CompanyUpdateRequest(BaseModel):
    pipeline_stage: PipelineStage | None = None
    manual_score_override: float | None = None


class TriggerResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    trigger_type: str
    description: str
    trigger_date: dt.date | None
    source_url: str
    confidence: float
    relevance_score: float
    product_fit_score: float
    why_it_matters: str

    model_config = {"from_attributes": True}


class ContactResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    role: str
    public_profile_url: str
    email: str
    source: str
    confidence: EvidenceStatus
    pipeline_stage: PipelineStage

    model_config = {"from_attributes": True}


class ContactCreateRequest(BaseModel):
    name: str = ""
    role: str = ""
    public_profile_url: str = ""
    email: str = ""
    source: str = ""
