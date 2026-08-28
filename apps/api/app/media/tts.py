"""
Free-first voiceover — pyttsx3 over the espeak/espeak-ng backend (installed
in the Dockerfile), offline, no API key, file-only synthesis (no audio
device needed in a headless container). Voiceover is never a hard
dependency: any failure here — missing library, no backend found, empty
text, or a suspiciously truncated recording — returns False so the render
pipeline falls back to a silent video with burned-in captions rather than
failing (or silently shipping a truncated video) the whole render (§8, §40).
"""
import logging
import wave
from pathlib import Path

logger = logging.getLogger(__name__)

# pyttsx3's espeak-ng driver has a known flakiness in headless/threaded
# environments (observed on Render's container): runAndWait() can return
# before synthesis of the full text actually completes, leaving a short,
# valid-but-truncated WAV file. Since video_renderer.py muxes with
# `-shortest`, a truncated track would silently cut the whole video down to
# match it rather than failing loudly — so the file existing and being
# non-empty isn't enough; its duration has to be plausible for the text.
_MAX_PLAUSIBLE_WORDS_PER_SECOND = 5.0
_MIN_DURATION_SAFETY_MARGIN = 0.5


def _synthesized_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        return frames / float(rate) if rate else 0.0


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
    if not path.exists() or path.stat().st_size == 0:
        return False

    word_count = len(text.split())
    min_expected_seconds = (word_count / _MAX_PLAUSIBLE_WORDS_PER_SECOND) * _MIN_DURATION_SAFETY_MARGIN
    try:
        actual_seconds = _synthesized_duration_seconds(path)
    except Exception as exc:  # noqa: BLE001 — an unreadable/malformed WAV is a failed synthesis
        logger.info("Could not read synthesized voiceover (%s) — falling back to a silent video", exc)
        return False

    if actual_seconds < min_expected_seconds:
        logger.warning(
            "Voiceover looks truncated (%.1fs for %d words, expected at least %.1fs) — "
            "falling back to a silent video rather than shipping a cut-off recording",
            actual_seconds, word_count, min_expected_seconds,
        )
        return False

    return True
