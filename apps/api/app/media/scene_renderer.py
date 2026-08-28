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
import io
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.agents.video_agent import Scene
from app.db.models.video import VideoBrandKit
from app.providers.image.base import ImageProvider

logger = logging.getLogger(__name__)

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


def _text_scrim_layer(size: tuple[int, int]) -> Image.Image:
    """A soft dark band across the vertical middle of the frame, strongest
    where the caption text sits and fading out above/below it — legibility
    over a busy/bright AI-generated photo can't depend on the photo's own
    contrast the way the procedural gradient's plain middle area can."""
    width, height = size
    band_top, band_bottom = int(height * 0.30), int(height * 0.72)
    mid, half = (band_top + band_bottom) / 2, max((band_bottom - band_top) / 2, 1)
    column = Image.new("L", (1, height))
    for y in range(height):
        falloff = max(0.0, 1 - abs(y - mid) / half)
        column.putpixel((0, y), int(150 * falloff))
    alpha_mask = column.resize((width, height))
    layer = Image.new("RGBA", size, (0, 0, 0, 255))
    layer.putalpha(alpha_mask)
    return layer


# Concrete, photographable scenes — these work well both as search queries
# (an image search engine needs a subject that actually exists as a photo,
# not an abstract instruction) and as generation prompts.
_SCENE_STYLE_HINTS = {
    "hook": "software engineer focused on laptop screen, modern office",
    "problem": "frustrated developer at computer with error on screen",
    "insight": "team at whiteboard having a breakthrough idea, bright office",
    "solution": "modern software analytics dashboard on screen, clean UI",
    "product": "laptop with code editor open, minimalist modern workspace",
    "cta": "team celebrating success, high five, modern office, bright",
}


def _ai_background_prompt(scene: Scene) -> tuple[str, str]:
    style = _SCENE_STYLE_HINTS.get(scene.key, "modern technology, professional office")
    prompt = f"{style}, professional photography, high quality"
    negative_prompt = "text, words, letters, writing, typography, watermark, logo, signature, blurry, low quality, distorted"
    return prompt, negative_prompt


def _cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Crop-then-scale to fill `size` without distorting the aspect ratio
    (a naive stretch is very noticeable on a real photo of a person/object,
    unlike on an abstract gradient)."""
    target_w, target_h = size
    src_w, src_h = image.size
    target_ratio, src_ratio = target_w / target_h, src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(src_h * target_ratio)
        left = (src_w - new_w) // 2
        image = image.crop((left, 0, left + new_w, src_h))
    else:
        new_h = int(src_w / target_ratio)
        top = (src_h - new_h) // 2
        image = image.crop((0, top, src_w, top + new_h))
    return image.resize(size, Image.LANCZOS)


def _generate_ai_background(scene: Scene, image_provider: ImageProvider | None, width: int, height: int) -> Image.Image | None:
    """Best-effort only — any failure (not configured, quota exhausted,
    timeout, malformed response) falls back to the procedural gradient-mesh
    background, never breaks the render."""
    if image_provider is None or not image_provider.configured():
        return None
    prompt, negative_prompt = _ai_background_prompt(scene)
    result = image_provider.generate(prompt=prompt, negative_prompt=negative_prompt, width=width, height=height)
    if not result.success:
        logger.info("AI background unavailable for scene '%s' (%s) — using the procedural background", scene.key, result.error)
        return None
    try:
        image = Image.open(io.BytesIO(result.image_bytes)).convert("RGB")
        if image.size != (width, height):
            image = _cover_resize(image, (width, height))
        return image
    except Exception as exc:  # noqa: BLE001 — a corrupt/unexpected response must never break the render
        logger.info("Could not decode AI-generated background for scene '%s' (%s) — using the procedural background", scene.key, exc)
        return None


# Scenes where showing the real product matters most — everywhere else
# keeps the abstract gradient-mesh background, so the mockup doesn't
# repeat six times and lose its impact.
_MOCKUP_SCENE_KEYS = {"product", "solution"}


def _fetch_product_screenshot(url: str) -> Image.Image | None:
    """Best-effort only, same non-hard-dependency principle as everything
    else in this pipeline — if the founder's screenshot URL is unreachable
    or not actually an image, the scene falls through to the normal AI-
    background/procedural path rather than breaking the render."""
    if not url:
        return None
    try:
        from app.research.fetcher import SSRFBlockedError, safe_fetch_binary

        fetched = safe_fetch_binary(url, max_bytes=8 * 1024 * 1024)
        if fetched.status_code != 200 or not fetched.content_type.startswith("image/"):
            return None
        return Image.open(io.BytesIO(fetched.content)).convert("RGB")
    except Exception as exc:  # noqa: BLE001 — SSRFBlockedError included
        logger.info("Could not fetch/decode product screenshot (%s)", exc)
        return None


def _contain_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Scale to fit entirely within `size`, preserving aspect ratio —
    unlike _cover_resize, never crops (a screenshot's UI chrome/edges
    matter; cropping them off would misrepresent the product)."""
    target_w, target_h = size
    src_w, src_h = image.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w, new_h = max(1, int(src_w * scale)), max(1, int(src_h * scale))
    return image.resize((new_w, new_h), Image.LANCZOS)


