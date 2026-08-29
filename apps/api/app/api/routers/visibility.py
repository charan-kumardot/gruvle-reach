import datetime as dt
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.git_executor import ApprovalRequiredError, CriticalRiskBlockedError, prepare_website_change
from app.actions.policy import can_approve
from app.agents.ai_visibility_agent import AIVisibilityAgent
from app.agents.risk_classifier import classify_risk, is_auto_prepareable
from app.agents.seo_agent import SEOAgent, detect_issues
from app.agents.website_optimization_agent import WebsiteOptimizationAgent, build_pr_body
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.enums import (
    ConfidenceLabel,
    OpportunityCoverage,
    OpportunityType,
    OptimizationMode,
    OrgRole,
    VisibilityCoverageStatus,
    WebsiteChangeStatus,
    WebsiteOpportunityStatus,
)
from app.db.models.opportunity import Opportunity
from app.db.models.product import Product, ProductProfile
from app.db.models.visibility import (
    DesignConstitution,
    ProductTruth,
    ProtectedPath,
    SEOIssue,
    VisibilityQuestion,
    Website,
    WebsiteChange,
    WebsiteGuardrails,
    WebsiteOpportunity,
    WebsiteScan,
)
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.git.base import GitProviderError
from app.providers.git.factory import get_git_provider_for_workspace
from app.research.website_scanner import detect_framework, scan_website
from app.schemas.visibility import (
    ApproveChangeRequest,
    DesignConstitutionRequest,
    DesignConstitutionResponse,
    GenerateProposalRequest,
    ProductTruthRequest,
    ProductTruthResponse,
    ProtectedPathRequest,
    ProtectedPathResponse,
    SEOIssueResponse,
    VisibilityQuestionResponse,
    WebsiteChangeResponse,
    WebsiteCreateRequest,
    WebsiteGuardrailsRequest,
    WebsiteGuardrailsResponse,
    WebsiteOpportunityResponse,
    WebsiteResponse,
    WebsiteScanResponse,
    WebsiteUpdateRequest,
)

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["visibility"])


def _get_website(db: Session, workspace_id: uuid.UUID, website_id: uuid.UUID) -> Website:
    website = db.get(Website, website_id)
    if website is None or website.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Website not found")
    return website


# ---- Websites -----------------------------------------------------------


@router.get("/websites", response_model=list[WebsiteResponse])
def list_websites(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID | None = None,
):
    stmt = select(Website).where(Website.workspace_id == ctx.workspace_id)
    if product_id:
        stmt = stmt.where(Website.product_id == product_id)
    return db.execute(stmt).scalars().all()


@router.post("/websites", response_model=WebsiteResponse, status_code=201)
def create_website(
    payload: WebsiteCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    framework, confidence = ("", ConfidenceLabel.UNKNOWN)
    if payload.url:
        framework, confidence = detect_framework(payload.url)

    website = Website(
        workspace_id=ctx.workspace_id,
        **payload.model_dump(),
    )
    if not website.framework:
        website.framework = framework
        website.framework_confidence = confidence

    db.add(website)
    db.flush()
    db.add(WebsiteGuardrails(website_id=website.id))
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="website_connected", resource_type="website", resource_id=str(website.id),
    )
    db.commit()
    db.refresh(website)
    return website


