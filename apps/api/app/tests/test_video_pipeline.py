"""create_pending_video/render_video_into_row split (§8-10) — the HTTP
router needs to return a RENDERING row fast and do the real work in a
background thread with its own session, since Render's free-tier CPU is
slow enough that doing it inline routinely timed out the request (observed
live against production, see the video_pipeline.py module docstring)."""
import uuid

import pytest

import datetime as dt

from app.agents.video_pipeline import STALE_RENDER_MINUTES, create_pending_video, mark_stale_renders_failed, render_video_into_row
from app.db.models.enums import VideoStatus
from app.db.models.product import Product
from app.db.models.tenancy import Organization, Workspace


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
    db.flush()
    yield workspace, product
    db.rollback()


def test_create_pending_video_is_fast_and_committed(db, workspace_and_product):
    workspace, product = workspace_and_product
    video = create_pending_video(db, workspace_id=workspace.id, product_id=product.id, content_variant_id=None, aspect_ratio="9:16")

    assert video.status == VideoStatus.RENDERING
    assert video.storage_url == ""
    assert video.id is not None  # committed, so a separate session/poller can see it
    db.rollback()


def test_render_video_into_row_handles_missing_video_gracefully(db):
    # Should not raise even if the row was somehow deleted between creation
    # and the background thread picking it up.
    render_video_into_row(db, video_id=uuid.uuid4(), idea="test", brand=None, truth=None)


def test_stale_render_is_marked_failed(db, workspace_and_product):
    """A row stuck at RENDERING (e.g. the container restarted mid-render,
    silently killing the background thread — observed live against
    Render's free tier) must self-heal to FAILED once it's stale enough,
    rather than a poller waiting on it forever."""
    workspace, product = workspace_and_product
    video = create_pending_video(db, workspace_id=workspace.id, product_id=product.id, content_variant_id=None, aspect_ratio="9:16")
    video.updated_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=STALE_RENDER_MINUTES + 1)
    db.commit()

    count = mark_stale_renders_failed(db, workspace_id=workspace.id)

    assert count == 1
    db.refresh(video)
    assert video.status == VideoStatus.FAILED
    assert "restarted" in video.render_log


def test_fresh_render_is_not_marked_failed(db, workspace_and_product):
    workspace, product = workspace_and_product
    video = create_pending_video(db, workspace_id=workspace.id, product_id=product.id, content_variant_id=None, aspect_ratio="9:16")

    count = mark_stale_renders_failed(db, workspace_id=workspace.id)

    assert count == 0
    db.refresh(video)
    assert video.status == VideoStatus.RENDERING
