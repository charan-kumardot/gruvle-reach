from urllib.parse import urlencode

import httpx

from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class FacebookProvider(SocialProvider):
    name = "facebook"

    AUTHORIZE_URL = "https://www.facebook.com/v19.0/dialog/oauth"
    GRAPH_BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, app_id: str, app_secret: str):
        self._app_id = app_id
        self._app_secret = app_secret

    def configured(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def capabilities(self) -> SocialCapabilities:
        if not self.configured():
            return SocialCapabilities(notes="Not configured — set FACEBOOK_APP_ID/SECRET to enable.")
        return SocialCapabilities(
            can_read_profile=True,
            can_publish_post=True,
            notes="Uses the Graph API's page feed endpoint (pages_manage_posts scope). The access token must be a Page access token, not a user token.",
        )

    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        if not self.configured():
            return None
        params = {
            "client_id": self._app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "pages_manage_posts,pages_read_engagement",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        if not self.configured() or not access_token:
            return PublishResult(
                status="manual_action_required",
                message="Facebook is not connected. Copy this draft and post manually, or connect Facebook in Settings → Integrations.",
            )
        try:
            resp = httpx.post(
                f"{self.GRAPH_BASE_URL}/me/feed",
                data={"message": body, "access_token": access_token},
                timeout=20,
            )
            if resp.status_code >= 400:
                return PublishResult(status="failed", message=f"Facebook API error {resp.status_code}: {resp.text[:300]}")
            post_id = resp.json().get("id", "")
            return PublishResult(status="published", external_id=post_id)
        except httpx.HTTPError as exc:
            return PublishResult(status="failed", message=str(exc))
