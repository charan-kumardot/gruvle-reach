import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.content_pipeline import generate_and_gate_variants, get_brand, get_truth
from app.agents.content_strategy_agent import plan_campaign_content
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.campaign import Campaign, CampaignChannel, CampaignMetric
from app.db.models.content import Content
from app.db.models.enums import OrgRole
from app.db.session import get_db
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignGenerateContentRequest,
    CampaignMetricCreateRequest,
    CampaignMetricResponse,
    CampaignResponse,
    CampaignUpdateRequest,
)
from app.schemas.content import ContentResponse

router = APIRouter(prefix="/workspaces/{workspace_id}/campaigns", tags=["campaigns"])


def _get_campaign_or_404(db: Session, campaign_id: uuid.UUID, workspace_id: uuid.UUID) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return db.execute(select(Campaign).where(Campaign.workspace_id == ctx.workspace_id).order_by(Campaign.created_at.desc())).scalars().all()


@router.post("", response_model=CampaignResponse, status_code=201)
def create_campaign(
    payload: CampaignCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    data = payload.model_dump()
    channels = data.pop("channels")
    campaign = Campaign(workspace_id=ctx.workspace_id, **data)
    db.add(campaign)
    db.flush()
    for channel in channels:
        db.add(CampaignChannel(campaign_id=campaign.id, channel=channel))
    db.commit()
    db.refresh(campaign)
    return campaign


@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    return _get_campaign_or_404(db, campaign_id, ctx.workspace_id)


@router.get("/{campaign_id}/content", response_model=list[ContentResponse])
def get_campaign_content(campaign_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_campaign_or_404(db, campaign_id, ctx.workspace_id)
    stmt = select(Content).where(Content.campaign_id == campaign_id).order_by(Content.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(
    campaign_id: uuid.UUID,
    payload: CampaignUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    campaign = _get_campaign_or_404(db, campaign_id, ctx.workspace_id)
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates and updates["status"] == "active" and ctx.role.value not in ("admin", "owner"):
        # Activating a campaign is a higher-stakes, multi-asset action than
        # approving a single post — requires ADMIN, not the MEMBER bar that
        # covers individual variant approval/publish (§7).
        raise HTTPException(status_code=403, detail="Activating a campaign requires the admin role or higher")
    for field, value in updates.items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return campaign


@router.post("/{campaign_id}/generate-content", response_model=list[ContentResponse])
def generate_campaign_content(
    campaign_id: uuid.UUID,
    payload: CampaignGenerateContentRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.ADMIN))],
    db: Annotated[Session, Depends(get_db)],
):
    campaign = _get_campaign_or_404(db, campaign_id, ctx.workspace_id)
    brand = get_brand(db, ctx.workspace_id, campaign.product_id)
    truth = get_truth(db, campaign.product_id)

    ideas = plan_campaign_content(db, campaign=campaign, brand=brand, count=payload.count)
    created: list[Content] = []
    for idea in ideas:
        content = Content(
            workspace_id=ctx.workspace_id, product_id=campaign.product_id, idea=idea["idea"],
            content_type=idea["content_type"], origin=idea["origin"], campaign_id=campaign.id,
        )
        db.add(content)
        db.flush()
        generate_and_gate_variants(db, content=content, brand=brand, truth=truth, channels=["linkedin", "x"], cta_hint=idea["cta_hint"])
        created.append(content)

    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="campaign_content_generated", resource_type="campaign", resource_id=str(campaign.id),
        metadata={"ideas_generated": len(created)},
    )
    db.commit()
    for content in created:
        db.refresh(content)
        _ = content.variants
    return created


@router.get("/{campaign_id}/metrics", response_model=list[CampaignMetricResponse])
def list_metrics(campaign_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    _get_campaign_or_404(db, campaign_id, ctx.workspace_id)
    return db.execute(select(CampaignMetric).where(CampaignMetric.campaign_id == campaign_id).order_by(CampaignMetric.metric_date.desc())).scalars().all()


@router.post("/{campaign_id}/metrics", response_model=CampaignMetricResponse, status_code=201)
def add_metric(
    campaign_id: uuid.UUID,
    payload: CampaignMetricCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    _get_campaign_or_404(db, campaign_id, ctx.workspace_id)
    metric = CampaignMetric(campaign_id=campaign_id, **payload.model_dump())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric
