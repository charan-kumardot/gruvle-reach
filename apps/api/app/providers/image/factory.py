from functools import lru_cache

from app.core.config import Settings, get_settings
from app.providers.image.base import ImageProvider
from app.providers.image.huggingface_provider import HuggingFaceImageProvider

# Hugging Face image generation is built and tested but not the active
# default — this account's free monthly inference credit is exhausted and
# has no payment method attached, so it fails-and-falls-back on every call
# today. General web image search (app/providers/image/search_provider.py)
# was tried and explicitly rejected — a query for "software engineer
# laptop office" returned a My Little Pony comic cover, unacceptable for a
# product marketing video and not worth the relevance-filtering complexity
# needed to make it reliable. The default background is the procedural
# gradient-mesh design (scene_renderer.py); product screenshots (uploaded
# by the founder, see VideoBrandKit.product_screenshot_url) are the
# reliable "real" visual, used for the product/solution scenes specifically.


def build_image_provider(settings: Settings) -> ImageProvider:
    return HuggingFaceImageProvider(settings.huggingface_api_token)


@lru_cache
def get_image_provider() -> ImageProvider:
    return build_image_provider(get_settings())
