"""
Git executor (visibility spec §19, §27, §33). The ONLY module permitted to
call GitProvider.create_branch / commit_file_change / create_pull_request.
Mirrors app/actions/executor.py's email-send pattern exactly: approval
check first, hard CRITICAL-risk block that no role can override, action
performed, audit logged. Agents never reach GitProvider directly.
"""
import datetime as dt
import re
import uuid

from sqlalchemy.orm import Session

from app.actions.policy import can_approve
from app.agents.risk_classifier import is_auto_prepareable
from app.core.audit import record_audit
from app.db.models.enums import OrgRole, RiskLevel, WebsiteChangeStatus
from app.db.models.visibility import WebsiteChange, Website
from app.providers.git.base import GitProvider, GitProviderError


class ApprovalRequiredError(RuntimeError):
    pass


class CriticalRiskBlockedError(RuntimeError):
    pass


def _slugify_branch(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    return f"gruvle-reach/{slug or 'website-change'}-{uuid.uuid4().hex[:6]}"


def prepare_website_change(
    db: Session,
    *,
    change: WebsiteChange,
    website: Website,
    pr_title: str,
    pr_body: str,
    approver_role: OrgRole,
    approver_id: uuid.UUID,
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    git_provider: GitProvider,
) -> WebsiteChange:
    if change.status != WebsiteChangeStatus.APPROVED:
        raise ApprovalRequiredError("WebsiteChange must be APPROVED before a branch/PR can be created")
    if not is_auto_prepareable(change.risk_level):
        # Hard block for HIGH/CRITICAL — no role or approval can override this (§10, §33).
        raise CriticalRiskBlockedError(
            f"{change.risk_level.value.upper()}-risk changes can never be auto-prepared, regardless of approval"
        )
    if not can_approve(approver_role):
        raise PermissionError("Role does not have permission to prepare a website change")
    if not git_provider.configured():
        raise GitProviderError("GitHub is not connected for this workspace")

    branch_name = _slugify_branch(pr_title)
    base_branch = website.default_branch

    try:
        git_provider.create_branch(
            owner=website.repository_owner, repo=website.repository_name,
            base_branch=base_branch, new_branch=branch_name,
        )
        change.branch_name = branch_name
        change.base_branch = base_branch
        change.status = WebsiteChangeStatus.BRANCH_CREATED

        commit_sha = ""
        for file_change in change.files_changed:
            commit_sha = git_provider.commit_file_change(
                owner=website.repository_owner, repo=website.repository_name, branch=branch_name,
                path=file_change["path"], new_content=file_change["after"],
                message=f"Gruvle Reach: {pr_title}",
                previous_sha=file_change.get("sha", ""),
            )
        change.commit_sha = commit_sha

        pr = git_provider.create_pull_request(
            owner=website.repository_owner, repo=website.repository_name,
            head_branch=branch_name, base_branch=base_branch, title=pr_title, body=pr_body,
        )
        change.pr_number = pr.number
        change.pr_url = pr.url
        change.status = WebsiteChangeStatus.PR_CREATED

    except GitProviderError as exc:
        record_audit(
            db, organization_id=organization_id, workspace_id=workspace_id, user_id=approver_id,
            action="website_change_prepare_failed", resource_type="website_change", resource_id=str(change.id),
            metadata={"error": str(exc)},
        )
        db.flush()
        raise

    record_audit(
        db, organization_id=organization_id, workspace_id=workspace_id, user_id=approver_id,
        action="website_change_pr_created", resource_type="website_change", resource_id=str(change.id),
        metadata={"branch": branch_name, "pr_url": change.pr_url},
    )
    db.flush()
    return change