def _render_browser_mockup(screenshot: Image.Image, card_size: tuple[int, int]) -> Image.Image:
    """A clean browser-window card: a header bar with traffic-light dots
    and a URL-bar pill, the screenshot contain-fit beneath it, rounded
    corners — the 'floating product card over a gradient' look used
    across most modern SaaS marketing pages (Linear, Stripe, Vercel)."""
    card_w, card_h = card_size
    card = Image.new("RGBA", card_size, (248, 250, 252, 255))
    draw = ImageDraw.Draw(card)

    header_h = int(card_h * 0.07)
    draw.rectangle([0, 0, card_w, header_h], fill=(226, 232, 240, 255))
    dot_r = max(2, int(header_h * 0.14))
    dot_y = header_h // 2
    for i, color in enumerate([(248, 113, 113), (250, 204, 21), (74, 222, 128)]):
        cx = int(header_h * 0.55) + i * int(dot_r * 3.2)
        draw.ellipse([cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r], fill=(*color, 255))
    pill_h = int(header_h * 0.42)
    draw.rounded_rectangle(
        [int(card_w * 0.30), dot_y - pill_h // 2, int(card_w * 0.75), dot_y + pill_h // 2],
        radius=pill_h // 2, fill=(203, 213, 225, 255),
    )

    content_area = (card_w, card_h - header_h)
    fitted = _contain_resize(screenshot, content_area)
    paste_x = (content_area[0] - fitted.width) // 2
    paste_y = header_h + (content_area[1] - fitted.height) // 2
    card.paste(fitted, (paste_x, paste_y))

    mask = Image.new("L", card_size, 0)
    corner_radius = int(min(card_size) * 0.04)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, card_w, card_h], radius=corner_radius, fill=255)
    card.putalpha(mask)
    return card


def _drop_shadow_layer(size: tuple[int, int], box: tuple[int, int, int, int], radius: int, blur: int) -> Image.Image:
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(box, radius=radius, fill=(0, 0, 0, 150))
    return shadow.filter(ImageFilter.GaussianBlur(blur))


