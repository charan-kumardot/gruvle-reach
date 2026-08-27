from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import WorkspaceContext, require_workspace_member
from app.db.models.action import Action
from app.db.models.company import Company
from app.db.models.enums import ActionStatus, OutreachMessageStatus, PipelineStage
from app.db.models.investor import InvestorMatch
from app.db.models.opportunity import Opportunity
from app.db.models.outreach import Outreach, OutreachMessage
from app.db.session import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}/analytics", tags=["analytics"])


@router.get("/dashboard")
def dashboard(ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)], db: Annotated[Session, Depends(get_db)]):
    def count(stmt) -> int:
        return db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    qualified_prospects = count(
        select(Company.id).where(Company.workspace_id == ctx.workspace_id, Company.icp_fit_score >= 75)
    )
    outreach_sent = count(
        select(OutreachMessage.id)
        .join(Outreach, Outreach.id == OutreachMessage.outreach_id)
        .where(Outreach.workspace_id == ctx.workspace_id, OutreachMessage.status == OutreachMessageStatus.SENT)
    )
    outreach_replied = count(
        select(Outreach.id).where(Outreach.workspace_id == ctx.workspace_id, Outreach.status == PipelineStage.REPLIED)
    )
    meetings = count(
        select(Outreach.id).where(Outreach.workspace_id == ctx.workspace_id, Outreach.status == PipelineStage.MEETING)
    )
    customers_won = count(
        select(Outreach.id).where(Outreach.workspace_id == ctx.workspace_id, Outreach.status == PipelineStage.WON)
    )
    investor_conversations = count(
        select(InvestorMatch.id).where(InvestorMatch.workspace_id == ctx.workspace_id, InvestorMatch.fit_score >= 70)
    )
    open_opportunities = count(
        select(Opportunity.id).where(Opportunity.workspace_id == ctx.workspace_id, Opportunity.status == "open")
    )
    actions_today = count(
        select(Action.id).where(Action.workspace_id == ctx.workspace_id, Action.status == ActionStatus.TODAY)
    )

    return {
        "qualified_prospects": qualified_prospects,
        "outreach_sent": outreach_sent,
        "outreach_replied": outreach_replied,
        "meetings": meetings,
        "customers_won": customers_won,
        "investor_conversations": investor_conversations,
        "open_opportunities": open_opportunities,
        "actions_today": actions_today,
    }
