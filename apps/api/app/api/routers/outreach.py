import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.actions.executor import ApprovalRequiredError, send_outreach_email
from app.actions.policy import can_approve
from app.agents.outreach_agent import OutreachAgent
from app.core.audit import record_audit
from app.core.deps import WorkspaceContext, require_workspace_member, require_workspace_role
from app.db.models.company import Company, CompanyTrigger
from app.db.models.enums import OrgRole, OutreachMessageStatus, PipelineStage
from app.db.models.outreach import Outreach, OutreachMessage
from app.db.models.product import Product
from app.db.session import get_db
from app.providers.ai.factory import get_ai_provider
from app.providers.email.factory import get_email_provider
from app.schemas.outreach import OutreachDraftRequest, OutreachResponse, OutreachSendRequest

router = APIRouter(prefix="/workspaces/{workspace_id}/outreach", tags=["outreach"])


@router.get("", response_model=list[OutreachResponse])
def list_outreach(
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
    status: PipelineStage | None = None,
):
    stmt = select(Outreach).where(Outreach.workspace_id == ctx.workspace_id)
    if status:
        stmt = stmt.where(Outreach.status == status)
    rows = db.execute(stmt.order_by(Outreach.created_at.desc())).scalars().all()
    for r in rows:
        _ = r.messages
    return rows


@router.post("/draft", response_model=OutreachResponse)
def draft_outreach(
    payload: OutreachDraftRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_role(OrgRole.MEMBER))],
    db: Annotated[Session, Depends(get_db)],
):
    product = db.get(Product, payload.product_id)
    if product is None or product.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Product not found")

    if payload.target_type != "company":
        raise HTTPException(status_code=400, detail="Only 'company' targets are supported for AI drafting in this build")

    company = db.get(Company, payload.target_id)
    if company is None or company.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="Company not found")

    trigger = db.get(CompanyTrigger, payload.trigger_id) if payload.trigger_id else None

    outreach = Outreach(
        workspace_id=ctx.workspace_id,
        product_id=payload.product_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        channel=payload.channel,
        status=PipelineStage.DRAFTED,
    )
    db.add(outreach)
    db.flush()

    agent = OutreachAgent(db, get_ai_provider())
    output = agent.draft_message(product=product, company=company, trigger=trigger)
    if output is None:
        raise HTTPException(status_code=503, detail="AI provider unavailable or returned an unparseable response.")

    message = OutreachMessage(
        outreach_id=outreach.id,
        draft_body=output.get("message", ""),
        personalization_evidence=[
            {"field": "why_contacting", "value": output.get("why_contacting", "")},
            {"field": "relevant_observation", "value": output.get("relevant_observation", "")},
            {"field": "value_proposition", "value": output.get("value_proposition", "")},
            {"field": "cta", "value": output.get("cta", "")},
        ],
        status=OutreachMessageStatus.DRAFTED,
    )
    db.add(message)
    db.commit()
    db.refresh(outreach)
    _ = outreach.messages
    return outreach


@router.post("/{outreach_id}/messages/{message_id}/approve", response_model=OutreachResponse)
def approve_message(
    outreach_id: uuid.UUID,
    message_id: uuid.UUID,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
):
    if not can_approve(ctx.role):
        raise HTTPException(status_code=403, detail="Your role cannot approve outreach")

    outreach = db.get(Outreach, outreach_id)
    message = db.get(OutreachMessage, message_id)
    if outreach is None or outreach.workspace_id != ctx.workspace_id or message is None or message.outreach_id != outreach_id:
        raise HTTPException(status_code=404, detail="Outreach message not found")

    message.status = OutreachMessageStatus.APPROVED
    message.approved_by = ctx.user.id
    message.approved_at = dt.datetime.now(dt.timezone.utc)
    outreach.status = PipelineStage.APPROVED

    record_audit(
        db, organization_id=ctx.organization_id, workspace_id=ctx.workspace_id, user_id=ctx.user.id,
        action="outreach_message_approved", resource_type="outreach_message", resource_id=str(message.id),
    )
    db.commit()
    db.refresh(outreach)
    _ = outreach.messages
    return outreach


@router.post("/{outreach_id}/messages/{message_id}/send", response_model=OutreachResponse)
def send_message(
    outreach_id: uuid.UUID,
    message_id: uuid.UUID,
    payload: OutreachSendRequest,
    ctx: Annotated[WorkspaceContext, Depends(require_workspace_member)],
    db: Annotated[Session, Depends(get_db)],
):
    outreach = db.get(Outreach, outreach_id)
    message = db.get(OutreachMessage, message_id)
    if outreach is None or outreach.workspace_id != ctx.workspace_id or message is None or message.outreach_id != outreach_id:
        raise HTTPException(status_code=404, detail="Outreach message not found")

    try:
        send_outreach_email(
            db,
            message=message,
            outreach=outreach,
            to_email=payload.to_email,
            subject=payload.subject,
            approver_role=ctx.role,
            approver_id=ctx.user.id,
            organization_id=ctx.organization_id,
            workspace_id=ctx.workspace_id,
            email_provider=get_email_provider(),
        )
    except ApprovalRequiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if message.status == OutreachMessageStatus.SENT:
        outreach.status = PipelineStage.SENT

    db.commit()
    db.refresh(outreach)
    _ = outreach.messages
    return outreach
