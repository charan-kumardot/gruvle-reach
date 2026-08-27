import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.campaign import Campaign, CampaignChannel, CampaignMetric
from app.db.models.enums import OrgRole
from app.db.session import get_db
from app.schemas.campaign import (
    CampaignCreateRequest,
    CampaignMetricCreateRequest,
    CampaignMetricResponse,
    CampaignResponse,
)

router = APIRouter(prefix="/workspaces/{workspace_id}/campaigns", tags=["campaigns"])


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


@router.get("/{campaign_id}/metrics", response_model=list[CampaignMetricResponse])
def list_metrics(campaign_id: uuid.UUID, ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return db.execute(select(CampaignMetric).where(CampaignMetric.campaign_id == campaign_id).order_by(CampaignMetric.metric_date.desc())).scalars().all()


@router.post("/{campaign_id}/metrics", response_model=CampaignMetricResponse, status_code=201)
def add_metric(
    campaign_id: uuid.UUID,
    payload: CampaignMetricCreateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None or campaign.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Campaign not found")
    metric = CampaignMetric(campaign_id=campaign_id, **payload.model_dump())
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric
