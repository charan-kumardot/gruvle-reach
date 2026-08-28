"""
Content executor (§19-20, §38-39). The ONLY module permitted to call
SocialProvider.publish_post for content. Mirrors app/actions/executor.py's
send_outreach_email pattern exactly: approval check first, action
performed, audit logged either way. Agents never reach SocialProvider
directly. Trusts the variant's READY/APPROVED gating rather than
re-running the AI validation layer here — same precedent as
git_executor.py, which doesn't re-validate either; a hand-edit after
approval is caught structurally by the PATCH route resetting status back
to DRAFT (see app/api/routers/content.py), not by re-checking here.
"""
import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.actions.policy import can_send
from app.core.audit import record_audit
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import ContentStatus, OrgRole
from app.providers.social.base import SocialProvider


class ApprovalRequiredError(RuntimeError):
    pass


def publish_content_variant(
    db: Session,
    *,
    variant: ContentVariant,
    content: Content,
    approver_role: OrgRole,
    approver_id: uuid.UUID,
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    social_provider: SocialProvider,
    access_token: str,
) -> ContentVariant:
    if variant.status not in (ContentStatus.APPROVED, ContentStatus.SCHEDULED):
        raise ApprovalRequiredError("Content variant must be APPROVED or SCHEDULED before it can be published")
    if not can_send(approver_role):
        raise PermissionError("Role does not have permission to publish content")

    result = social_provider.publish_post(access_token=access_token, body=variant.body, media_urls=variant.media_refs or None)

    now = dt.datetime.now(dt.timezone.utc)
    if result.status == "published":
        variant.status = ContentStatus.PUBLISHED
        variant.published_at = now
    elif result.status == "manual_action_required":
        pass  # left as-is — the router only reaches this executor for a
        # connected channel, so this path should rarely fire in practice
    else:
        variant.status = ContentStatus.FAILED
        variant.rejected_reason = result.message

    record_audit(
        db,
        organization_id=organization_id,
        workspace_id=workspace_id,
        user_id=approver_id,
        action="content_variant_published" if result.status == "published" else "content_variant_publish_failed",
        resource_type="content_variant",
        resource_id=str(variant.id),
        metadata={"provider": social_provider.name, "status": result.status},
    )
    db.flush()
    return variant