def _build_product_mockup_frame(scene: Scene, brand_kit: VideoBrandKit | None, aspect_ratio: str, screenshot: Image.Image) -> Image.Image:
    final_w, final_h = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    width, height = int(final_w * _ZOOM_MASTER_SCALE), int(final_h * _ZOOM_MASTER_SCALE)

    bg_base = _hex_to_rgb(brand_kit.background_color if brand_kit else "", default=(10, 12, 20))
    accent = _hex_to_rgb(brand_kit.primary_color if brand_kit else "", default=(99, 102, 241))
    secondary = _hex_to_rgb(brand_kit.secondary_color if brand_kit else "", default=(139, 92, 246))
    text_color = _hex_to_rgb(brand_kit.text_color if brand_kit else "", default=(248, 250, 252))

    gradient_top = tuple(min(255, c + 14) for c in bg_base)
    image = _vertical_gradient((width, height), gradient_top, bg_base).convert("RGBA")
    blobs = _blob_layer((width, height), [
        (int(width * 0.85), int(height * 0.06), int(width * 0.34), accent, 110),
        (int(width * 0.08), int(height * 0.97), int(width * 0.38), secondary, 90),
    ])
    image = Image.alpha_composite(image, blobs)
    draw = ImageDraw.Draw(image)

    # Heading text top-aligned and smaller than the full-bleed scenes —
    # leaves room for the mockup card below rather than competing with it.
    font_size = int(width * 0.052)
    font = _load_font(font_size)
    max_text_width = int(width * 0.82)
    lines = _wrap_text(draw, scene.text, font, max_text_width)
    line_height = int(font_size * 1.3)
    text_y = int(height * 0.065)
    _draw_text_with_shadow(draw, (width // 2, text_y), lines, font, line_height, text_color)

    rule_width = int(width * 0.08)
    rule_y = text_y - int(font_size * 0.5)
    draw.rounded_rectangle(
        [width // 2 - rule_width // 2, rule_y, width // 2 + rule_width // 2, rule_y + 5], radius=3, fill=(*accent, 255),
    )

    card_top = text_y + line_height * len(lines) + int(height * 0.05)
    card_w = int(width * 0.84)
    card_h = int(height * 0.97) - card_top
    if card_h > int(card_w * 0.3):  # sanity floor — skip the card if there's no reasonable room left
        card = _render_browser_mockup(screenshot, (card_w, card_h))
        card_x = (width - card_w) // 2
        shadow_offset = int(width * 0.012)
        shadow = _drop_shadow_layer(
            (width, height),
            (card_x + shadow_offset, card_top + shadow_offset * 2, card_x + card_w + shadow_offset, card_top + card_h + shadow_offset * 2),
            int(min(card_w, card_h) * 0.04), int(width * 0.018),
        )
        image = Image.alpha_composite(image, shadow)
        image.paste(card, (card_x, card_top), card)

    return image.convert("RGB")


def _draw_text_with_shadow(draw: ImageDraw.ImageDraw, xy: tuple[int, int], lines: list[str], font, line_height: int, text_color: tuple[int, int, int]) -> None:
    x, y = xy
    shadow_color = (0, 0, 0, 140)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_x = x - (bbox[2] - bbox[0]) // 2
        draw.text((line_x + 3, y + 4), line, font=font, fill=shadow_color)
        draw.text((line_x, y), line, font=font, fill=text_color)
        y += line_height


def _build_master_frame(
    scene: Scene, brand_kit: VideoBrandKit | None, aspect_ratio: str, image_provider: ImageProvider | None = None,
) -> Image.Image:
    if scene.key in _MOCKUP_SCENE_KEYS and brand_kit and brand_kit.product_screenshot_url:
        screenshot = _fetch_product_screenshot(brand_kit.product_screenshot_url)
        if screenshot is not None:
            return _build_product_mockup_frame(scene, brand_kit, aspect_ratio, screenshot)

    final_w, final_h = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    width, height = int(final_w * _ZOOM_MASTER_SCALE), int(final_h * _ZOOM_MASTER_SCALE)

    bg_base = _hex_to_rgb(brand_kit.background_color if brand_kit else "", default=(10, 12, 20))
    accent = _hex_to_rgb(brand_kit.primary_color if brand_kit else "", default=(99, 102, 241))
    secondary = _hex_to_rgb(brand_kit.secondary_color if brand_kit else "", default=(139, 92, 246))
    text_color = _hex_to_rgb(brand_kit.text_color if brand_kit else "", default=(248, 250, 252))

    ai_background = _generate_ai_background(scene, image_provider, width, height)
    if ai_background is not None:
        # Real AI photography/illustration as the base, plus a dark scrim
        # behind the text zone for guaranteed legibility (see
        # _text_scrim_layer) — the model isn't asked to render any text.
        image = ai_background.convert("RGBA")
        image = Image.alpha_composite(image, _text_scrim_layer((width, height)))
    else:
        # Free-first fallback: a subtle vertical gradient base (never
        # flat), then two soft, large, heavily-blurred color blobs in the
        # brand's accent/secondary colors — the "gradient mesh" look used
        # across most modern SaaS marketing sites/videos (Linear, Stripe,
        # Vercel, etc).
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


def render_scene_animation(scene: Scene, brand_kit: VideoBrandKit | None, aspect_ratio: str, image_provider: ImageProvider | None = None):
    """Yields (frame_image, hold_duration_seconds) lazily, one at a time,
    whose durations sum to scene.duration_seconds — a slow zoom-in across
    the scene instead of one static held frame.

    Deliberately a generator, not a list: a 6-scene video can have 150-240
    full-resolution animation frames, and materializing all of them as PIL
    Images before saving any to disk was very likely OOM-killing the
    background render thread on Render's memory-constrained free tier
    (observed live: the thread died silently with an empty render_log,
    the classic symptom of the process being killed rather than erroring).
    The only thing held across the whole scene now is the one master
    frame; video_renderer.py saves each animation frame to disk and drops
    it immediately."""
    final_size = RESOLUTIONS.get(aspect_ratio, RESOLUTIONS["9:16"])
    master = _build_master_frame(scene, brand_kit, aspect_ratio, image_provider)

    frame_count = max(2, min(_MAX_FRAMES_PER_SCENE, round(scene.duration_seconds * _MOTION_FRAMES_PER_SECOND)))
    frame_duration = scene.duration_seconds / frame_count

    for i in range(frame_count):
        t = i / (frame_count - 1) if frame_count > 1 else 0.0
        yield (_zoom_crop(master, t, final_size), frame_duration)


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
