"""Product screenshot -> premium browser mockup compositing (per the
user's explicit direction: real product screenshots, not AI-generated or
web-searched imagery — see app/providers/image/factory.py for why)."""
from PIL import Image, ImageDraw

from app.agents.video_agent import Scene
from app.db.models.video import VideoBrandKit
from app.media.scene_renderer import RESOLUTIONS, _build_product_mockup_frame, _contain_resize, _render_browser_mockup


def _fake_screenshot(size=(1400, 900)) -> Image.Image:
    image = Image.new("RGB", size, (255, 255, 255))
    ImageDraw.Draw(image).rectangle([0, 0, size[0], 80], fill=(30, 41, 59))
    return image


def test_contain_resize_never_crops_and_preserves_aspect_ratio():
    src = _fake_screenshot((1400, 900))  # 14:9
    fitted = _contain_resize(src, (700, 700))  # fit inside a square
    assert fitted.width <= 700 and fitted.height <= 700
    assert abs((fitted.width / fitted.height) - (1400 / 900)) < 0.01


def test_render_browser_mockup_produces_correct_card_size():
    card = _render_browser_mockup(_fake_screenshot(), (600, 900))
    assert card.size == (600, 900)
    assert card.mode == "RGBA"


def test_build_product_mockup_frame_produces_master_sized_image():
    scene = Scene(key="product", text="Gruvle Radar detects changes across your stack.", duration_seconds=3.0)
    kit = VideoBrandKit(workspace_id=None, product_id=None)  # uses column defaults
    master = _build_product_mockup_frame(scene, kit, "9:16", _fake_screenshot())
    final_w, final_h = RESOLUTIONS["9:16"]
    # Master is rendered larger than final size for the Ken Burns zoom crop.
    assert master.width > final_w and master.height > final_h
    assert master.mode == "RGB"


def test_build_product_mockup_frame_works_with_no_brand_kit():
    scene = Scene(key="solution", text="Watches the changes that matter.", duration_seconds=3.0)
    master = _build_product_mockup_frame(scene, None, "1:1", _fake_screenshot())
    assert master.mode == "RGB"
    assert master.width > 0 and master.height > 0
