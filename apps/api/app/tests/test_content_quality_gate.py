"""Content quality/anti-spam gate (§28-29) — the deterministic layer must
catch duplicates, length violations, forbidden words, and unsupported
claims before any AI call happens; the AI layer only runs once the
deterministic layer has already passed."""
import uuid

import pytest

from app.agents.content_quality_gate import run_quality_gate
from app.db.models.content import Content, ContentVariant
from app.db.models.product import BrandBrain
from app.db.models.tenancy import Organization, Workspace


@pytest.fixture
def workspace_and_product(db):
    from app.db.models.product import Product

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


def _make_content(db, workspace_id, product_id, idea="Some idea") -> Content:
    content = Content(workspace_id=workspace_id, product_id=product_id, idea=idea)
    db.add(content)
    db.flush()
    return content


def _make_variant(db, content_id, *, channel="x", body="") -> ContentVariant:
    variant = ContentVariant(content_id=content_id, channel=channel, body=body)
    db.add(variant)
    db.flush()
    return variant


class _NeverCalledAIProvider:
    name = "unused"

    def configured(self):
        return True

    def generate_json(self, **kwargs):
        raise AssertionError("AI must not be called once the deterministic layer already failed")

    def generate_text(self, **kwargs):
        raise AssertionError("AI must not be called")


def test_exact_duplicate_is_blocked(db, workspace_and_product):
    workspace, product = workspace_and_product
    existing_content = _make_content(db, workspace.id, product.id)
    _make_variant(db, existing_content.id, channel="x", body="Your API didn't break. It changed.")

    new_content = _make_content(db, workspace.id, product.id)
    new_variant = _make_variant(db, new_content.id, channel="x", body="Your API didn't break. It changed.")

    result = run_quality_gate(db, variant=new_variant, content=new_content, brand=None, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is False
    assert any("uplicate" in r for r in result.blocking_reasons)
    db.rollback()


def test_near_duplicate_is_blocked(db, workspace_and_product):
    workspace, product = workspace_and_product
    existing_content = _make_content(db, workspace.id, product.id)
    _make_variant(db, existing_content.id, channel="linkedin", body="Small changes in your dependencies can create large downstream problems for your product.")

    new_content = _make_content(db, workspace.id, product.id)
    new_variant = _make_variant(db, new_content.id, channel="linkedin", body="Small changes in your dependencies can create large downstream problems for your business.")

    result = run_quality_gate(db, variant=new_variant, content=new_content, brand=None, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is False
    db.rollback()


def test_different_channel_is_not_considered_a_duplicate(db, workspace_and_product):
    workspace, product = workspace_and_product
    existing_content = _make_content(db, workspace.id, product.id)
    _make_variant(db, existing_content.id, channel="linkedin", body="Identical text on a different channel.")

    new_content = _make_content(db, workspace.id, product.id)
    new_variant = _make_variant(db, new_content.id, channel="x", body="Identical text on a different channel.")

    result = run_quality_gate(db, variant=new_variant, content=new_content, brand=None, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is True
    db.rollback()


def test_platform_length_limit_is_enforced(db, workspace_and_product):
    workspace, product = workspace_and_product
    content = _make_content(db, workspace.id, product.id)
    variant = _make_variant(db, content.id, channel="x", body="x" * 281)

    result = run_quality_gate(db, variant=variant, content=content, brand=None, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is False
    assert any("280" in r for r in result.blocking_reasons)
    db.rollback()


def test_forbidden_word_is_blocked(db, workspace_and_product):
    workspace, product = workspace_and_product
    brand = BrandBrain(workspace_id=workspace.id, product_id=product.id, words_to_avoid=["guaranteed"])
    db.add(brand)
    db.flush()
    content = _make_content(db, workspace.id, product.id)
    variant = _make_variant(db, content.id, channel="linkedin", body="This is guaranteed to work every time.")

    result = run_quality_gate(db, variant=variant, content=content, brand=brand, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is False
    assert any("guaranteed" in r for r in result.blocking_reasons)
    db.rollback()


def test_unsupported_certification_claim_is_blocked(db, workspace_and_product):
    workspace, product = workspace_and_product
    brand = BrandBrain(workspace_id=workspace.id, product_id=product.id, claims=[], proof_points=[])
    db.add(brand)
    db.flush()
    content = _make_content(db, workspace.id, product.id)
    variant = _make_variant(db, content.id, channel="linkedin", body="We are SOC 2 certified and trusted by thousands of customers.")

    result = run_quality_gate(db, variant=variant, content=content, brand=brand, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is False
    db.rollback()


def test_certification_claim_allowed_when_in_approved_proof_points(db, workspace_and_product):
    workspace, product = workspace_and_product
    brand = BrandBrain(workspace_id=workspace.id, product_id=product.id, claims=[], proof_points=["SOC 2 certified since 2025"])
    db.add(brand)
    db.flush()
    content = _make_content(db, workspace.id, product.id)
    variant = _make_variant(db, content.id, channel="linkedin", body="We are SOC 2 certified.")

    result = run_quality_gate(db, variant=variant, content=content, brand=brand, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is True
    db.rollback()


def test_clean_content_passes_without_brand_or_truth(db, workspace_and_product):
    workspace, product = workspace_and_product
    content = _make_content(db, workspace.id, product.id)
    variant = _make_variant(db, content.id, channel="linkedin", body="A normal, honest post about our product.")

    result = run_quality_gate(db, variant=variant, content=content, brand=None, truth=None, ai_provider=_NeverCalledAIProvider())
    assert result.passed is True
    db.rollback()
