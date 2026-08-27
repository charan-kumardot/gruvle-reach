from app.providers.email.base import EmailProvider, EmailSendResult


class DisabledEmailProvider(EmailProvider):
    """Used when EMAIL_PROVIDER=disabled or misconfigured. The app still
    boots and outreach drafting still works — sending simply reports
    'not configured' instead of raising, so callers can show a clear
    'connect an email provider' state in the UI."""

    name = "disabled"

    def configured(self) -> bool:
        return False

    def send(self, *, to: str, subject: str, html_body: str, text_body: str = "") -> EmailSendResult:
        return EmailSendResult(success=False, error="No email provider is configured for this workspace")
