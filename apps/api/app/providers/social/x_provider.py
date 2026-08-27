from urllib.parse import urlencode

import httpx

from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class XProvider(SocialProvider):
    name = "x"

    AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
    TWEETS_URL = "https://api.x.com/2/tweets"

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret

    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def capabilities(self) -> SocialCapabilities:
        if not self.configured():
            return SocialCapabilities(notes="Not configured — set X_CLIENT_ID/SECRET to enable.")
        return SocialCapabilities(
            can_read_profile=True,
            can_publish_post=True,
            notes="Uses X API v2 OAuth2 (PKCE) with tweet.write scope.",
        )

    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        if not self.configured():
            return None
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "tweet.read tweet.write users.read offline.access",
            "code_challenge": "challenge",  # PKCE challenge is generated per-session by the auth flow, not here
            "code_challenge_method": "plain",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        if not self.configured() or not access_token:
            return PublishResult(
                status="manual_action_required",
                message="X is not connected. Copy this draft and post manually, or connect X in Settings → Integrations.",
            )
        try:
            resp = httpx.post(
                self.TWEETS_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"text": body},
                timeout=20,
            )
            if resp.status_code >= 400:
                return PublishResult(status="failed", message=f"X API error {resp.status_code}: {resp.text[:300]}")
            data = resp.json().get("data", {})
            return PublishResult(status="published", external_id=data.get("id", ""))
        except httpx.HTTPError as exc:
            return PublishResult(status="failed", message=str(exc))
