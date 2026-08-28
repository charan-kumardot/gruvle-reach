from urllib.parse import urlencode

import httpx

from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class RedditProvider(SocialProvider):
    name = "reddit"

    AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
    SUBMIT_URL = "https://oauth.reddit.com/api/submit"

    def __init__(self, client_id: str, client_secret: str):
        self._client_id = client_id
        self._client_secret = client_secret

    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def capabilities(self) -> SocialCapabilities:
        if not self.configured():
            return SocialCapabilities(notes="Not configured — set REDDIT_CLIENT_ID/SECRET to enable.")
        return SocialCapabilities(
            can_read_profile=True,
            can_publish_post=True,
            notes=(
                "Uses Reddit's official API (submit self-post). A specific subreddit isn't chosen here — "
                "the draft is written as a genuine discussion contribution; posting still requires the "
                "founder to pick an appropriate, rule-compliant subreddit before publishing."
            ),
        )

    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        if not self.configured():
            return None
        params = {
            "client_id": self._client_id,
            "response_type": "code",
            "state": state,
            "redirect_uri": redirect_uri,
            "duration": "permanent",
            "scope": "submit identity",
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"

    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        if not self.configured() or not access_token:
            return PublishResult(
                status="manual_action_required",
                message="Reddit is not connected. Copy this draft and post it manually in an appropriate subreddit, or connect Reddit in Settings → Integrations.",
            )
        # Reddit's submit API requires a target subreddit, which this
        # generic publish_post signature doesn't carry — official API only,
        # never bypassing that requirement with a guessed default.
        return PublishResult(
            status="manual_action_required",
            message="Reddit requires choosing a specific subreddit before submitting — copy this draft and post it manually to the right community.",
        )
