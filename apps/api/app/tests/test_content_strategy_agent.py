"""Daily content planner (§2-5) — must stay bounded (MAX_DAILY_CONTENT_ITEMS)
and must never let a reactive/competitive-response opportunity into the
fully-autonomous plan; those only ever surface via a manual trigger."""
import uuid

import pytest

from app.agents.content_strategy_agent import MAX_DAILY_CONTENT_ITEMS, plan_campaign_content, plan_daily_content
from app.db.models.campaign import Campaign
from app.db.models.enums import OpportunityType
from app.db.models.opportunity import Opportunity
from app.db.models.product import BrandBrain, Product
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


def _make_opportunity(db, workspace_id, product_id, *, title, related_entity_type="") -> Opportunity:
    opp = Opportunity(
        workspace_id=workspace_id, product_id=product_id, type=OpportunityType.CONTENT,
        title=title, description="test", related_entity_type=related_entity_type, status="open",
    )
    db.add(opp)
    db.flush()
    return opp


def test_plan_is_bounded_by_max_daily_content_items(db, workspace_and_product):
    workspace, product = workspace_and_product
    for i in range(10):
        _make_opportunity(db, workspace.id, product.id, title=f"Opportunity {i}")

    ideas = plan_daily_content(db, workspace_id=workspace.id, product_id=product.id, brand=None)
    assert len(ideas) <= MAX_DAILY_CONTENT_ITEMS
    db.rollback()


def test_reactive_competitive_opportunities_are_excluded_from_autonomous_plan(db, workspace_and_product):
    workspace, product = workspace_and_product
    reactive = _make_opportunity(db, workspace.id, product.id, title="Competitor launched a new feature", related_entity_type="competitor_change")
    normal = _make_opportunity(db, workspace.id, product.id, title="Industry trend worth covering")

    ideas = plan_daily_content(db, workspace_id=workspace.id, product_id=product.id, brand=None)
    used_opportunity_ids = {idea["source_opportunity_id"] for idea in ideas}
    assert reactive.id not in used_opportunity_ids
    assert normal.id in used_opportunity_ids
    db.rollback()


def test_falls_back_to_brand_key_messages_when_no_opportunities_or_insights(db, workspace_and_product):
    workspace, product = workspace_and_product
    brand = BrandBrain(workspace_id=workspace.id, product_id=product.id, key_messages=["We help teams ship faster", "Built for founders"])
    db.add(brand)
    db.flush()

    ideas = plan_daily_content(db, workspace_id=workspace.id, product_id=product.id, brand=brand)
    assert len(ideas) > 0
    assert all(idea["idea"] in brand.key_messages for idea in ideas)
    db.rollback()


def test_plan_returns_empty_when_no_signal_at_all(db, workspace_and_product):
    workspace, product = workspace_and_product
    ideas = plan_daily_content(db, workspace_id=workspace.id, product_id=product.id, brand=None)
    assert ideas == []


def test_campaign_plan_is_bounded_by_requested_count(db, workspace_and_product):
    workspace, product = workspace_and_product
    campaign = Campaign(workspace_id=workspace.id, product_id=product.id, name="Launch", goal="signups")
    db.add(campaign)
    db.flush()

    ideas = plan_campaign_content(db, campaign=campaign, brand=None, count=3)
    assert len(ideas) == 3
    assert all(idea["origin"] == "campaign" for idea in ideas)
    db.rollback()
