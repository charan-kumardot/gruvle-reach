"""
Unlike the other provider factories (which read process env config),
GitProvider credentials are per-workspace, founder-supplied, and encrypted
in the database — so this factory needs a DB session and workspace id
rather than global Settings.
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_cipher
from app.db.models.enums import IntegrationStatus
from app.db.models.integration import Integration, IntegrationCredential
from app.providers.git.base import GitProvider
from app.providers.git.github_provider import GitHubProvider


def get_git_provider_for_workspace(db: Session, workspace_id: uuid.UUID) -> GitProvider:
    integration = db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider_name == "github",
            Integration.status == IntegrationStatus.CONNECTED,
        )
    ).scalar_one_or_none()
    if integration is None:
        return GitHubProvider(token="")

    cred = db.execute(
        select(IntegrationCredential).where(IntegrationCredential.integration_id == integration.id)
    ).scalar_one_or_none()
    if cred is None:
        return GitHubProvider(token="")

    try:
        payload = json.loads(get_cipher().decrypt(cred.encrypted_payload))
    except ValueError:
        return GitHubProvider(token="")

    return GitHubProvider(token=payload.get("pat", ""))
