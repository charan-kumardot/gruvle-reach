from app.providers.social.base import PublishResult, SocialCapabilities, SocialProvider


class MockSocialProvider(SocialProvider):
    """Used ONLY for demo-mode/testing so the UI can exercise the
    draft-approve-publish flow end to end without real credentials. Every
    result it returns is tagged so it can never be mistaken for a real send;
    the demo seed script is the only caller expected to use this."""

    name = "mock"

    def __init__(self, platform_label: str = "mock"):
        self._platform_label = platform_label

    def configured(self) -> bool:
        return True

    def capabilities(self) -> SocialCapabilities:
        return SocialCapabilities(
            can_read_profile=True,
            can_publish_post=True,
            notes="DEMO ONLY — simulated provider, does not contact any real platform.",
        )

    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        return None

    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        return PublishResult(status="published", external_id="demo-simulated", message="[DEMO] Simulated publish — not sent to any real platform.")
