import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.chief_growth_agent import generate_daily_actions, get_daily_brief
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.action import Action, ActionRun
from app.db.models.enums import ActionStatus, OrgRole
from app.db.session import get_db
from app.schemas.action import ActionResponse, ActionStatusUpdateRequest

router = APIRouter(prefix="/workspaces/{workspace_id}/actions", tags=["actions"])


@router.get("", response_model=list[ActionResponse])
def list_actions(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    status: ActionStatus | None = None,
    product_id: uuid.UUID | None = None,
):
    stmt = select(Action).where(Action.workspace_id == ctx.workspace_id)
    if status:
        stmt = stmt.where(Action.status == status)
    if product_id:
        stmt = stmt.where(Action.product_id == product_id)
    return db.execute(stmt.order_by(Action.expected_value_score.desc())).scalars().all()


@router.get("/daily-brief", response_model=list[ActionResponse])
def daily_brief(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
):
    actions = get_daily_brief(db, workspace_id=ctx.workspace_id, product_id=product_id)
    db.commit()
    for a in actions:
        db.refresh(a)
    return actions


@router.post("/refresh", response_model=list[ActionResponse])
def refresh_actions(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
    product_id: uuid.UUID,
):
    actions = generate_daily_actions(db, workspace_id=ctx.workspace_id, product_id=product_id)
    db.commit()
    for a in actions:
        db.refresh(a)
    return actions


@router.patch("/{action_id}/status", response_model=ActionResponse)
def update_action_status(
    action_id: uuid.UUID,
    payload: ActionStatusUpdateRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    action = db.get(Action, action_id)
    if action is None or action.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Action not found")
    action.status = payload.status
    db.commit()
    db.refresh(action)
    return action


@router.post("/{action_id}/approve", response_model=ActionResponse)
def approve_action(
    action_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    action = db.get(Action, action_id)
    if action is None or action.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Action not found")

    run = ActionRun(action_id=action.id, status="approved", executed_by=ctx.user.id, executed_at=dt.datetime.now(dt.timezone.utc))
    db.add(run)
    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="action_approved", resource_type="action", resource_id=str(action.id),
    )
    db.commit()
    db.refresh(action)
    return action


@router.post("/{action_id}/complete", response_model=ActionResponse)
def complete_action(
    action_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    action = db.get(Action, action_id)
    if action is None or action.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Action not found")
    action.status = ActionStatus.COMPLETED
    db.commit()
    db.refresh(action)
    return action
