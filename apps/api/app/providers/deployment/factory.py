import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_cipher
from app.db.models.enums import IntegrationStatus
from app.db.models.integration import Integration, IntegrationCredential
from app.providers.deployment.base import DeploymentProvider
from app.providers.deployment.disabled_provider import DisabledDeploymentProvider
from app.providers.deployment.vercel_provider import VercelProvider


def get_deployment_provider_for_website(db: Session, workspace_id: uuid.UUID) -> DeploymentProvider:
    integration = db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider_name == "vercel_target",
            Integration.status == IntegrationStatus.CONNECTED,
        )
    ).scalar_one_or_none()
    if integration is None:
        return DisabledDeploymentProvider()

    cred = db.execute(
        select(IntegrationCredential).where(IntegrationCredential.integration_id == integration.id)
    ).scalar_one_or_none()
    if cred is None:
        return DisabledDeploymentProvider()

    try:
        payload = json.loads(get_cipher().decrypt(cred.encrypted_payload))
    except ValueError:
        return DisabledDeploymentProvider()

    provider = VercelProvider(token=payload.get("token", ""), project_id=payload.get("project_id", ""))
    return provider if provider.configured() else DisabledDeploymentProvider()
