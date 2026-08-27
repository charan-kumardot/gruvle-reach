from app.core.config import Settings, get_settings
from app.providers.social.base import SocialProvider
from app.providers.social.instagram_provider import InstagramProvider
from app.providers.social.linkedin_provider import LinkedInProvider
from app.providers.social.producthunt_provider import ProductHuntProvider
from app.providers.social.x_provider import XProvider


def get_social_providers(settings: Settings | None = None) -> dict[str, SocialProvider]:
    settings = settings or get_settings()
    return {
        "linkedin": LinkedInProvider(settings.linkedin_client_id, settings.linkedin_client_secret),
        "x": XProvider(settings.x_client_id, settings.x_client_secret),
        "instagram": InstagramProvider(settings.instagram_app_id, settings.instagram_app_secret),
        "product_hunt": ProductHuntProvider(settings.producthunt_client_id, settings.producthunt_client_secret),
    }
