from urllib.parse import urlencode

from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class InstagramProvider(SocialProvider):
    name = "instagram"

    AUTHORIZE_URL = "https://www.facebook.com/v21.0/dialog/oauth"

    def __init__(self, app_id: str, app_secret: str):
        self._app_id = app_id
        self._app_secret = app_secret

    def configured(self) -> bool:
        return bool(self._app_id and self._app_secret)

    def capabilities(self) -> SocialCapabilities:
        if not self.configured():
            return SocialCapabilities(notes="Not configured — set INSTAGRAM_APP_ID/SECRET to enable.")
        return SocialCapabilities(
            can_read_profile=True,
            notes=(
                "Publishing requires a connected Instagram Business/Creator account via the Meta "
                "Content Publishing API (two-step: create media container, then publish) and app "
                "review from Meta. Until that review is complete, posts are prepared as drafts for manual publishing."
            ),
        )

    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        if not self.configured():
            return None
        params = {
            "client_id": self._app_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": "instagram_basic,instagram_content_publish,pages_show_list",
            "response_type": "code",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        # Instagram's Content Publishing API requires an image/video container
        # (text-only posts aren't supported) and Meta app review — always a
        # manual/prepared-draft flow in this build.
        return PublishResult(
            status="manual_action_required",
            message="Instagram publishing requires an approved Meta app + media asset. Draft prepared for manual posting.",
        )
