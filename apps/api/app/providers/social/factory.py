import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import get_cipher
from app.db.models.enums import IntegrationStatus
from app.db.models.integration import Integration, IntegrationCredential
from app.providers.social.base import SocialProvider
from app.providers.social.facebook_provider import FacebookProvider
from app.providers.social.instagram_provider import InstagramProvider
from app.providers.social.linkedin_provider import LinkedInProvider
from app.providers.social.producthunt_provider import ProductHuntProvider
from app.providers.social.reddit_provider import RedditProvider
from app.providers.social.x_provider import XProvider


def get_social_providers(settings: Settings | None = None) -> dict[str, SocialProvider]:
    settings = settings or get_settings()
    return {
        "linkedin": LinkedInProvider(settings.linkedin_client_id, settings.linkedin_client_secret),
        "x": XProvider(settings.x_client_id, settings.x_client_secret),
        "instagram": InstagramProvider(settings.instagram_app_id, settings.instagram_app_secret),
        "product_hunt": ProductHuntProvider(settings.producthunt_client_id, settings.producthunt_client_secret),
        "reddit": RedditProvider(settings.reddit_client_id, settings.reddit_client_secret),
        "facebook": FacebookProvider(settings.facebook_app_id, settings.facebook_app_secret),
    }


def get_social_access_token_for_workspace(db: Session, workspace_id: uuid.UUID, provider_name: str) -> str:
    """Per-workspace decrypt, same shape as
    app/providers/git/factory.py::get_git_provider_for_workspace — content
    publish reads a social access token the same way git_executor reads a
    GitHub token. Returns "" (never raises) if not connected, so callers
    can treat "no token" as "not connected" without a try/except."""
    integration = db.execute(
        select(Integration).where(
            Integration.workspace_id == workspace_id,
            Integration.provider_name == provider_name,
            Integration.status == IntegrationStatus.CONNECTED,
        )
    ).scalar_one_or_none()
    if integration is None:
        return ""

    cred = db.execute(
        select(IntegrationCredential).where(IntegrationCredential.integration_id == integration.id)
    ).scalar_one_or_none()
    if cred is None:
        return ""

    try:
        payload = json.loads(get_cipher().decrypt(cred.encrypted_payload))
    except ValueError:
        return ""

    return payload.get("access_token", "")
