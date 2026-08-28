import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.agents.content_agent import ContentAgent
from app.agents.content_pipeline import generate_and_gate_variants, get_brand, get_truth
from app.agents.content_quality_gate import run_quality_gate
from app.agents.content_strategy_agent import AUTONOMOUS_CHANNELS, plan_daily_content
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import ContentStatus, IntegrationStatus, OrgRole
from app.db.models.integration import Integration
from app.db.models.opportunity import Opportunity
from app.db.models.product import BrandBrain
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.social.factory import get_social_access_token_for_workspace, get_social_providers
from app.schemas.content import (
    ContentIdeaCreateRequest,
    ContentResponse,
    ContentVariantRejectRequest,
    ContentVariantResponse,
    ContentVariantScheduleRequest,
    ContentVariantUpdateRequest,
    PlanTodayRequest,
)
from app.schemas.product import BrandBrainRequest, BrandBrainResponse
from app.actions import content_executor

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["content"])


@router.get("/brand-brain", response_model=BrandBrainResponse | None)
def get_brand_brain(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID | None = None,
):
    stmt = select(BrandBrain).where(BrandBrain.workspace_id == ctx.workspace_id)
    stmt = stmt.where(BrandBrain.product_id == product_id) if product_id else stmt.where(BrandBrain.product_id.is_(None))
    return db.execute(stmt).scalars().first()


@router.put("/brand-brain", response_model=BrandBrainResponse)
def upsert_brand_brain(
    payload: BrandBrainRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID | None = None,
):
    stmt = select(BrandBrain).where(BrandBrain.workspace_id == ctx.workspace_id)
    stmt = stmt.where(BrandBrain.product_id == product_id) if product_id else stmt.where(BrandBrain.product_id.is_(None))
    brand = db.execute(stmt).scalars().first()
    if brand is None:
        brand = BrandBrain(workspace_id=ctx.workspace_id, product_id=product_id)
        db.add(brand)
    for field, value in payload.model_dump().items():
        setattr(brand, field, value)
    db.commit()
    db.refresh(brand)
    return brand


@router.get("/content", response_model=list[ContentResponse])
def list_content(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    status: ContentStatus | None = None,
):
    stmt = select(Content).where(Content.workspace_id == ctx.workspace_id)
    if status:
        stmt = stmt.where(Content.status == status)
    return db.execute(stmt.order_by(Content.created_at.desc())).scalars().all()


@router.get("/content/calendar", response_model=list[ContentVariantResponse])
def get_content_calendar(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    from_: dt.datetime | None = Query(None, alias="from"),
    to: dt.datetime | None = None,
):
    stmt = (
        select(ContentVariant)
        .join(Content, Content.id == ContentVariant.content_id)
        .where(
            Content.workspace_id == ctx.workspace_id,
            or_(ContentVariant.scheduled_at.isnot(None), ContentVariant.published_at.isnot(None)),
        )
    )
    if from_:
        stmt = stmt.where(or_(ContentVariant.scheduled_at >= from_, ContentVariant.published_at >= from_))
    if to:
        stmt = stmt.where(or_(ContentVariant.scheduled_at <= to, ContentVariant.published_at <= to))
    return db.execute(stmt.order_by(ContentVariant.scheduled_at.asc().nulls_last())).scalars().all()


