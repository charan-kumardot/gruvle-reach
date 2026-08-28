"""
Deterministic scene rendering — Pillow, no AI. Produces a short animation
PER SCENE (a slow Ken Burns zoom over a modern gradient-mesh background —
soft blurred color blobs, the same visual language as Linear/Stripe/Vercel
marketing pages) rather than one flat static frame, so the final video
reads as motion graphics instead of a text slide. Cheap by construction:
each scene still renders ONE full-detail "master" frame; every animation
frame after that is just a crop+resize of the master (fast raster ops),
so frame count can be generous without meaningfully increasing render
time. video_renderer.py turns the frame lists this module returns into a
video via the same simple concat-demuxer pipeline as before — no new
FFmpeg filter complexity, keeping render cost/risk unchanged.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.agents.video_agent import Scene
from app.db.models.video import VideoBrandKit

# (width, height) per aspect ratio — moderate resolution keeps render time
# and output size small, appropriate for short-form social video (§13).
RESOLUTIONS: dict[str, tuple[int, int]] = {
    "9:16": (720, 1280),
    "1:1": (720, 720),
    "16:9": (1280, 720),
}

# The master canvas is rendered this much larger than the final frame size
# so the zoom animation can crop a shrinking window from it without ever
# upscaling (soft/blurry) pixels.
_ZOOM_MASTER_SCALE = 1.16
# Fraction of the animation that's a pure zoom-in (1.0 -> the scale above),
# applied via crop+resize per frame — a slow, subtle Ken Burns move reads
# as "video," a fast one reads as a slideshow effect, so keep it gentle.
_MOTION_FRAMES_PER_SECOND = 8
_MAX_FRAMES_PER_SCENE = 40

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


def _vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    width, height = size
    base = Image.new("RGB", (1, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        row = tuple(int(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
        base.putpixel((0, y), row)
    return base.resize((width, height))


def _blob_layer(size: tuple[int, int], blobs: list[tuple[int, int, int, tuple[int, int, int], int]]) -> Image.Image:
    """blobs: list of (cx, cy, radius, rgb, alpha). Drawn on a transparent
    layer then heavily blurred for the soft 'gradient mesh' look."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for cx, cy, radius, color, alpha in blobs:
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(*color, alpha))
    blur_radius = int(min(size) * 0.12)
    return layer.filter(ImageFilter.GaussianBlur(blur_radius))


def _draw_text_with_shadow(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[str], font, line_height: int, text_color: tuple[int, int, int]) -> None:
    x, y = xy
    shadow_color = (0, 0, 0, 140)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_x = x - (bbox[2] - bbox[0]) // 2
        draw.text((line_x + 3, y + 4), line, font=font, fill=shadow_color)
        draw.text((line_x, y), line, font=font, fill=text_color)
        y += line_height


def _build_master_frame(scene: Scene, brand_kit: VideoBrandKit | None, aspect_ratio: str) -> Image.Image:
    final_w, final_h = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    width, height = int(final_w * _ZOOM_MASTER_SCALE), int(final_h * _ZOOM_MASTER_SCALE)

    bg_base = _hex_to_rgb(brand_kit.background_color if brand_kit else "", default=(10, 12, 20))
    accent = _hex_to_rgb(brand_kit.primary_color if brand_kit else "", default=(99, 102, 241))
    secondary = _hex_to_rgb(brand_kit.secondary_color if brand_kit else "", default=(139, 92, 246))
    text_color = _hex_to_rgb(brand_kit.text_color if brand_kit else "", default=(248, 250, 252))

    # A subtle vertical gradient base (never flat), then two soft, large,
    # heavily-blurred color blobs in the brand's accent/secondary colors —
    # the "gradient mesh" look used across most modern SaaS marketing
    # sites/videos (Linear, Stripe, Vercel, etc).
    gradient_top = tuple(min(255, c + 14) for c in bg_base)
    image = _vertical_gradient((width, height), gradient_top, bg_base).convert("RGBA")
    blobs = _blob_layer((width, height), [
        (int(width * 0.82), int(height * 0.12), int(width * 0.38), accent, 130),
        (int(width * 0.12), int(height * 0.88), int(width * 0.42), secondary, 110),
        (int(width * 0.5), int(height * 0.45), int(width * 0.30), accent, 45),
    ])
    image = Image.alpha_composite(image, blobs)
    draw = ImageDraw.Draw(image)

    font_size = int(width * 0.072)
    font = _load_font(font_size)
    max_text_width = int(width * 0.80)
    lines = _wrap_text(draw, scene.text, font, max_text_width)
    line_height = int(font_size * 1.32)
    total_text_height = line_height * len(lines)
    text_y = (height - total_text_height) // 2
    _draw_text_with_shadow(draw, (width // 2, text_y), lines, font, line_height, text_color)

    # A small accent-colored kicker rule above the text — a cheap but
    # effective "designed" touch, not just raw text on a background.
    rule_width = int(width * 0.10)
    rule_y = text_y - int(font_size * 0.55)
    draw.rounded_rectangle(
        [width // 2 - rule_width // 2, rule_y, width // 2 + rule_width // 2, rule_y + 6],
        radius=3, fill=(*accent, 255),
    )

    return image.convert("RGB")


def _zoom_crop(master: Image.Image, t: float, final_size: tuple[int, int]) -> Image.Image:
    """t in [0, 1]: 0 shows the full master (zoomed out), 1 shows a native-
    resolution center crop (zoomed in) — a slow, continuous zoom-in over
    the scene's duration."""
    master_w, master_h = master.size
    final_w, final_h = final_size
    scale = _ZOOM_MASTER_SCALE - t * (_ZOOM_MASTER_SCALE - 1.0)
    crop_w, crop_h = int(final_w * scale), int(final_h * scale)
    left = (master_w - crop_w) // 2
    top = (master_h - crop_h) // 2
    cropped = master.crop((left, top, left + crop_w, top + crop_h))
    return cropped.resize(final_size, Image.LANCZOS)


def render_scene_animation(scene: Scene, brand_kit: VideoBrandKit | None, aspect_ratio: str) -> list[tuple[Image.Image, float]]:
    """Returns [(frame_image, hold_duration_seconds), ...] whose durations
    sum to scene.duration_seconds — a slow zoom-in across the scene
    instead of one static held frame."""
    final_size = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    master = _build_master_frame(scene, brand_kit, aspect_ratio)

    frame_count = max(2, min(_MAX_FRAMES_PER_SCENE, round(scene.duration_seconds * _MOTION_FRAMES_PER_SECOND)))
    frame_duration = scene.duration_seconds / frame_count

    frames: list[tuple[Image.Image, float]] = []
    for i in range(frame_count):
        t = i / (frame_count - 1) if frame_count > 1 else 0.0
        frames.append((_zoom_crop(master, t, final_size), frame_duration))
    return frames


def render_transition_frames(
    from_frame: Image.Image, to_frame: Image.Image, *, count: int = 6, total_duration: float = 0.28,
) -> list[tuple[Image.Image, float]]:
    """A short crossfade between two scenes, built as a handful of alpha-
    blended frames rather than an FFmpeg xfade filter — keeps the render
    pipeline on the same simple, already-proven concat-demuxer path."""
    per_frame = total_duration / count
    frames: list[tuple[Image.Image, float]] = []
    for i in range(1, count + 1):
        alpha = i / (count + 1)
        blended = Image.blend(from_frame.convert("RGB"), to_frame.convert("RGB"), alpha)
        frames.append((blended, per_frame))
    return frames
