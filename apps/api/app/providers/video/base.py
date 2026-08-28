"""
VideoProvider abstraction (§15). Scoped to the deterministic rendering
half of the pipeline only (scene/voice/caption composition -> mp4) —
script writing is an AI call and lives in app/agents/video_agent.py
instead, the same division of labor this codebase uses everywhere else
(agents own AI calls, providers own external-system I/O/computation). A
paid video provider could implement this same interface later without
touching video_agent.py or any call site.
"""
from abc import ABC, abstractmethod

from app.agents.video_agent import Scene
from app.db.models.video import VideoBrandKit
from app.media.video_renderer import RenderResult


class VideoProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def render(self, scenes: list[Scene], *, brand_kit: VideoBrandKit | None, aspect_ratio: str) -> RenderResult:
        ...
