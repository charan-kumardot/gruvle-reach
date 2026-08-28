"""Router-level behaviors that live in app/api/routers/content.py itself,
not in an agent or the executor: a hand-edit invalidates a prior approval
(§28), and publish-now never reaches the executor/provider for an
unconnected channel — structural, not exception-handled (§20, §38-39).
Calls the route functions directly (they're plain functions under the
FastAPI Depends() decorations) with a hand-built WorkspaceContext, the same
level of directness test_approval_gate.py uses for the email executor."""
import datetime as dt
import uuid

import pytest
from fastapi import HTTPException

from app.api.routers.content import approve_variant, publish_variant_now, update_variant
from app.core.deps import WorkspaceContext
from app.core.security import hash_password
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import ContentStatus, OrgRole
from app.db.models.product import Product
from app.db.models.tenancy import Organization, OrganizationMember, User, Workspace
from app.schemas.content import ContentVariantUpdateRequest


@pytest.fixture
def ctx_and_variant(db):
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    workspace = Workspace(organization_id=org.id, name="Test WS", slug="test")
    db.add(workspace)
    db.flush()
    user = User(email=f"member-{uuid.uuid4().hex[:10]}@example.com", password_hash=hash_password("testpassword123"))
    db.add(user)
    db.flush()
    membership = OrganizationMember(organization_id=org.id, user_id=user.id, role=OrgRole.MEMBER)
    db.add(membership)
    product = Product(workspace_id=workspace.id, name="Test Product")
    db.add(product)
    db.flush()
    content = Content(workspace_id=workspace.id, product_id=product.id, idea="Test idea")
    db.add(content)
    db.flush()
    variant = ContentVariant(
        content_id=content.id, channel="linkedin", body="Original approved text", status=ContentStatus.APPROVED,
        approved_by=user.id, approved_at=dt.datetime.now(dt.timezone.utc),
    )
    db.add(variant)
    db.flush()

    ctx = WorkspaceContext(workspace=workspace, membership=membership, user=user)
    yield ctx, variant
    db.rollback()


def test_editing_an_approved_variant_resets_it_to_draft(db, ctx_and_variant):
    ctx, variant = ctx_and_variant

    update_variant(variant.id, ContentVariantUpdateRequest(body="Edited text, changes the meaning"), ctx, db)

    assert variant.status == ContentStatus.DRAFT
    assert variant.approved_by is None
    assert variant.approved_at is None


def test_editing_status_only_does_not_reset_approval(db, ctx_and_variant):
    """A no-op / metadata-only PATCH (body unchanged) must not blow away a
    valid approval — only an actual body change should."""
    ctx, variant = ctx_and_variant

    update_variant(variant.id, ContentVariantUpdateRequest(body=variant.body), ctx, db)

    assert variant.status == ContentStatus.APPROVED
    assert variant.approved_by is not None


def test_publish_now_on_unconnected_channel_never_changes_status(db, ctx_and_variant):
    ctx, variant = ctx_and_variant
    original_status = variant.status

    result = publish_variant_now(variant.id, ctx, db)

    assert result["status"] == "manual_action_required"
    assert variant.status == original_status  # never touched — no executor/provider call happened


def test_approve_requires_ready_or_approval_required_status(db, ctx_and_variant):
    ctx, variant = ctx_and_variant
    variant.status = ContentStatus.DRAFT
    db.flush()

    with pytest.raises(HTTPException) as exc_info:
        approve_variant(variant.id, ctx, db)
    assert exc_info.value.status_code == 400


def test_approve_succeeds_from_ready(db, ctx_and_variant):
    ctx, variant = ctx_and_variant
    variant.status = ContentStatus.READY
    variant.approved_by = None
    variant.approved_at = None
    db.flush()

    approve_variant(variant.id, ctx, db)

    assert variant.status == ContentStatus.APPROVED
    assert variant.approved_by == ctx.user.id
