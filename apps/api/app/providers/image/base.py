"""
ImageProvider abstraction. Optional — the app must render a full scene
background with zero credentials (see scene_renderer.py's procedural
gradient-mesh fallback); when configured, this supplies a real AI-
generated background image instead, used as raw material scene_renderer.py
still composites its own text/shadow/kicker-rule on top of, so legibility
never depends on the model rendering readable text (diffusion models
reliably cannot).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImageGenerationResult:
    success: bool
    image_bytes: bytes = b""
    content_type: str = "image/jpeg"
    error: str = ""


class ImageProvider(ABC):
    name: str = "base"

    @abstractmethod
    def configured(self) -> bool:
        ...

    @abstractmethod
    def generate(self, *, prompt: str, negative_prompt: str = "", width: int = 1024, height: int = 1024) -> ImageGenerationResult:
        ...
