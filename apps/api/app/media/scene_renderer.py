"""
Deterministic scene rendering — Pillow, no AI. Renders one PNG frame per
video scene: a solid background + accent bar from VideoBrandKit's colors,
with the scene's script text wrapped and centered. This frame text IS the
burned-in caption (§10, §14) — no separate word-level caption-sync pass is
needed for v1, since the full line is already on screen for the scene's
whole duration.
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.agents.video_agent import Scene
from app.db.models.video import VideoBrandKit

# (width, height) per aspect ratio — moderate resolution keeps render time
# and output size small, appropriate for short-form social video (§13).
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "9:16": (720, 1280),
    "1:1": (720, 720),
    "16:9": (1280, 720),
}

# Cross-platform candidates so the same code renders identically in the
# Linux Docker image (fonts-dejavu-core, installed in the Dockerfile) and
# on a developer's Windows/macOS machine — falls back to Pillow's built-in
# bitmap font if none are found, never hard-fails.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _load_font(size: int):
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).is_file():
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_color: str, default: tuple[int, int, int]) -> tuple[int, int, int]:
    value = (hex_color or "").lstrip("#")
    if len(value) != 6:
        return default
    try:
        return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))
    except ValueError:
        return default


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_scene_frame(scene: Scene, brand_kit: VideoBrandKit | None, aspect_ratio: str) -> bytes:
    width, height = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    bg_color = _hex_to_rgb(brand_kit.background_color if brand_kit else "", default=(15, 23, 42))
    accent_color = _hex_to_rgb(brand_kit.primary_color if brand_kit else "", default=(99, 102, 241))
    text_color = _hex_to_rgb(brand_kit.text_color if brand_kit else "", default=(248, 250, 252))

    image = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(image)

    accent_height = max(int(height * 0.015), 6)
    draw.rectangle([0, 0, width, accent_height], fill=accent_color)

    font_size = int(width * 0.075)
    font = _load_font(font_size)
    max_text_width = int(width * 0.82)
    lines = _wrap_text(draw, scene.text, font, max_text_width)

    line_height = int(font_size * 1.35)
    total_text_height = line_height * len(lines)
    y = (height - total_text_height) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_width = bbox[2] - bbox[0]
        x = (width - line_width) // 2
        draw.text((x, y), line, font=font, fill=text_color)
        y += line_height

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
