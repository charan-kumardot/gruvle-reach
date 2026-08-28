"""Voiceover synthesis must self-validate its own output duration — a
pyttsx3/espeak-ng flakiness observed in production (Render's container)
can return a short-but-valid WAV file that only covers a fraction of the
requested text. Since video_renderer.py muxes audio with -shortest, an
undetected truncation would silently cut the whole video down to match a
few seconds of audio instead of failing over to a silent+captioned
render (§8, §40)."""
import wave
from pathlib import Path

from app.media.tts import synthesize_voiceover


def _write_silent_wav(path: Path, duration_seconds: float, framerate: int = 22050) -> None:
    n_frames = int(duration_seconds * framerate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(framerate)
        wav_file.writeframes(b"\x00\x00" * n_frames)


def test_empty_text_returns_false():
    assert synthesize_voiceover("", "unused.wav") is False


def test_truncated_recording_is_rejected(tmp_path, monkeypatch):
    """A ~70-word script synthesized as only 3 seconds of audio (the
    actual failure mode observed against production) must be rejected."""
    out_path = tmp_path / "voiceover.wav"
    long_text = " ".join(["word"] * 70)  # ~70 words, needs >= ~7s even at a very fast speaking rate

    class _FakeEngine:
        def save_to_file(self, text, path):
            _write_silent_wav(Path(path), duration_seconds=3.0)

        def runAndWait(self):
            pass

        def stop(self):
            pass

    import sys
    import types

    fake_pyttsx3 = types.ModuleType("pyttsx3")
    fake_pyttsx3.init = lambda: _FakeEngine()
    monkeypatch.setitem(sys.modules, "pyttsx3", fake_pyttsx3)

    assert synthesize_voiceover(long_text, str(out_path)) is False


def test_plausible_duration_recording_is_accepted(tmp_path, monkeypatch):
    out_path = tmp_path / "voiceover.wav"
    text = "Ever wonder why your latest deploy blew up"  # 7 words

    class _FakeEngine:
        def save_to_file(self, text, path):
            _write_silent_wav(Path(path), duration_seconds=3.0)  # plausible for 7 words

        def runAndWait(self):
            pass

        def stop(self):
            pass

    import sys
    import types

    fake_pyttsx3 = types.ModuleType("pyttsx3")
    fake_pyttsx3.init = lambda: _FakeEngine()
    monkeypatch.setitem(sys.modules, "pyttsx3", fake_pyttsx3)

    assert synthesize_voiceover(text, str(out_path)) is True
