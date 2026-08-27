from urllib.parse import urlencode

from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class ProductHuntProvider(SocialProvider):
    """Product Hunt's public API is read-mostly (GraphQL) — there is no
    official endpoint to submit a product launch programmatically; launches
    are always created through producthunt.com by a human. So this adapter
    is permanently `manual_action_required` for publishing, and only offers
    read access (checking a product's existing launch data) once configured."""

    name = "product_hunt"

    AUTHORIZE_URL = "https://api.producthunt.com/v2/oauth/authorize"

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret

    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def capabilities(self) -> SocialCapabilities:
        if not self.configured():
            return SocialCapabilities(notes="Not configured — set PRODUCTHUNT_CLIENT_ID/SECRET to enable.")
        return SocialCapabilities(
            can_read_company=True,
            notes="Read-only via Product Hunt's public GraphQL API. Launch submission has no public API and always requires manual action on producthunt.com.",
        )

    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        if not self.configured():
            return None
        params = {
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "response_type": "code",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        return PublishResult(
            status="manual_action_required",
            message="Product Hunt has no public launch-submission API. Use the generated launch kit to submit manually at producthunt.com/posts/new.",
        )
