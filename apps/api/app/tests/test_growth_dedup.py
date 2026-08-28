"""Research memory (§23) and investor dedup — both must short-circuit
before any network/AI call, so these are cheap, fast, offline-safe tests."""
import datetime as dt
import uuid

import pytest

from app.db.models.investor import Investor
from app.db.models.research import Evidence
from app.db.models.tenancy import Organization, Workspace
from app.providers.search.base import SearchResult
from app.research.evidence import recent_evidence_exists


@pytest.fixture
def workspace(db):
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    ws = Workspace(organization_id=org.id, name="Test WS", slug="test")
    db.add(ws)
    db.flush()
    yield ws
    db.rollback()


def test_recent_evidence_exists_true_within_window(db, workspace):
    db.add(Evidence(
        workspace_id=workspace.id, claim="c", source_url="https://example.com/a", evidence_snippet="",
        source_type="webpage", confidence=0.5, retrieved_at=dt.datetime.now(dt.timezone.utc), content_hash="x",
    ))
    db.flush()
    assert recent_evidence_exists(db, workspace_id=workspace.id, source_url="https://example.com/a", max_age_days=7) is True
    db.rollback()


def test_recent_evidence_exists_false_outside_window(db, workspace):
    stale = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=30)
    db.add(Evidence(
        workspace_id=workspace.id, claim="c", source_url="https://example.com/b", evidence_snippet="",
        source_type="webpage", confidence=0.5, retrieved_at=stale, content_hash="x",
    ))
    db.flush()
    assert recent_evidence_exists(db, workspace_id=workspace.id, source_url="https://example.com/b", max_age_days=7) is False
    db.rollback()


def test_recent_evidence_exists_false_for_unseen_url(db, workspace):
    assert recent_evidence_exists(db, workspace_id=workspace.id, source_url="https://example.com/never-seen", max_age_days=7) is False


class _FixedSearchProvider:
    name = "fixed"

    def __init__(self, results):
        self._results = results

    def configured(self):
        return True

    def search(self, query, *, max_results=10):
        return self._results[:max_results]


class _NeverCalledAIProvider:
    name = "unused"

    def configured(self):
        return True

    def generate_json(self, **kwargs):
        raise AssertionError("AI must not be called for an already-known investor URL")

    def generate_text(self, **kwargs):
        raise AssertionError("AI must not be called")


def test_investor_discovery_skips_already_known_website(db):
    from app.agents.investor_discovery_agent import InvestorDiscoveryAgent
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

    known_url = f"https://known-fund-{uuid.uuid4().hex[:8]}.example.com"
    db.add(Investor(fund_name="Already Known Ventures", website=known_url, source_url=known_url))
    db.flush()

    search = _FixedSearchProvider([SearchResult(title="Already Known Ventures", url=known_url, snippet="", source_type="webpage")])
    agent = InvestorDiscoveryAgent(db, _NeverCalledAIProvider(), search)

    discovered = agent.discover_investors(workspace_id=workspace.id, product=product, profile=None, queries=["irrelevant query"])
    assert discovered == []  # skipped before any AI call — AssertionError above would have failed the test otherwise
    db.rollback()
