"""An outreach message must be APPROVED before it can be sent — the LLM/agent
layer never sends directly (§25, §67, §70)."""
import uuid

import pytest

from app.actions.executor import ApprovalRequiredError, send_outreach_email
from app.db.models.enums import OrgRole, OutreachMessageStatus, PipelineStage
from app.db.models.outreach import Outreach, OutreachMessage
from app.core.security import hash_password
from app.db.models.product import Product
from app.db.models.tenancy import Organization, User, Workspace
from app.providers.email.disabled_provider import DisabledEmailProvider


class _FakeSuccessEmailProvider:
    name = "fake"

    def configured(self):
        return True

    def send(self, *, to, subject, html_body, text_body=""):
        from app.providers.email.base import EmailSendResult

        return EmailSendResult(success=True, provider_message_id="fake-123")


@pytest.fixture
def workspace_and_product(db):
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    workspace = Workspace(organization_id=org.id, name="Test WS", slug="test")
    db.add(workspace)
    db.flush()
    product = Product(workspace_id=workspace.id, name="Test Product")
    db.add(product)
    user = User(email=f"approver-{uuid.uuid4().hex[:10]}@example.com", password_hash=hash_password("testpassword123"))
    db.add(user)
    db.flush()
    yield workspace, product, user
    db.rollback()


def test_unapproved_message_cannot_be_sent(db, workspace_and_product):
    workspace, product, user = workspace_and_product
    outreach = Outreach(
        workspace_id=workspace.id, product_id=product.id, target_type="company", target_id=uuid.uuid4(), status=PipelineStage.DRAFTED
    )
    db.add(outreach)
    db.flush()
    message = OutreachMessage(outreach_id=outreach.id, draft_body="Hello", status=OutreachMessageStatus.DRAFTED)
    db.add(message)
    db.flush()

    with pytest.raises(ApprovalRequiredError):
        send_outreach_email(
            db,
            message=message,
            outreach=outreach,
            to_email="someone@example.com",
            subject="Hi",
            approver_role=OrgRole.OWNER,
            approver_id=user.id,
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            email_provider=_FakeSuccessEmailProvider(),
        )


def test_viewer_role_cannot_send_even_if_approved(db, workspace_and_product):
    workspace, product, user = workspace_and_product
    outreach = Outreach(
        workspace_id=workspace.id, product_id=product.id, target_type="company", target_id=uuid.uuid4(), status=PipelineStage.APPROVED
    )
    db.add(outreach)
    db.flush()
    message = OutreachMessage(outreach_id=outreach.id, draft_body="Hello", status=OutreachMessageStatus.APPROVED)
    db.add(message)
    db.flush()

    with pytest.raises(PermissionError):
        send_outreach_email(
            db,
            message=message,
            outreach=outreach,
            to_email="someone@example.com",
            subject="Hi",
            approver_role=OrgRole.VIEWER,
            approver_id=user.id,
            organization_id=workspace.organization_id,
            workspace_id=workspace.id,
            email_provider=_FakeSuccessEmailProvider(),
        )


def test_approved_message_sends_and_marks_sent(db, workspace_and_product):
    workspace, product, user = workspace_and_product
    outreach = Outreach(
        workspace_id=workspace.id, product_id=product.id, target_type="company", target_id=uuid.uuid4(), status=PipelineStage.APPROVED
    )
    db.add(outreach)
    db.flush()
    message = OutreachMessage(outreach_id=outreach.id, draft_body="Hello", status=OutreachMessageStatus.APPROVED)
    db.add(message)
    db.flush()

    send_outreach_email(
        db,
        message=message,
        outreach=outreach,
        to_email="someone@example.com",
        subject="Hi",
        approver_role=OrgRole.OWNER,
        approver_id=user.id,
        organization_id=workspace.organization_id,
        workspace_id=workspace.id,
        email_provider=_FakeSuccessEmailProvider(),
    )
    assert message.status == OutreachMessageStatus.SENT


def test_disabled_email_provider_never_pretends_to_send():
    result = DisabledEmailProvider().send(to="x@example.com", subject="s", html_body="b")
    assert result.success is False
