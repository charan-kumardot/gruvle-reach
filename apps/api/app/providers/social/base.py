"""
SocialProvider abstraction (§28-30, §64). Every social platform is an
optional adapter: the app must start and the Outreach/Content modules must
work fully (drafting, approval, tracking-as-manual) with zero social
credentials configured. When a platform's OAuth app credentials are added to
.env later, `configured()` flips to True and the connect flow becomes
available — no other code changes.

We only ever call *official* platform APIs here, never scrape or automate
around login forms. Any capability the official API doesn't expose (e.g.
Product Hunt product submission) is permanently reported as
`manual_action_required` rather than faked.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class PublishResult:
    status: str  # "published" | "manual_action_required" | "failed"
    external_id: str = ""
    external_url: str = ""
    message: str = ""


@dataclass
class SocialCapabilities:
    can_read_profile: bool = False
    can_read_company: bool = False
    can_publish_post: bool = False
    can_publish_comment: bool = False
    can_read_engagement: bool = False
    notes: str = ""


class SocialProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        """True only if this app has registered OAuth client credentials for
        the platform. Does NOT mean a specific workspace has connected."""

    @abstractmethod
    def capabilities(self) -> SocialCapabilities:
        ...

    @abstractmethod
    def authorize_url(self, *, state: str, redirect_uri: str) -> str | None:
        """Official OAuth authorize URL, or None if not configured."""

    @abstractmethod
    def publish_post(self, *, access_token: str, body: str, media_urls: list[str] | None = None) -> PublishResult:
        ...
