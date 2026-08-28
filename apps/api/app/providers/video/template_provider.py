import shutil

from app.agents.video_agent import Scene
from app.db.models.video import VideoBrandKit
from app.media.video_renderer import RenderResult, render_video
from app.providers.video.base import VideoProvider


class TemplateVideoProvider(VideoProvider):
    """The free-first implementation (§16, §40) — Pillow scenes + FFmpeg
    concat, optional pyttsx3 voiceover. The sole v1 implementation; a paid
    provider can be added later behind the same VideoProvider interface."""

    name = "template"

    def configured(self) -> bool:
        return shutil.which("ffmpeg") is not None

    def render(self, scenes: list[Scene], *, brand_kit: VideoBrandKit | None, aspect_ratio: str) -> RenderResult:
        return render_video(scenes, brand_kit=brand_kit, aspect_ratio=aspect_ratio)
