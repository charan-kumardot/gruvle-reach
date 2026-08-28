"""Risk classifier and git-write approval gating (visibility spec §10, §27, §33)."""
import uuid

import pytest

from app.actions.git_executor import ApprovalRequiredError, CriticalRiskBlockedError, prepare_website_change
from app.agents.risk_classifier import classify_risk, is_auto_prepareable
from app.db.models.enums import OrgRole, RiskLevel, WebsiteChangeStatus
from app.core.security import hash_password
from app.db.models.tenancy import Organization, User, Workspace
from app.db.models.visibility import Website, WebsiteChange
from app.providers.git.mock_provider import MockGitProvider


@pytest.mark.parametrize(
    "path",
    [".env", ".env.production", "app/secrets/keys.py", "credentials.json", "id_rsa.pem",
     "app/auth/login.py", "billing/stripe.py", ".github/workflows/deploy.yml", "docker-compose.yml", "Dockerfile"],
)
def test_critical_paths_always_classified_critical(path):
    risk, _ = classify_risk(file_path=path, protected_patterns=[])
    assert risk == RiskLevel.CRITICAL


def test_protected_pattern_forces_critical_even_if_otherwise_low_risk():
    risk, reason = classify_risk(file_path="components/navigation/nav.tsx", protected_patterns=["*navigation*"])
    assert risk == RiskLevel.CRITICAL
    assert "protected" in reason.lower()


@pytest.mark.parametrize("path", ["public/robots.txt", "app/meta/schema.json", "public/manifest.json"])
def test_metadata_paths_classified_low(path):
    risk, _ = classify_risk(file_path=path, protected_patterns=[])
    assert risk == RiskLevel.LOW


@pytest.mark.parametrize("path", ["components/hero/hero.tsx", "components/pricing/table.tsx", "app/layout.tsx"])
def test_ui_paths_classified_high(path):
    risk, _ = classify_risk(file_path=path, protected_patterns=[])
    assert risk == RiskLevel.HIGH


def test_only_low_and_medium_are_auto_prepareable():
    assert is_auto_prepareable(RiskLevel.LOW) is True
    assert is_auto_prepareable(RiskLevel.MEDIUM) is True
    assert is_auto_prepareable(RiskLevel.HIGH) is False
    assert is_auto_prepareable(RiskLevel.CRITICAL) is False


@pytest.fixture
def website_fixture(db):
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db.add(org)
    db.flush()
    workspace = Workspace(organization_id=org.id, name="Test WS", slug="test")
    db.add(workspace)
    db.flush()
    from app.db.models.product import Product

    product = Product(workspace_id=workspace.id, name="Test Product")
    db.add(product)
    db.flush()
    website = Website(
        workspace_id=workspace.id, product_id=product.id, name="Test Site", url="https://example.com",
        repository_owner="acme", repository_name="site", default_branch="main",
    )
    db.add(website)
    user = User(email=f"approver-{uuid.uuid4().hex[:10]}@example.com", password_hash=hash_password("testpassword123"))
    db.add(user)
    db.flush()
    yield workspace, website, user
    db.rollback()


def test_prepare_rejects_unapproved_change(db, website_fixture):
    workspace, website, user = website_fixture
    change = WebsiteChange(website_id=website.id, risk_level=RiskLevel.LOW, status=WebsiteChangeStatus.VALIDATED, files_changed=[])
    db.add(change)
    db.flush()

    with pytest.raises(ApprovalRequiredError):
        prepare_website_change(
            db, change=change, website=website, pr_title="t", pr_body="b",
            approver_role=OrgRole.OWNER, approver_id=user.id, organization_id=workspace.organization_id,
            workspace_id=workspace.id, git_provider=MockGitProvider(),
        )


def test_prepare_rejects_high_risk_even_if_approved(db, website_fixture):
    workspace, website, user = website_fixture
    change = WebsiteChange(website_id=website.id, risk_level=RiskLevel.HIGH, status=WebsiteChangeStatus.APPROVED, files_changed=[])
    db.add(change)
    db.flush()

    with pytest.raises(CriticalRiskBlockedError):
        prepare_website_change(
            db, change=change, website=website, pr_title="t", pr_body="b",
            approver_role=OrgRole.OWNER, approver_id=user.id, organization_id=workspace.organization_id,
            workspace_id=workspace.id, git_provider=MockGitProvider(),
        )


def test_prepare_rejects_critical_risk_even_if_approved(db, website_fixture):
    workspace, website, user = website_fixture
    change = WebsiteChange(website_id=website.id, risk_level=RiskLevel.CRITICAL, status=WebsiteChangeStatus.APPROVED, files_changed=[])
    db.add(change)
    db.flush()

    with pytest.raises(CriticalRiskBlockedError):
        prepare_website_change(
            db, change=change, website=website, pr_title="t", pr_body="b",
            approver_role=OrgRole.OWNER, approver_id=user.id, organization_id=workspace.organization_id,
            workspace_id=workspace.id, git_provider=MockGitProvider(),
        )


def test_prepare_rejects_viewer_role(db, website_fixture):
    workspace, website, user = website_fixture
    change = WebsiteChange(website_id=website.id, risk_level=RiskLevel.LOW, status=WebsiteChangeStatus.APPROVED, files_changed=[])
    db.add(change)
    db.flush()

    with pytest.raises(PermissionError):
        prepare_website_change(
            db, change=change, website=website, pr_title="t", pr_body="b",
            approver_role=OrgRole.VIEWER, approver_id=user.id, organization_id=workspace.organization_id,
            workspace_id=workspace.id, git_provider=MockGitProvider(),
        )


def test_prepare_succeeds_for_approved_low_risk_change(db, website_fixture):
    workspace, website, user = website_fixture
    change = WebsiteChange(
        website_id=website.id, risk_level=RiskLevel.LOW, status=WebsiteChangeStatus.APPROVED,
        files_changed=[{"path": "robots.txt", "before": "", "after": "User-agent: *\n", "sha": ""}],
    )
    db.add(change)
    db.flush()

    result = prepare_website_change(
        db, change=change, website=website, pr_title="Add robots.txt", pr_body="b",
        approver_role=OrgRole.OWNER, approver_id=user.id, organization_id=workspace.organization_id,
        workspace_id=workspace.id, git_provider=MockGitProvider(),
    )
    assert result.status == WebsiteChangeStatus.PR_CREATED
    assert result.pr_url
    assert result.branch_name.startswith("gruvle-reach/")
