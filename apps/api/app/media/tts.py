"""
Free-first voiceover — pyttsx3 over the espeak/espeak-ng backend (installed
in the Dockerfile), offline, no API key, file-only synthesis (no audio
device needed in a headless container). Voiceover is never a hard
dependency: any failure here — missing library, no backend found, empty
text — returns False so the render pipeline falls back to a silent video
with burned-in captions rather than failing the whole render (§8, §40).
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def synthesize_voiceover(text: str, out_path: str) -> bool:
    if not text.strip():
        return False
    try:
        import pyttsx3
    except ImportError:
        logger.info("pyttsx3 not installed — skipping voiceover, video will be silent with captions")
        return False

    try:
        engine = pyttsx3.init()
        engine.save_to_file(text, out_path)
        engine.runAndWait()
        engine.stop()
    except Exception as exc:  # noqa: BLE001 — any TTS backend failure is non-fatal
        logger.info("Voiceover synthesis failed (%s) — falling back to a silent video", exc)
        return False

    path = Path(out_path)
    return path.exists() and path.stat().st_size > 0
