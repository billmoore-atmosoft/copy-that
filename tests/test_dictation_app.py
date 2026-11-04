"""Tests for DictationApp transcription threading."""
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from dictation_engine import DictationApp, DEFAULT_CONFIG


class TestTranscriptionThreading:
    """Verify transcription runs in background thread, not hotkey thread."""

    def test_toggle_recording_stop_does_not_block(self):
        """Stopping recording must return quickly (transcription in background)."""
        config = {**DEFAULT_CONFIG, "beep_on_start": False, "vad_enabled": False}
        app = DictationApp(config)

        # Mock the whisper model with a slow transcribe
        app.whisper = MagicMock()
        app.whisper.transcribe = MagicMock(side_effect=lambda *a, **kw: (time.sleep(0.5) or "hello"))
        app._model_ready.set()  # Mark model as loaded

        # Mock recorder to return some audio
        import numpy as np
        app.recorder = MagicMock()
        app.recorder.stop = MagicMock(return_value=np.full(16000, 0.05, dtype=np.float32))

        # Simulate: start recording, then stop
        app.start_recording()

        start = time.time()
        app.toggle_recording()
        elapsed = time.time() - start

        # toggle_recording should return quickly (< 200ms), not wait for transcription
        assert elapsed < 0.3, f"toggle_recording blocked for {elapsed:.2f}s — transcription must run in background"
        app.cancel()
        app._takes.wait_idle()
        app.stop()


def test_hotkey_while_loading_says_so_instead_of_failing_silently():
    app = DictationApp({**DEFAULT_CONFIG, "beep_on_start": False})
    seen = []
    app.add_callback(lambda state, data: seen.append(data))
    try:
        assert app.start_recording() is False
        assert seen[-1] == {"message": "Still loading, ready in a moment", "loading": True}
    finally:
        app.stop()
