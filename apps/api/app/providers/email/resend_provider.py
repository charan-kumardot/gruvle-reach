import httpx

from app.providers.email.base import EmailProvider, EmailSendResult


class ResendProvider(EmailProvider):
    name = "resend"

    def __init__(self, api_key: str, from_email: str):
        self._api_key = api_key
        self._from_email = from_email

    def configured(self) -> bool:
        return bool(self._api_key and self._from_email)

    def send(self, *, to: str, subject: str, html_body: str, text_body: str = "") -> EmailSendResult:
        if not self.configured():
            return EmailSendResult(success=False, error="Resend is not configured")

        try:
            resp = httpx.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "from": self._from_email,
                    "to": [to],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body or None,
                },
                timeout=20,
            )
        except httpx.HTTPError as exc:
            return EmailSendResult(success=False, error=str(exc))

        if resp.status_code >= 400:
            return EmailSendResult(success=False, error=f"Resend error {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        return EmailSendResult(success=True, provider_message_id=data.get("id", ""))
