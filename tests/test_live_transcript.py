import threading
import time

import numpy as np

from audio_chunks import TimedWord, WindowedTranscript, window_ranges
from live_transcript import LiveTranscript

SR = 16000


def speechlike(seconds, seed=0):
    """Loud audio with short quiet gaps, so window cuts move to pauses."""
    rng = np.random.default_rng(seed)
    audio = rng.uniform(-0.2, 0.2, int(seconds * SR)).astype(np.float32)
    for gap in range(3, int(seconds), 4):
        audio[gap * SR:gap * SR + SR // 4] = 0
    return audio


def fake_window(calls):
    """One word per 0.5s of audio, named by its absolute position."""
    def transcribe(samples, offset):
        calls.append((round(offset, 3), len(samples)))
        count = int(len(samples) / SR / 0.5)
        return [TimedWord(f"w{round(offset + i * 0.5, 2)}", offset + i * 0.5) for i in range(count)]
    return transcribe


def test_growing_recording_matches_whole_recording_for_any_arrival_pattern():
    audio = speechlike(70)
    batch = WindowedTranscript(fake_window([]))
    batch.advance(audio, final=True)
    for step in (0.3, 1.0, 4.7):
        calls = []
        live = WindowedTranscript(fake_window(calls))
        seen = 0
        while seen < len(audio):
            seen = min(len(audio), seen + int(step * SR))
            live.advance(audio[:seen])
        before_release = len(calls)
        live.advance(audio, final=True)
        assert live.text == batch.text
        # Only the window that was still open at release is left.
        assert len(calls) - before_release == 1
        assert before_release == len(list(window_ranges(audio))) - 1


def test_preview_commits_nothing():
    audio = speechlike(20)
    calls = []
    live = WindowedTranscript(fake_window(calls))
    live.advance(audio[:18 * SR])
    committed = list(live.words)
    preview = live.preview(audio[:18 * SR])
    assert live.words == committed
    assert len(preview) > len(committed)


class FakeModel:
    def __init__(self, delay=0.0):
        self.infer_lock = threading.Lock()
        self.delay = delay
        self.calls = []

    def windowed_transcript(self, sample_rate, language, cancelled=None):
        inner = fake_window(self.calls)
        def window(samples, offset):
            deadline = time.monotonic() + self.delay
            while time.monotonic() < deadline:
                if cancelled and cancelled():
                    from audio_chunks import Cancelled
                    raise Cancelled()
                time.sleep(0.005)
            return inner(samples, offset)
        return WindowedTranscript(window, sample_rate)


def test_live_session_recognizes_finished_windows_and_matches_batch():
    audio = speechlike(40)
    recorded = {"n": 0}
    texts = []
    model = FakeModel()
    live = LiveTranscript(model, lambda: audio[:recorded["n"]], SR, "en", texts.append, interval=0.01)
    for n in range(0, len(audio) + 1, SR):
        recorded["n"] = n
        time.sleep(0.03)
    text = live.finish(audio)
    batch = WindowedTranscript(fake_window([]))
    batch.advance(audio, final=True)
    assert text == batch.text
    assert live.windows_while_recording == len(list(window_ranges(audio))) - 1
    assert texts and texts[-1].startswith("w0")


def test_release_preempts_a_slow_live_pass():
    audio = speechlike(10)
    model = FakeModel(delay=5)
    live = LiveTranscript(model, lambda: audio, SR, "en", None, interval=0.01)
    time.sleep(0.1)  # A provisional pass is now running.
    model.delay = 0
    start = time.monotonic()
    live.finish(audio)
    assert time.monotonic() - start < 0.5


def test_live_session_skips_while_an_earlier_take_holds_the_model():
    audio = speechlike(30)
    model = FakeModel()
    model.infer_lock.acquire()
    live = LiveTranscript(model, lambda: audio, SR, "en", None, interval=0.01)
    time.sleep(0.1)
    assert model.calls == []
    model.infer_lock.release()
    assert live.finish(audio)
