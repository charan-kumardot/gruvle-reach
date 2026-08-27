"""
AnalyticsProvider abstraction — emits product-analytics events (§82). The
default implementation writes to our own database (no third-party
dependency); a paid analytics adapter (PostHog/Mixpanel/etc.) can be added
later behind the same interface. Never pass raw research content or
credentials as event properties.
"""
from abc import ABC, abstractmethod


class AnalyticsProvider(ABC):
    name: str = "base"

    @abstractmethod
    def track(self, *, event: str, workspace_id: str | None, properties: dict) -> None:
        ...


class NoopAnalyticsProvider(AnalyticsProvider):
    name = "noop"

    def track(self, *, event: str, workspace_id: str | None, properties: dict) -> None:
        return None
