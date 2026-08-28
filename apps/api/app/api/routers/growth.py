import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.learning_agent import run_learning_analysis
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.enums import LearningInsightStatus, OrgRole
from app.db.models.growth import LearningInsight
from app.db.session import get_db
from app.schemas.growth import LearningInsightResponse

router = APIRouter(prefix="/workspaces/{workspace_id}/learning-insights", tags=["growth"])


@router.get("", response_model=list[LearningInsightResponse])
def list_learning_insights(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    status: LearningInsightStatus | None = None,
):
    stmt = select(LearningInsight).where(LearningInsight.workspace_id == ctx.workspace_id)
    if status:
        stmt = stmt.where(LearningInsight.status == status)
    return db.execute(stmt.order_by(LearningInsight.confidence.desc())).scalars().all()


@router.post("/analyze", response_model=list[LearningInsightResponse])
def analyze(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
):
    """Deterministic — no AI call, no cost. Only ever surfaces an insight
    once the minimum sample size is met (§24's anti-overfitting requirement)."""
    insights = run_learning_analysis(db, workspace_id=ctx.workspace_id, product_id=product_id)
    db.commit()
    for insight in insights:
        db.refresh(insight)
    return insights


@router.post("/{insight_id}/accept", response_model=LearningInsightResponse)
def accept_insight(
    insight_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    insight = db.get(LearningInsight, insight_id)
    if insight is None or insight.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight.status = LearningInsightStatus.ACCEPTED
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="learning_insight_accepted", resource_type="learning_insight", resource_id=str(insight.id),
    )
    db.commit()
    db.refresh(insight)
    return insight


@router.post("/{insight_id}/ignore", response_model=LearningInsightResponse)
def ignore_insight(
    insight_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    insight = db.get(LearningInsight, insight_id)
    if insight is None or insight.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Insight not found")
    insight.status = LearningInsightStatus.IGNORED
    db.commit()
    db.refresh(insight)
    return insight
