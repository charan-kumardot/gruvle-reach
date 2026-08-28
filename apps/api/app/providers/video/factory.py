from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.video.base import VideoProvider
from app.providers.video.template_provider import TemplateVideoProvider


def build_video_provider(settings: Settings) -> VideoProvider:
    # Single active provider, same shape as AI/Search (unlike Social's
    # multi-provider dict) — only one render backend runs at a time.
    return TemplateVideoProvider()


@lru_cache
def get_video_provider() -> VideoProvider:
    return build_video_provider(get_settings())
