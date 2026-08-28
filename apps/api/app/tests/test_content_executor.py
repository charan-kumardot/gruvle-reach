"""Content variant must be APPROVED/SCHEDULED before it can be published —
the agent/planner layer never calls SocialProvider directly (§19-20,
§38-39). Mirrors test_approval_gate.py's shape for the email executor."""
import uuid

import pytest

from app.actions.content_executor import ApprovalRequiredError, publish_content_variant
from app.core.security import hash_password
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import ContentStatus, OrgRole
from app.db.models.product import Product
from app.db.models.tenancy import Organization, User, Workspace
from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class _FakeSocialProvider(SocialProvider):
    name = "fake"

    def __init__(self, result: PublishResult):
        self._result = result

    def configured(self):
        return True

    def capabilities(self):
        return SocialCapabilities()

    def authorize_url(self, *, state, redirect_uri):
        return None

    def publish_post(self, *, access_token, body, media_urls=None):
        return self._result


@pytest.fixture
def workspace_and_variant(db):
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
    content = Content(workspace_id=workspace.id, product_id=product.id, idea="Test idea")
    db.add(content)
    db.flush()
    variant = ContentVariant(content_id=content.id, channel="linkedin", body="Test post", status=ContentStatus.APPROVED)
    db.add(variant)
    db.flush()
    yield workspace, content, variant, user
    db.rollback()


def test_draft_variant_cannot_be_published(db, workspace_and_variant):
    workspace, content, variant, user = workspace_and_variant
    variant.status = ContentStatus.DRAFT

    with pytest.raises(ApprovalRequiredError):
        publish_content_variant(
            db, variant=variant, content=content, approver_role=OrgRole.OWNER, approver_id=user.id,
            organization_id=workspace.organization_id, workspace_id=workspace.id,
            social_provider=_FakeSocialProvider(PublishResult(status="published")), access_token="tok",
        )


def test_viewer_role_cannot_publish(db, workspace_and_variant):
    workspace, content, variant, user = workspace_and_variant

    with pytest.raises(PermissionError):
        publish_content_variant(
            db, variant=variant, content=content, approver_role=OrgRole.VIEWER, approver_id=user.id,
            organization_id=workspace.organization_id, workspace_id=workspace.id,
            social_provider=_FakeSocialProvider(PublishResult(status="published")), access_token="tok",
        )


def test_manual_action_required_leaves_status_unchanged(db, workspace_and_variant):
    workspace, content, variant, user = workspace_and_variant

    publish_content_variant(
        db, variant=variant, content=content, approver_role=OrgRole.OWNER, approver_id=user.id,
        organization_id=workspace.organization_id, workspace_id=workspace.id,
        social_provider=_FakeSocialProvider(PublishResult(status="manual_action_required")), access_token="",
    )
    assert variant.status == ContentStatus.APPROVED  # unchanged, never silently marked published or failed


def test_successful_publish_marks_published(db, workspace_and_variant):
    workspace, content, variant, user = workspace_and_variant

    publish_content_variant(
        db, variant=variant, content=content, approver_role=OrgRole.OWNER, approver_id=user.id,
        organization_id=workspace.organization_id, workspace_id=workspace.id,
        social_provider=_FakeSocialProvider(PublishResult(status="published", external_id="123")), access_token="tok",
    )
    assert variant.status == ContentStatus.PUBLISHED
    assert variant.published_at is not None


def test_failed_publish_marks_failed_with_reason(db, workspace_and_variant):
    workspace, content, variant, user = workspace_and_variant

    publish_content_variant(
        db, variant=variant, content=content, approver_role=OrgRole.OWNER, approver_id=user.id,
        organization_id=workspace.organization_id, workspace_id=workspace.id,
        social_provider=_FakeSocialProvider(PublishResult(status="failed", message="API error 500")), access_token="tok",
    )
    assert variant.status == ContentStatus.FAILED
    assert variant.rejected_reason == "API error 500"
