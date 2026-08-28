"""
FFmpeg orchestration via subprocess — deliberately no ffmpeg-python/moviepy
dependency, keeping this light per the codebase's existing dependency
posture. Composes each scene's Ken Burns zoom animation (scene_renderer.py)
plus short crossfade transitions between scenes into one concat-demuxer
timeline — still a single simple `ffmpeg -f concat` call, no filter_complex
graph, so render cost/reliability stays the same shape as the original
one-static-frame-per-scene version despite the much richer motion.
"""
import logging
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.agents.video_agent import Scene
from app.db.models.video import VideoBrandKit
from app.media.scene_renderer import render_scene_animation, render_transition_frames
from app.media.tts import synthesize_voiceover
from app.providers.image.factory import get_image_provider

logger = logging.getLogger(__name__)

FFMPEG_TIMEOUT_SECONDS = 120


@dataclass
class RenderResult:
    success: bool
    local_path: str = ""
    workdir: str = ""  # scratch temp dir — caller deletes it (shutil.rmtree) after uploading local_path
    duration_seconds: float = 0.0
    has_voiceover: bool = False
    render_log: str = ""
    error: str = ""


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def render_video(scenes: list[Scene], *, brand_kit: VideoBrandKit | None, aspect_ratio: str) -> RenderResult:
    if not scenes:
        return RenderResult(success=False, error="No scenes to render")
    if not _ffmpeg_available():
        return RenderResult(success=False, error="ffmpeg binary not found on PATH")

    workdir = Path(tempfile.mkdtemp(prefix="gruvle_video_"))
    log_lines: list[str] = []
    try:
        # Stream every frame straight to disk as it's generated — a 6-scene
        # video can have 150-240 full-resolution animation frames, and
        # holding them all as PIL Images at once (the previous approach)
        # was very likely OOM-killing the background render thread on
        # Render's memory-constrained free tier. At most two frames (the
        # previous scene's last frame + the current scene's first, for the
        # crossfade between them) are ever held in memory simultaneously.
        frame_paths: list[Path] = []
        frame_durations: list[float] = []
        prev_scene_last_frame = None
        frame_idx = 0

        def _save_frame(image) -> None:
            nonlocal frame_idx
            frame_path = workdir / f"frame_{frame_idx:04d}.png"
            image.save(frame_path, format="PNG")
            frame_paths.append(frame_path)
            frame_idx += 1

        image_provider = get_image_provider()
        for scene in scenes:
            is_first_frame_of_scene = True
            last_frame_of_scene = None
            for image, duration in render_scene_animation(scene, brand_kit, aspect_ratio, image_provider):
                if is_first_frame_of_scene and prev_scene_last_frame is not None:
                    for t_image, t_duration in render_transition_frames(prev_scene_last_frame, image):
                        _save_frame(t_image)
                        frame_durations.append(t_duration)
                is_first_frame_of_scene = False
                _save_frame(image)
                frame_durations.append(duration)
                last_frame_of_scene = image
            prev_scene_last_frame = last_frame_of_scene

        if not frame_paths:
            return RenderResult(success=False, error="No frames were rendered")

        list_path = workdir / "concat_list.txt"
        with list_path.open("w", encoding="utf-8") as f:
            for frame_path, duration in zip(frame_paths, frame_durations):
                posix_path = frame_path.as_posix()
                f.write(f"file '{posix_path}'\n")
                f.write(f"duration {duration}\n")
            # concat demuxer quirk: the last entry's duration is ignored
            # unless the file is listed once more without a duration.
            f.write(f"file '{frame_paths[-1].as_posix()}'\n")

        total_duration = sum(frame_durations)

        narration = " ... ".join(scene.text for scene in scenes)
        voiceover_path = workdir / "voiceover.wav"
        has_voiceover = synthesize_voiceover(narration, str(voiceover_path))

        output_path = workdir / f"{uuid.uuid4().hex}.mp4"
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_path)]
        if has_voiceover:
            cmd += ["-i", str(voiceover_path)]
        cmd += ["-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if has_voiceover:
            cmd += ["-c:a", "aac", "-shortest"]
        cmd += [str(output_path)]

        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT_SECONDS)
        log_lines.append(" ".join(cmd))
        log_lines.append(f"{len(frame_paths)} frames")
        log_lines.append(proc.stderr[-4000:])

        if proc.returncode != 0 or not output_path.exists():
            shutil.rmtree(workdir, ignore_errors=True)
            return RenderResult(success=False, render_log="\n".join(log_lines), error=f"ffmpeg exited {proc.returncode}")

        return RenderResult(
            success=True, local_path=str(output_path), workdir=str(workdir), duration_seconds=total_duration,
            has_voiceover=has_voiceover, render_log="\n".join(log_lines),
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(workdir, ignore_errors=True)
        return RenderResult(success=False, render_log="\n".join(log_lines), error="ffmpeg render timed out")
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(workdir, ignore_errors=True)
        return RenderResult(success=False, render_log="\n".join(log_lines), error=str(exc))