@router.get("/content/queue", response_model=list[ContentVariantResponse])
def get_content_queue(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    stmt = (
        select(ContentVariant)
        .join(Content, Content.id == ContentVariant.content_id)
        .where(
            Content.workspace_id == ctx.workspace_id,
            ContentVariant.status.in_([ContentStatus.READY, ContentStatus.APPROVAL_REQUIRED]),
        )
        .order_by(ContentVariant.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


@router.post("/content/generate", response_model=ContentResponse)
def generate_content(
    payload: ContentIdeaCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    brand = get_brand(db, ctx.workspace_id, payload.product_id)
    truth = get_truth(db, payload.product_id)

    content = Content(
        workspace_id=ctx.workspace_id,
        product_id=payload.product_id,
        idea=payload.idea,
        status=ContentStatus.DRAFT,
        source_idea_id=payload.source_idea_id,
        content_type=payload.content_type,
        origin="manual",
    )
    db.add(content)
    db.flush()

    variants = generate_and_gate_variants(db, content=content, brand=brand, truth=truth, channels=payload.channels)
    if not variants:
        raise HTTPException(status_code=503, detail="AI provider unavailable or returned an unparseable response.")

    db.commit()
    db.refresh(content)
    _ = content.variants  # load relationship before returning
    return content


@router.post("/content/plan-today", response_model=list[ContentResponse])
def plan_today(
    payload: PlanTodayRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    """Zero-input daily content planning (§2-4), the manual 'run it now'
    trigger mirroring the Products page's 'Run Autonomous Discovery' button."""
    brand = get_brand(db, ctx.workspace_id, payload.product_id)
    truth = get_truth(db, payload.product_id)

    ideas = plan_daily_content(db, workspace_id=ctx.workspace_id, product_id=payload.product_id, brand=brand)
    created: list[Content] = []
    for idea in ideas:
        content = Content(
            workspace_id=ctx.workspace_id, product_id=payload.product_id, idea=idea["idea"],
            content_type=idea["content_type"], origin=idea["origin"],
        )
        db.add(content)
        db.flush()
        generate_and_gate_variants(db, content=content, brand=brand, truth=truth, channels=AUTONOMOUS_CHANNELS, cta_hint=idea["cta_hint"])
        if idea.get("source_opportunity_id"):
            opportunity = db.get(Opportunity, idea["source_opportunity_id"])
            if opportunity is not None:
                opportunity.status = "actioned"
        created.append(content)

    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="content_plan_today", resource_type="product", resource_id=str(payload.product_id),
        metadata={"ideas_generated": len(created)},
    )
    db.commit()
    for content in created:
        db.refresh(content)
        _ = content.variants
    return created


@router.patch("/content/variants/{variant_id}", response_model=None)
def update_variant(
    variant_id: uuid.UUID,
    payload: ContentVariantUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    variant = db.get(ContentVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Content variant not found")

    body_changed = payload.body is not None and payload.body != variant.body
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)

    if body_changed and variant.status in (ContentStatus.APPROVED, ContentStatus.SCHEDULED):
        # A hand-edit invalidates a prior approval/schedule — must re-pass
        # the quality gate and be re-approved (§28 quality gate must sit
        # between generation and any approved/publishable state).
        variant.status = ContentStatus.DRAFT
        variant.approved_by = None
        variant.approved_at = None
        variant.scheduled_at = None
    elif payload.status == ContentStatus.APPROVED:
        variant.approved_by = ctx.user.id
        variant.approved_at = dt.datetime.now(dt.timezone.utc)

    db.commit()
    db.refresh(variant)
    return ContentVariantResponse.model_validate(variant)


@router.post("/content/variants/{variant_id}/approve", response_model=ContentVariantResponse)
def approve_variant(
    variant_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    variant = db.get(ContentVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Content variant not found")
    if variant.status not in (ContentStatus.READY, ContentStatus.APPROVAL_REQUIRED):
        raise HTTPException(status_code=400, detail=f"Cannot approve a variant in status {variant.status.value}")

    variant.status = ContentStatus.APPROVED
    variant.approved_by = ctx.user.id
    variant.approved_at = dt.datetime.now(dt.timezone.utc)
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="content_variant_approved", resource_type="content_variant", resource_id=str(variant.id),
    )
    db.commit()
    db.refresh(variant)
    return variant


@router.post("/content/variants/{variant_id}/reject", response_model=ContentVariantResponse)
def reject_variant(
    variant_id: uuid.UUID,
    payload: ContentVariantRejectRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    variant = db.get(ContentVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Content variant not found")

    variant.status = ContentStatus.REJECTED
    variant.rejected_reason = payload.reason
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="content_variant_rejected", resource_type="content_variant", resource_id=str(variant.id),
        metadata={"reason": payload.reason},
    )
    db.commit()
    db.refresh(variant)
    return variant


@router.post("/content/variants/{variant_id}/schedule", response_model=ContentVariantResponse)
def schedule_variant(
    variant_id: uuid.UUID,
    payload: ContentVariantScheduleRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    variant = db.get(ContentVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Content variant not found")
    if variant.status != ContentStatus.APPROVED:
        raise HTTPException(status_code=400, detail="Content variant must be APPROVED before it can be scheduled")

    variant.status = ContentStatus.SCHEDULED
    variant.scheduled_at = payload.scheduled_at
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="content_variant_scheduled", resource_type="content_variant", resource_id=str(variant.id),
        metadata={"scheduled_at": payload.scheduled_at.isoformat()},
    )
    db.commit()
    db.refresh(variant)
    return variant


@router.post("/content/variants/{variant_id}/publish-now", response_model=None)
def publish_variant_now(
    variant_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    variant = db.get(ContentVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Content variant not found")
    if variant.status not in (ContentStatus.APPROVED, ContentStatus.SCHEDULED):
        raise HTTPException(status_code=400, detail=f"Cannot publish a variant in status {variant.status.value}")

    integration = db.execute(
        select(Integration).where(
            Integration.workspace_id == ctx.workspace_id,
            Integration.provider_name == variant.channel,
            Integration.status == IntegrationStatus.CONNECTED,
        )
    ).scalar_one_or_none()

    if integration is None:
        # Structural, not exception-handled: never call the executor for an
        # unconnected channel — "never fail if not connected" (§20, §38-39).
        return {
            "status": "manual_action_required",
            "body": variant.body,
            "media_urls": variant.media_refs,
            "message": f"{variant.channel} is not connected. Copy this draft and post manually, or connect it in Settings → Integrations.",
        }

    content = db.get(Content, variant.content_id)
    social_provider = get_social_providers().get(variant.channel)
    if social_provider is None:
        raise HTTPException(status_code=400, detail=f"Unknown channel: {variant.channel}")
    access_token = get_social_access_token_for_workspace(db, ctx.workspace_id, variant.channel)

    updated = content_executor.publish_content_variant(
        db, variant=variant, content=content, approver_role=ctx.role, approver_id=ctx.user.id,
        organization_id=ctx.organization_id, workspace_id=ctx.workspace_id,
        social_provider=social_provider, access_token=access_token,
    )
    db.commit()
    db.refresh(updated)
    return ContentVariantResponse.model_validate(updated)


@router.post("/content/variants/{variant_id}/regenerate", response_model=ContentVariantResponse)
def regenerate_variant(
    variant_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    variant = db.get(ContentVariant, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Content variant not found")
    content = db.get(Content, variant.content_id)
    if content is None or content.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Content variant not found")

    brand = get_brand(db, ctx.workspace_id, content.product_id)
    truth = get_truth(db, content.product_id)
    agent = ContentAgent(db, get_ai_provider())
    output = agent.generate_variants(idea=content.idea, brand=brand, channels=[variant.channel])
    if output is None or not output.get("variants"):
        raise HTTPException(status_code=503, detail="AI provider unavailable or returned an unparseable response.")

    new_data = output["variants"][0]
    variant.body = new_data.get("body", "")
    variant.cta = new_data.get("cta", "")
    variant.approved_by = None
    variant.approved_at = None
    variant.scheduled_at = None

    gate_result = run_quality_gate(db, variant=variant, content=content, brand=brand, truth=truth, ai_provider=get_ai_provider())
    if gate_result.passed:
        variant.status = ContentStatus.READY
        variant.quality_flags = {"warnings": gate_result.warnings}
    else:
        variant.status = ContentStatus.FAILED
        variant.quality_flags = {"blocking_reasons": gate_result.blocking_reasons}

    db.commit()
    db.refresh(variant)
    return variant
