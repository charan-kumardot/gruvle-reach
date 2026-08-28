import httpx

from app.providers.image.base import ImageGenerationResult, ImageProvider

# hf-inference is Hugging Face's own hosted infra (as opposed to the
# third-party-routed providers like fal-ai/replicate used for video) —
# the more consistently free-tier-friendly path for image generation.
_MODEL_URL = "https://router.huggingface.co/hf-inference/models/stabilityai/stable-diffusion-3-medium-diffusers"


def _round_to_multiple(value: int, multiple: int = 16) -> int:
    return max(multiple, (value // multiple) * multiple)


class HuggingFaceImageProvider(ImageProvider):
    name = "huggingface"

    def __init__(self, api_token: str):
        self._token = api_token

    def configured(self) -> bool:
        return bool(self._token)

    def generate(self, *, prompt: str, negative_prompt: str = "", width: int = 1024, height: int = 1024) -> ImageGenerationResult:
        if not self.configured():
            return ImageGenerationResult(success=False, error="Hugging Face token not configured")

        parameters = {"width": _round_to_multiple(width), "height": _round_to_multiple(height)}
        if negative_prompt:
            parameters["negative_prompt"] = negative_prompt

        try:
            # A video has up to 6 scenes, each attempting one of these
            # calls sequentially in the background render thread — a slow/
            # hanging call needs to fail fast and fall back rather than let
            # worst-case latency across all scenes approach the stale-
            # render safety net's 5-minute threshold on its own.
            resp = httpx.post(
                _MODEL_URL,
                headers={"Authorization": f"Bearer {self._token}"},
                json={"inputs": prompt, "parameters": parameters},
                timeout=25,
            )
            if resp.status_code >= 400:
                return ImageGenerationResult(success=False, error=f"Hugging Face image API error {resp.status_code}: {resp.text[:300]}")
            content_type = resp.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                # A 200 with a JSON body means the model is loading/queued
                # or returned a structured error rather than image bytes.
                return ImageGenerationResult(success=False, error=f"Unexpected response ({content_type}): {resp.text[:300]}")
            return ImageGenerationResult(success=True, image_bytes=resp.content, content_type=content_type)
        except httpx.HTTPError as exc:
            return ImageGenerationResult(success=False, error=str(exc))
