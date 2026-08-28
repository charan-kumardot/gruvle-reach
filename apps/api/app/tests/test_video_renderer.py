"""Free-first video render pipeline (§8-10, §16, §40) — must produce a
real, playable mp4 from a short fixture script using the actual FFmpeg
binary, with no voiceover required to pass (silent + burned-in-caption
fallback is the documented, acceptable baseline)."""
import shutil
from pathlib import Path

import pytest

from app.agents.video_agent import Scene
from app.media.video_renderer import render_video

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg binary not available in this environment")


def test_render_produces_a_playable_mp4_from_two_scenes():
    scenes = [
        Scene(key="hook", text="Your API didn't break. It changed.", duration_seconds=2.0),
        Scene(key="cta", text="Know what changed before it affects your business.", duration_seconds=2.0),
    ]

    result = render_video(scenes, brand_kit=None, aspect_ratio="9:16")
    try:
        assert result.success is True, result.error or result.render_log
        assert Path(result.local_path).exists()
        assert Path(result.local_path).stat().st_size > 1000  # a real encoded video, not an empty/corrupt file
        # 4.0s of scene animation + one ~0.28s crossfade transition between them.
        assert result.duration_seconds == pytest.approx(4.28, abs=0.05)
    finally:
        if result.workdir:
            shutil.rmtree(result.workdir, ignore_errors=True)


def test_render_with_no_scenes_fails_cleanly():
    result = render_video([], brand_kit=None, aspect_ratio="9:16")
    assert result.success is False
    assert result.error
