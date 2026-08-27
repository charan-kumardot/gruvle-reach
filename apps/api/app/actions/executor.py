"""
Action executor (§70). The ONLY module in the codebase permitted to call
EmailProvider.send / SocialProvider.publish_post. Every call here is
preceded by an approval check and followed by an audit log entry — an LLM
or agent can recommend, but nothing in agents/ can reach this module
directly; only an authenticated, authorized API route can.
"""
import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.db.models.enums import OrgRole, OutreachMessageStatus
from app.db.models.outreach import Outreach, OutreachEvent, OutreachMessage
from app.providers.email.base import EmailProvider

from app.actions.policy import can_send


class ApprovalRequiredError(RuntimeError):
    pass


def send_outreach_email(
    db: Session,
    *,
    message: OutreachMessage,
    outreach: Outreach,
    to_email: str,
    subject: str,
    approver_role: OrgRole,
    approver_id: uuid.UUID,
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    email_provider: EmailProvider,
) -> OutreachEvent:
    if message.status != OutreachMessageStatus.APPROVED:
        raise ApprovalRequiredError("Outreach message must be APPROVED before it can be sent")
    if not can_send(approver_role):
        raise PermissionError("Role does not have permission to send outreach")

    result = email_provider.send(
        to=to_email,
        subject=subject,
        html_body=message.draft_body.replace("\n", "<br>"),
        text_body=message.draft_body,
    )

    now = dt.datetime.now(dt.timezone.utc)
    if result.success:
        message.status = OutreachMessageStatus.SENT
        message.sent_at = now
        outreach.status = outreach.status  # pipeline stage advanced by the caller/router, not here
        event = OutreachEvent(
            outreach_id=outreach.id,
            event_type="sent",
            occurred_at=now,
            event_metadata={"provider": email_provider.name, "provider_message_id": result.provider_message_id},
        )
    else:
        event = OutreachEvent(
            outreach_id=outreach.id,
            event_type="send_failed",
            occurred_at=now,
            event_metadata={"provider": email_provider.name, "error": result.error},
        )

    db.add(event)
    record_audit(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=approver_id,
        action="outreach_message_sent" if result.success else "outreach_message_send_failed",
        resource_type="outreach_message",
        resource_id=str(message.id),
        metadata={"provider": email_provider.name},
    )
    db.flush()
    return event
