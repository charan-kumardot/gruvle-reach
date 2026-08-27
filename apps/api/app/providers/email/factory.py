from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.email.base import EmailProvider
from app.providers.email.disabled_provider import DisabledEmailProvider
from app.providers.email.resend_provider import ResendProvider
from app.providers.email.smtp_provider import SMTPProvider


def build_email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider == "resend" and settings.resend_api_key:
        return ResendProvider(settings.resend_api_key, settings.resend_from_email)
    if settings.email_provider == "smtp" and settings.smtp_host:
        return SMTPProvider(
            settings.smtp_host, settings.smtp_port, settings.smtp_username, settings.smtp_password, settings.smtp_from_email
        )
    return DisabledEmailProvider()


@lru_cache
def get_email_provider() -> EmailProvider:
    return build_email_provider(get_settings())
