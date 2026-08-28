"""Learning Engine anti-overfitting gate (§24: 'do not overfit small
datasets') — never surface an insight below the minimum sample size, never
duplicate a pending insight, and the confidence heuristic must be
monotonic and capped well short of certainty."""
import datetime as dt
import uuid

import pytest

from app.agents.learning_agent import (
    MIN_SAMPLE_SIZE,
    _confidence_for_sample,
    _upsert_insight,
    analyze_content_by_channel,
    analyze_outreach_by_industry,
)
from app.core.security import hash_password
from app.db.models.company import Company
from app.db.models.content import Content, ContentVariant
from app.db.models.enums import ContentStatus, OrgRole, PipelineStage
from app.db.models.outreach import Outreach
from app.db.models.product import Product
from app.db.models.tenancy import Organization, User, Workspace


def test_confidence_is_monotonic_and_capped():
    low = _confidence_for_sample(1)
    high = _confidence_for_sample(100)
    assert 0 < low < high <= 0.85


def test_upsert_insight_rejects_below_minimum_sample_size(db):
    result = _upsert_insight(
        db, workspace_id=uuid.uuid4(), product_id=uuid.uuid4(), dimension="industry",
        group_label="test group", group_rate=0.8, baseline_rate=0.1,
        sample_size=10, group_n=MIN_SAMPLE_SIZE - 1,
    )
    assert result is None


def test_upsert_insight_rejects_small_lift_even_with_enough_samples(db):
    result = _upsert_insight(
        db, workspace_id=uuid.uuid4(), product_id=uuid.uuid4(), dimension="industry",
        group_label="test group", group_rate=0.11, baseline_rate=0.10,  # lift ~1.1x, below the 1.3x bar
        sample_size=50, group_n=MIN_SAMPLE_SIZE,
    )
    assert result is None


def test_upsert_insight_accepts_meaningful_lift_at_minimum_sample_size(db):
    result = _upsert_insight(
        db, workspace_id=uuid.uuid4(), product_id=uuid.uuid4(), dimension="industry",
        group_label="AI SaaS companies", group_rate=0.4, baseline_rate=0.1,  # 4x lift
        sample_size=50, group_n=MIN_SAMPLE_SIZE,
    )
    assert result is not None
    assert result.sample_size == MIN_SAMPLE_SIZE
    assert result.result_summary["lift"] == pytest.approx(4.0)
    db.rollback()


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


def _make_company(db, workspace_id, product_id, industry: str) -> Company:
    company = Company(workspace_id=workspace_id, product_id=product_id, name=f"Co-{uuid.uuid4().hex[:6]}", industry=industry)
    db.add(company)
    db.flush()
    return company


def test_analyze_outreach_by_industry_needs_minimum_sample_per_group(db, workspace_and_product):
    workspace, product = workspace_and_product

    # Only 3 outreach records for "AI SaaS" — below MIN_SAMPLE_SIZE, must not surface.
    for i in range(3):
        company = _make_company(db, workspace.id, product.id, "AI SaaS")
        db.add(Outreach(
            workspace_id=workspace.id, product_id=product.id, target_type="company", target_id=company.id,
            status=PipelineStage.REPLIED if i == 0 else PipelineStage.SENT,
        ))
    db.flush()

    insights = analyze_outreach_by_industry(db, workspace_id=workspace.id, product_id=product.id)
    assert insights == []
    db.rollback()


def test_analyze_outreach_by_industry_surfaces_real_signal(db, workspace_and_product):
    workspace, product = workspace_and_product

    # "AI SaaS": 5/6 reply -> high rate. "Fintech": 1/6 reply -> low rate (baseline-dragging).
    for i in range(6):
        company = _make_company(db, workspace.id, product.id, "AI SaaS")
        db.add(Outreach(
            workspace_id=workspace.id, product_id=product.id, target_type="company", target_id=company.id,
            status=PipelineStage.REPLIED if i < 5 else PipelineStage.SENT,
        ))
    for i in range(6):
        company = _make_company(db, workspace.id, product.id, "Fintech")
        db.add(Outreach(
            workspace_id=workspace.id, product_id=product.id, target_type="company", target_id=company.id,
            status=PipelineStage.REPLIED if i < 1 else PipelineStage.SENT,
        ))
    db.flush()

    insights = analyze_outreach_by_industry(db, workspace_id=workspace.id, product_id=product.id)
    assert any("AI SaaS" in i.hypothesis for i in insights)
    db.rollback()


def _make_measured_variant(db, workspace_id, product_id, *, channel: str, impressions: int, engaged: int) -> ContentVariant:
    content = Content(workspace_id=workspace_id, product_id=product_id, idea="test idea")
    db.add(content)
    db.flush()
    variant = ContentVariant(
        content_id=content.id, channel=channel, body="test", status=ContentStatus.PUBLISHED,
        performance={"impressions": impressions, "likes": engaged, "comments": 0, "shares": 0},
    )
    db.add(variant)
    db.flush()
    return variant


def test_content_learning_needs_minimum_sample_per_channel(db, workspace_and_product):
    workspace, product = workspace_and_product

    # Only 3 measured LinkedIn variants — below MIN_SAMPLE_SIZE, must not surface.
    for _ in range(3):
        _make_measured_variant(db, workspace.id, product.id, channel="linkedin", impressions=100, engaged=50)
    for _ in range(3):
        _make_measured_variant(db, workspace.id, product.id, channel="x", impressions=100, engaged=1)

    insights = analyze_content_by_channel(db, workspace_id=workspace.id, product_id=product.id)
    assert insights == []
    db.rollback()


def test_content_learning_ignores_unmeasured_variants(db, workspace_and_product):
    workspace, product = workspace_and_product

    content = Content(workspace_id=workspace.id, product_id=product.id, idea="unmeasured")
    db.add(content)
    db.flush()
    for _ in range(10):
        db.add(ContentVariant(content_id=content.id, channel="linkedin", body="never published", status=ContentStatus.READY))
    db.flush()

    insights = analyze_content_by_channel(db, workspace_id=workspace.id, product_id=product.id)
    assert insights == []  # zero measured variants -> nothing to learn from, not treated as a 0% rate
    db.rollback()


def test_content_learning_surfaces_real_signal(db, workspace_and_product):
    workspace, product = workspace_and_product

    # LinkedIn: 50% engagement rate (high). X: ~2% engagement rate (low, baseline-dragging).
    for _ in range(6):
        _make_measured_variant(db, workspace.id, product.id, channel="linkedin", impressions=100, engaged=50)
    for _ in range(6):
        _make_measured_variant(db, workspace.id, product.id, channel="x", impressions=100, engaged=2)

    insights = analyze_content_by_channel(db, workspace_id=workspace.id, product_id=product.id)
    assert any("linkedin" in i.hypothesis for i in insights)
    db.rollback()
