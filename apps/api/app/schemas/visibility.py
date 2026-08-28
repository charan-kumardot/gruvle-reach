import datetime as dt
import uuid

from pydantic import BaseModel, Field

from app.db.models.enums import (
    ConfidenceLabel,
    OpportunityCoverage,
    OptimizationMode,
    RiskLevel,
    VisibilityCoverageStatus,
    WebsiteChangeStatus,
    WebsiteOpportunityStatus,
)


class WebsiteCreateRequest(BaseModel):
    name: str
    url: str
    product_id: uuid.UUID
    repository_owner: str = ""
    repository_name: str = ""
    default_branch: str = "main"
    deployment_platform: str = ""
    framework: str = ""


class WebsiteResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    product_id: uuid.UUID
    name: str
    url: str
    repository_owner: str
    repository_name: str
    default_branch: str
    deployment_platform: str
    framework: str
    framework_confidence: ConfidenceLabel

    model_config = {"from_attributes": True}


class WebsiteScanResponse(BaseModel):
    id: uuid.UUID
    website_id: uuid.UUID
    status: str
    started_at: dt.datetime | None
    completed_at: dt.datetime | None
    raw_result: dict
    summary_scores: dict
    error: str

    model_config = {"from_attributes": True}


class SEOIssueResponse(BaseModel):
    id: uuid.UUID
    website_scan_id: uuid.UUID
    issue_type: str
    impact: str
    evidence: str
    recommendation: str
    confidence: float
    status: str

    model_config = {"from_attributes": True}


class VisibilityQuestionResponse(BaseModel):
    id: uuid.UUID
    website_id: uuid.UUID
    question: str
    category: str
    coverage_status: VisibilityCoverageStatus
    evidence_snippet: str
    confidence: float

    model_config = {"from_attributes": True}


class ProductTruthRequest(BaseModel):
    definition: str = ""
    target_customer: str = ""
    problem: str = ""
    solution: str = ""
    core_features: list[str] = Field(default_factory=list)
    positioning: str = ""
    approved_claims: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    brand_voice: str = ""
    competitors: list[str] = Field(default_factory=list)
    pricing: str = ""
    differentiators: list[str] = Field(default_factory=list)


class ProductTruthResponse(ProductTruthRequest):
    id: uuid.UUID
    product_id: uuid.UUID

    model_config = {"from_attributes": True}


class DesignConstitutionRequest(BaseModel):
    typography: str = ""
    colors: str = ""
    logo_rules: str = ""
    spacing: str = ""
    component_system: str = ""
    navigation: str = ""
    layout: str = ""
    animation: str = ""
    responsive_rules: str = ""
    glassmorphism_rules: str = ""


class DesignConstitutionResponse(DesignConstitutionRequest):
    id: uuid.UUID
    website_id: uuid.UUID

    model_config = {"from_attributes": True}


class ProtectedPathRequest(BaseModel):
    path_pattern: str
    label: str = ""


class ProtectedPathResponse(ProtectedPathRequest):
    id: uuid.UUID
    website_id: uuid.UUID

    model_config = {"from_attributes": True}


class WebsiteGuardrailsRequest(BaseModel):
    protect_product_meaning: bool = True
    protect_brand_voice: bool = True
    protect_visual_design: bool = True
    require_approval_content: bool = True
    require_approval_code: bool = True
    require_approval_production: bool = True
    block_unsupported_claims: bool = True
    run_build_checks: bool = True
    run_visual_checks: bool = True


class WebsiteGuardrailsResponse(WebsiteGuardrailsRequest):
    id: uuid.UUID
    website_id: uuid.UUID

    model_config = {"from_attributes": True}


class WebsiteOpportunityResponse(BaseModel):
    id: uuid.UUID
    website_id: uuid.UUID
    opportunity_id: uuid.UUID | None
    title: str
    description: str
    target_path: str
    current_coverage: OpportunityCoverage
    product_fit_score: float
    impact: str
    confidence: float
    status: WebsiteOpportunityStatus

    model_config = {"from_attributes": True}


class GenerateProposalRequest(BaseModel):
    target_path: str = ""  # optional — falls back to framework-based heuristics


class WebsiteChangeResponse(BaseModel):
    id: uuid.UUID
    website_id: uuid.UUID
    website_opportunity_id: uuid.UUID | None
    risk_level: RiskLevel
    mode: OptimizationMode
    status: WebsiteChangeStatus
    branch_name: str
    base_branch: str
    commit_sha: str
    pr_number: int | None
    pr_url: str
    files_changed: list
    semantic_diff: dict
    reason: str

    model_config = {"from_attributes": True}


class ApproveChangeRequest(BaseModel):
    pr_title: str
    pr_body_extra: str = ""