@router.get("/websites/{website_id}", response_model=WebsiteResponse)
def get_website(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return _get_website(db, ctx.workspace_id, website_id)


@router.patch("/websites/{website_id}", response_model=WebsiteResponse)
def update_website(
    website_id: uuid.UUID,
    payload: WebsiteUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Fixing a typo'd URL (or a domain change) shouldn't mean losing every
    scan/SEO-issue/opportunity/change tied to this website by deleting and
    re-creating it — this was the only way to correct it before."""
    website = _get_website(db, ctx.workspace_id, website_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        if value is not None:
            setattr(website, field, value)
    if "url" in updates and updates["url"]:
        framework, confidence = detect_framework(website.url)
        website.framework = framework
        website.framework_confidence = confidence
    db.commit()
    db.refresh(website)
    return website


@router.delete("/websites/{website_id}", status_code=204)
def delete_website(
    website_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    website = _get_website(db, ctx.workspace_id, website_id)
    db.delete(website)
    db.commit()


# ---- Scan -----------------------------------------------------------------


@router.post("/websites/{website_id}/scan", response_model=WebsiteScanResponse)
def run_scan(
    website_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    website = _get_website(db, ctx.workspace_id, website_id)

    scan = WebsiteScan(website_id=website.id, status="running", started_at=dt.datetime.now(dt.timezone.utc))
    db.add(scan)
    db.flush()

    raw_result = scan_website(website.url)
    scan.raw_result = raw_result
    scan.completed_at = dt.datetime.now(dt.timezone.utc)
    scan.status = "failed" if raw_result.get("fetch_error") else "completed"

    if scan.status == "completed":
        issues = detect_issues(raw_result)
        seo_agent = SEOAgent(db, get_ai_provider())
        recommendations = seo_agent.generate_recommendations(issues=issues, workspace_id=ctx.workspace_id)
        for issue in issues:
            db.add(
                SEOIssue(
                    website_scan_id=scan.id, issue_type=issue.issue_type, impact=issue.impact,
                    evidence=issue.evidence, recommendation=recommendations.get(issue.issue_type, ""),
                    confidence=issue.confidence,
                )
            )

        scores = _compute_summary_scores(raw_result, issues)
        scan.summary_scores = scores

        _sync_website_opportunities(db, ctx, website, issues)

    db.commit()
    db.refresh(scan)
    return scan


def _compute_summary_scores(raw_result: dict, issues: list) -> dict:
    def val(key: str):
        return raw_result.get(key, {}).get("value")

    # Homepage issues are weighted in full; per-page issues (from sampled
    # internal/sitemap pages — evidence prefixed "[url] ") are averaged per
    # page instead of summed linearly, so scanning more pages doesn't
    # mechanically crater the score just for having more of them sampled.
    weights = {"low": 3, "medium": 7, "high": 15}
    homepage_issues = [i for i in issues if not i.evidence.startswith("[")]
    page_issues = [i for i in issues if i.evidence.startswith("[")]

    homepage_penalty = sum(weights.get(i.impact, 5) for i in homepage_issues)
    per_page_penalty: dict[str, int] = {}
    for i in page_issues:
        page_url = i.evidence.split("]", 1)[0].lstrip("[")
        per_page_penalty[page_url] = per_page_penalty.get(page_url, 0) + weights.get(i.impact, 5)
    avg_page_penalty = round(sum(per_page_penalty.values()) / len(per_page_penalty)) if per_page_penalty else 0

    seo_score = max(0, 100 - homepage_penalty - avg_page_penalty)

    technical_score = 100
    if not val("https"):
        technical_score -= 30
    if val("broken_links_sample"):
        technical_score -= 10 * min(3, len(val("broken_links_sample")))
    if not val("mobile_friendly"):
        technical_score -= 15
    technical_score = max(0, technical_score)

    content_score = 100
    if not val("title"):
        content_score -= 25
    if not val("meta_description"):
        content_score -= 25
    if val("h1_count") == 0:
        content_score -= 20
    content_score = max(0, content_score)

    geo_score = 50  # refined once visibility questions are checked (see /geo-scan)

    overall = round((seo_score + technical_score + content_score + geo_score) / 4)

    return {
        "seo": seo_score, "technical": technical_score, "content": content_score,
        "geo": geo_score, "brand_clarity": 70, "overall": overall,
    }


def _sync_website_opportunities(db: Session, ctx: WorkspaceContext, website: Website, issues: list) -> None:
    """Content Opportunity Engine tie-in (§13): mirrors high/medium impact
    SEO issues into WebsiteOpportunity + the existing unified Opportunity
    feed, skipping ones that already have an open opportunity."""
    existing = db.execute(
        select(WebsiteOpportunity.title).where(
            WebsiteOpportunity.website_id == website.id, WebsiteOpportunity.status == WebsiteOpportunityStatus.OPEN
        )
    ).scalars().all()
    existing_titles = set(existing)

    for issue in issues:
        if issue.impact not in ("medium", "high"):
            continue
        # Per-page issues (from sampled internal/sitemap pages) prefix their
        # evidence with "[url] " — fold that into the title so each page's
        # issue gets its own opportunity instead of colliding on a single
        # generic "Fix: missing title" title.
        page_match = re.match(r"^\[(.+?)\]\s*", issue.evidence)
        base_title = f"Fix: {issue.issue_type.replace('_', ' ')}"
        title = f"{base_title} ({page_match.group(1)})" if page_match else base_title
        if title in existing_titles:
            continue

        opportunity = Opportunity(
            workspace_id=ctx.workspace_id, product_id=website.product_id, type=OpportunityType.CONTENT,
            title=title, description=issue.evidence, status="open",
        )
        db.add(opportunity)
        db.flush()

        db.add(
            WebsiteOpportunity(
                website_id=website.id, opportunity_id=opportunity.id, title=title, description=issue.evidence,
                current_coverage=OpportunityCoverage.LOW, product_fit_score=70.0 if issue.impact == "high" else 55.0,
                impact=issue.impact, confidence=issue.confidence, status=WebsiteOpportunityStatus.OPEN,
            )
        )
        existing_titles.add(title)


@router.get("/websites/{website_id}/scans", response_model=list[WebsiteScanResponse])
def list_scans(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    return db.execute(select(WebsiteScan).where(WebsiteScan.website_id == website_id).order_by(WebsiteScan.created_at.desc())).scalars().all()


@router.get("/websites/{website_id}/scans/latest", response_model=WebsiteScanResponse | None)
def latest_scan(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    return db.execute(select(WebsiteScan).where(WebsiteScan.website_id == website_id).order_by(WebsiteScan.created_at.desc())).scalars().first()


@router.get("/websites/{website_id}/seo-issues", response_model=list[SEOIssueResponse])
def list_seo_issues(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    scan = db.execute(select(WebsiteScan).where(WebsiteScan.website_id == website_id).order_by(WebsiteScan.created_at.desc())).scalars().first()
    if scan is None:
        return []
    return db.execute(select(SEOIssue).where(SEOIssue.website_scan_id == scan.id)).scalars().all()


# ---- GEO / AI visibility --------------------------------------------------


@router.post("/websites/{website_id}/geo-scan", response_model=list[VisibilityQuestionResponse])
def run_geo_scan(
    website_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    website = _get_website(db, ctx.workspace_id, website_id)
    product = db.get(Product, website.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    profile = db.execute(
        select(ProductProfile).where(ProductProfile.product_id == product.id).order_by(ProductProfile.created_at.desc())
    ).scalars().first()

    latest_scan_row = db.execute(select(WebsiteScan).where(WebsiteScan.website_id == website_id).order_by(WebsiteScan.created_at.desc())).scalars().first()
    if latest_scan_row is None:
        raise HTTPException(status_code=400, detail="Run a scan first")

    agent = AIVisibilityAgent(db, get_ai_provider())
    questions = agent.generate_questions(product=product, profile=profile, workspace_id=ctx.workspace_id)
    if not questions:
        raise HTTPException(status_code=503, detail="AI provider unavailable or returned an unparseable response.")

    page_text = " ".join(
        str(latest_scan_row.raw_result.get(k, {}).get("value", ""))
        for k in ("title", "meta_description")
    )
    headings = latest_scan_row.raw_result.get("headings", {}).get("value", {})
    page_text += " " + " ".join(h for level in headings.values() for h in level)

    # Also fold in title/meta/headings from sampled internal/sitemap pages —
    # otherwise GEO coverage is blind to answers that live on /pricing,
    # /faq, etc. rather than the homepage.
    for page in latest_scan_row.raw_result.get("sampled_pages", {}).get("value", []):
        page_text += " " + str(page.get("title") or "") + " " + str(page.get("meta_description") or "")
        page_headings = page.get("headings") or {}
        page_text += " " + " ".join(h for level in page_headings.values() for h in level)

    coverage = agent.check_coverage(questions=[q["question"] for q in questions], page_text=page_text, workspace_id=ctx.workspace_id)
    coverage_by_question = {c.get("question"): c for c in coverage}

    created = []
    now = dt.datetime.now(dt.timezone.utc)
    for q in questions:
        c = coverage_by_question.get(q["question"], {})
        row = VisibilityQuestion(
            website_id=website.id, question=q["question"], category=q.get("category", ""),
            coverage_status=VisibilityCoverageStatus.MENTIONED if c.get("covered") else VisibilityCoverageStatus.NOT_DETECTED,
            evidence_snippet=c.get("evidence_snippet", ""), source_url=website.url,
            confidence=float(c.get("confidence", 0.5)), checked_at=now,
        )
        db.add(row)
        created.append(row)

    db.commit()
    for r in created:
        db.refresh(r)
    return created


@router.get("/websites/{website_id}/visibility-questions", response_model=list[VisibilityQuestionResponse])
def list_visibility_questions(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    return db.execute(select(VisibilityQuestion).where(VisibilityQuestion.website_id == website_id).order_by(VisibilityQuestion.checked_at.desc())).scalars().all()


# ---- Product Truth ----------------------------------------------------------


@router.get("/products/{product_id}/product-truth", response_model=ProductTruthResponse | None)
def get_product_truth(product_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(ProductTruth).where(ProductTruth.product_id == product_id)).scalars().first()


@router.put("/products/{product_id}/product-truth", response_model=ProductTruthResponse)
def upsert_product_truth(
    product_id: uuid.UUID,
    payload: ProductTruthRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    truth = db.execute(select(ProductTruth).where(ProductTruth.product_id == product_id)).scalars().first()
    if truth is None:
        truth = ProductTruth(product_id=product_id)
        db.add(truth)
    for field, value in payload.model_dump().items():
        setattr(truth, field, value)
    db.commit()
    db.refresh(truth)
    return truth


# ---- Design Constitution / Protected Paths / Guardrails --------------------


@router.get("/websites/{website_id}/design-constitution", response_model=DesignConstitutionResponse | None)
def get_design_constitution(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    return db.execute(select(DesignConstitution).where(DesignConstitution.website_id == website_id)).scalars().first()


@router.put("/websites/{website_id}/design-constitution", response_model=DesignConstitutionResponse)
def upsert_design_constitution(
    website_id: uuid.UUID,
    payload: DesignConstitutionRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    _get_website(db, ctx.workspace_id, website_id)
    dc = db.execute(select(DesignConstitution).where(DesignConstitution.website_id == website_id)).scalars().first()
    if dc is None:
        dc = DesignConstitution(website_id=website_id)
        db.add(dc)
    for field, value in payload.model_dump().items():
        setattr(dc, field, value)
    db.commit()
    db.refresh(dc)
    return dc


@router.get("/websites/{website_id}/protected-paths", response_model=list[ProtectedPathResponse])
def list_protected_paths(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    return db.execute(select(ProtectedPath).where(ProtectedPath.website_id == website_id)).scalars().all()


@router.post("/websites/{website_id}/protected-paths", response_model=ProtectedPathResponse, status_code=201)
def add_protected_path(
    website_id: uuid.UUID,
    payload: ProtectedPathRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    _get_website(db, ctx.workspace_id, website_id)
    row = ProtectedPath(website_id=website_id, **payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/websites/{website_id}/protected-paths/{path_id}", status_code=204)
def remove_protected_path(
    website_id: uuid.UUID, path_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    row = db.get(ProtectedPath, path_id)
    if row is None or row.website_id != website_id:
        raise HTTPException(status_code=404, detail="Protected path not found")
    db.delete(row)
    db.commit()


@router.get("/websites/{website_id}/guardrails", response_model=WebsiteGuardrailsResponse)
def get_guardrails(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    guardrails = db.execute(select(WebsiteGuardrails).where(WebsiteGuardrails.website_id == website_id)).scalars().first()
    if guardrails is None:
        guardrails = WebsiteGuardrails(website_id=website_id)
        db.add(guardrails)
        db.commit()
        db.refresh(guardrails)
    return guardrails


@router.put("/websites/{website_id}/guardrails", response_model=WebsiteGuardrailsResponse)
def update_guardrails(
    website_id: uuid.UUID,
    payload: WebsiteGuardrailsRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    _get_website(db, ctx.workspace_id, website_id)
    guardrails = db.execute(select(WebsiteGuardrails).where(WebsiteGuardrails.website_id == website_id)).scalars().first()
    if guardrails is None:
        guardrails = WebsiteGuardrails(website_id=website_id)
        db.add(guardrails)
    for field, value in payload.model_dump().items():
        setattr(guardrails, field, value)
    db.commit()
    db.refresh(guardrails)
    return guardrails


# ---- Opportunities & Changes ------------------------------------------------


@router.get("/websites/{website_id}/opportunities", response_model=list[WebsiteOpportunityResponse])
def list_website_opportunities(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    return db.execute(
        select(WebsiteOpportunity).where(WebsiteOpportunity.website_id == website_id).order_by(WebsiteOpportunity.product_fit_score.desc())
    ).scalars().all()


@router.post("/websites/{website_id}/opportunities/{opportunity_id}/generate-proposal", response_model=WebsiteChangeResponse)
def generate_proposal(
    website_id: uuid.UUID,
    opportunity_id: uuid.UUID,
    payload: GenerateProposalRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    website = _get_website(db, ctx.workspace_id, website_id)
    opportunity = db.get(WebsiteOpportunity, opportunity_id)
    if opportunity is None or opportunity.website_id != website_id:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    git_provider = get_git_provider_for_workspace(db, ctx.workspace_id)
    if not git_provider.configured():
        raise HTTPException(
            status_code=400,
            detail="Connect GitHub in Settings -> Integrations before generating a proposal that touches code.",
        )

    agent = WebsiteOptimizationAgent(db, get_ai_provider())
    located = agent.find_target_file(git=git_provider, website=website, explicit_path=payload.target_path)
    if located is None:
        if not payload.target_path:
            raise HTTPException(status_code=404, detail="Could not locate a source file for this opportunity — specify target_path explicitly.")
        # File doesn't exist yet at an explicitly-given path — treat this as
        # a "create new file" proposal (e.g. a missing robots.txt/sitemap.xml).
        target_path, current_content, current_sha = payload.target_path, "", ""
    else:
        target_path, current_content, current_sha = located

    truth = db.execute(select(ProductTruth).where(ProductTruth.product_id == website.product_id)).scalars().first()
    constitution = db.execute(select(DesignConstitution).where(DesignConstitution.website_id == website_id)).scalars().first()
    protected = db.execute(select(ProtectedPath).where(ProtectedPath.website_id == website_id)).scalars().all()

    result = agent.propose_change(
        website=website, issue_description=opportunity.description, target_path=target_path,
        current_content=current_content, current_sha=current_sha, truth=truth, constitution=constitution,
        protected_patterns=[p.path_pattern for p in protected], workspace_id=ctx.workspace_id,
    )

    change = WebsiteChange(
        website_id=website_id, website_opportunity_id=opportunity_id,
        risk_level=result["risk_level"], mode=OptimizationMode.PROPOSE, status=result["status"],
        files_changed=result["files_changed"], semantic_diff=result["semantic_diff"], reason=result["reason"],
        created_by=ctx.user.id,
    )
    db.add(change)
    opportunity.status = WebsiteOpportunityStatus.PROPOSED

    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="website_change_proposed", resource_type="website_change", resource_id=str(change.id),
        metadata={"risk_level": result["risk_level"].value, "status": result["status"].value},
    )
    db.commit()
    db.refresh(change)
    return change


@router.get("/websites/{website_id}/changes", response_model=list[WebsiteChangeResponse])
def list_changes(website_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_website(db, ctx.workspace_id, website_id)
    return db.execute(select(WebsiteChange).where(WebsiteChange.website_id == website_id).order_by(WebsiteChange.created_at.desc())).scalars().all()


@router.get("/websites/{website_id}/changes/{change_id}", response_model=WebsiteChangeResponse)
def get_change(website_id: uuid.UUID, change_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    change = db.get(WebsiteChange, change_id)
    if change is None or change.website_id != website_id:
        raise HTTPException(status_code=404, detail="Change not found")
    return change


@router.post("/websites/{website_id}/changes/{change_id}/approve", response_model=WebsiteChangeResponse)
def approve_change(
    website_id: uuid.UUID, change_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
):
    if not can_approve(ctx.role):
        raise HTTPException(status_code=403, detail="Your role cannot approve website changes")
    change = db.get(WebsiteChange, change_id)
    if change is None or change.website_id != website_id:
        raise HTTPException(status_code=404, detail="Change not found")
    if change.status != WebsiteChangeStatus.VALIDATED:
        raise HTTPException(status_code=409, detail=f"Change must be VALIDATED to approve (currently {change.status.value})")
    if not is_auto_prepareable(change.risk_level):
        raise HTTPException(
            status_code=403,
            detail=f"{change.risk_level.value.upper()}-risk changes can never be approved for automatic branch/PR preparation — review and make this change manually instead.",
        )

    change.status = WebsiteChangeStatus.APPROVED
    change.approved_by = ctx.user.id
    change.approved_at = dt.datetime.now(dt.timezone.utc)
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="website_change_approved", resource_type="website_change", resource_id=str(change.id),
    )
    db.commit()
    db.refresh(change)
    return change


@router.post("/websites/{website_id}/changes/{change_id}/prepare", response_model=WebsiteChangeResponse)
def prepare_change(
    website_id: uuid.UUID, change_id: uuid.UUID,
    payload: ApproveChangeRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
):
    website = _get_website(db, ctx.workspace_id, website_id)
    change = db.get(WebsiteChange, change_id)
    if change is None or change.website_id != website_id:
        raise HTTPException(status_code=404, detail="Change not found")

    website_opportunity = db.get(WebsiteOpportunity, change.website_opportunity_id) if change.website_opportunity_id else None
    pr_body = build_pr_body(
        opportunity_title=payload.pr_title, why=(website_opportunity.description if website_opportunity else "") + ("\n\n" + payload.pr_body_extra if payload.pr_body_extra else ""),
        files_changed=change.files_changed, semantic_diff=change.semantic_diff, risk_level=change.risk_level.value,
    )

    git_provider = get_git_provider_for_workspace(db, ctx.workspace_id)
    try:
        prepare_website_change(
            db, change=change, website=website, pr_title=payload.pr_title, pr_body=pr_body,
            approver_role=ctx.role, approver_id=ctx.user.id, organization_id=ctx.organization_id,
            workspace_id=ctx.workspace_id, git_provider=git_provider,
        )
    except ApprovalRequiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CriticalRiskBlockedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except GitProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if website_opportunity is not None:
        website_opportunity.status = WebsiteOpportunityStatus.COMPLETED

    db.commit()
    db.refresh(change)
    return change
