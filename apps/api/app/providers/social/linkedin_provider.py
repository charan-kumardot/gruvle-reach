from urllib.parse import urlencode

import httpx

from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class LinkedInProvider(SocialProvider):
    name = "linkedin"

    AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
    UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret

    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def capabilities(self) -> SocialCapabilities:
        if not self.configured():
            return SocialCapabilities(notes="Not configured — set LINKEDIN_CLIENT_ID/SECRET to enable.")
        return SocialCapabilities(
            can_read_profile=True,
            can_publish_post=True,
            notes="Uses LinkedIn's official Sign In + Share API (w_member_social scope). Company page posting requires additional Marketing API access LinkedIn grants per-application.",
        )

    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        if not self.configured():
            return None
        params = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "openid profile w_member_social",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        if not self.configured() or not access_token:
            return PublishResult(
                status="manual_action_required",
                message="LinkedIn is not connected. Copy this draft and post manually, or connect LinkedIn in Settings → Integrations.",
            )
        # Real UGC Posts call — only reached once a workspace has completed
        # OAuth and holds a valid member access token.
        try:
            resp = httpx.post(
                self.UGC_POSTS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Restli-Protocol-Version": "2.0.0",
                    "Content-Type": "application/json",
                },
                json={
                    "author": "urn:li:person:me",
                    "lifecycleState": "PUBLISHED",
                    "specificContent": {
                        "com.linkedin.ugc.ShareContent": {
                            "shareCommentary": {"text": body},
                            "shareMediaCategory": "NONE",
                        }
                    },
                    "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
                },
                timeout=20,
            )
            if resp.status_code >= 400:
                return PublishResult(status="failed", message=f"LinkedIn API error {resp.status_code}: {resp.text[:300]}")
            post_id = resp.headers.get("x-restli-id", "")
            return PublishResult(status="published", external_id=post_id)
        except httpx.HTTPError as exc:
            return PublishResult(status="failed", message=str(exc))
