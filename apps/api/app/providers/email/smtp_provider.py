import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.providers.email.base import EmailProvider, EmailSendResult


class SMTPProvider(EmailProvider):
    name = "smtp"

    def __init__(self, host: str, port: int, username: str, password: str, from_email: str):
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_email = from_email

    def configured(self) -> bool:
        return bool(self._host and self._from_email)

    def send(self, *, to: str, subject: str, html_body: str, text_body: str = "") -> EmailSendResult:
        if not self.configured():
            return EmailSendResult(success=False, error="SMTP is not configured")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from_email
        msg["To"] = to
        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self._host, self._port, timeout=20) as server:
                server.starttls()
                if self._username:
                    server.login(self._username, self._password)
                server.sendmail(self._from_email, [to], msg.as_string())
        except Exception as exc:  # noqa: BLE001
            return EmailSendResult(success=False, error=str(exc))

        return EmailSendResult(success=True)
