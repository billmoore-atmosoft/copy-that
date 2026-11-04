"""Tests for AudioRecorder thread safety and timeout."""
import threading
import time
import numpy as np
import pytest

from dictation_engine import AudioRecorder


class TestAudioRecorderThreadSafety:
    """Verify AudioRecorder uses proper synchronization."""

    def test_frames_list_has_lock(self):
        """AudioRecorder must use a lock when accessing _frames."""
        recorder = AudioRecorder(sample_rate=16000)
        assert hasattr(recorder, '_lock'), "AudioRecorder must have a _lock attribute"
        assert isinstance(recorder._lock, type(threading.Lock()))

    def test_stop_returns_empty_when_not_started(self):
        recorder = AudioRecorder(sample_rate=16000)
        audio = recorder.stop()
        assert len(audio) == 0
        assert audio.dtype == np.float32


class TestAudioRecorderTimeout:
    """Verify max_record_seconds is enforced."""

    def test_max_record_seconds_stops_recording(self):
        """Recording should auto-stop after max_record_seconds."""
        recorder = AudioRecorder(sample_rate=16000, max_record_seconds=1)
        assert hasattr(recorder, 'max_record_seconds')
        assert recorder.max_record_seconds == 1

    def test_default_max_record_seconds_is_none(self):
        """Default recorder has no timeout."""
        recorder = AudioRecorder(sample_rate=16000)
        assert recorder.max_record_seconds is None


class SlowCloseStream:
    """Fake PortAudio stream: stop delivers a final block, close is slow."""
    instances = []

    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.closed = threading.Event()
        SlowCloseStream.instances.append(self)

    def start(self):
        self.callback(np.ones((1024, 1), np.float32), 1024, None, None)

    def stop(self):
        self.callback(np.ones((512, 1), np.float32), 512, None, None)

    def close(self):
        time.sleep(0.3)
        self.closed.set()


class TestAudioRecorderRelease:
    def test_stop_keeps_final_block_without_waiting_for_close(self, monkeypatch):
        import types, sys
        monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=SlowCloseStream))
        recorder = AudioRecorder(sample_rate=16000)
        recorder.start()
        started = time.monotonic()
        audio = recorder.stop()
        assert time.monotonic() - started < 0.2
        assert len(audio) == 1536
        assert not SlowCloseStream.instances[-1].closed.is_set()

    def test_start_waits_for_previous_close(self, monkeypatch):
        import types, sys
        monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=SlowCloseStream))
        recorder = AudioRecorder(sample_rate=16000)
        recorder.start()
        recorder.stop()
        previous = SlowCloseStream.instances[-1]
        recorder.start()
        assert previous.closed.is_set()
        recorder.stop()


class TestAudioRecorderLimitWarning:
    def test_warning_fires_before_limit_and_is_cancelled_by_stop(self, monkeypatch):
        import types, sys
        monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=SlowCloseStream))
        warned = threading.Event()
        recorder = AudioRecorder(sample_rate=16000, max_record_seconds=0.3,
                                 on_timeout=lambda: None, on_warning=warned.set, warning_seconds=0.2)
        recorder.start()
        assert warned.wait(1)
        recorder.stop()
        early = threading.Event()
        recorder = AudioRecorder(sample_rate=16000, max_record_seconds=0.5,
                                 on_timeout=lambda: None, on_warning=early.set, warning_seconds=0.2)
        recorder.start()
        recorder.stop()
        time.sleep(0.4)
        assert not early.is_set()


class SilentThenLiveStream(SlowCloseStream):
    def start(self):
        self.callback(np.zeros((1024, 1), np.float32), 1024, None, None)


class TestAudioRecorderLive:
    def test_live_only_after_non_zero_audio(self, monkeypatch):
        import types, sys
        monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(InputStream=SilentThenLiveStream))
        recorder = AudioRecorder(sample_rate=16000)
        recorder.start()
        assert not recorder.live.is_set()  # A waking device sends exact zeros.
        stream = SilentThenLiveStream.instances[-1]
        stream.callback(np.full((1024, 1), 0.01, np.float32), 1024, None, None)
        assert recorder.live.is_set()
        recorder.stop()


class FakeOutput:
    instances = []

    def __init__(self, callback, **kwargs):
        self.callback = callback
        self.closed = False
        FakeOutput.instances.append(self)

    def start(self):
        pass

    def stop(self):
        pass

    def close(self):
        self.closed = True


class TestCuePlayer:
    def test_stalled_output_is_replaced_instead_of_swallowing_cues(self, monkeypatch):
        import types, sys
        import dictation_engine
        monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(OutputStream=FakeOutput))
        player = dictation_engine.CuePlayer()
        assert player.hold()
        first = FakeOutput.instances[-1]
        player._last_fill -= 1.0  # The device stopped requesting audio.
        player.play(np.ones(10, np.float32))
        time.sleep(0.3)
        second = FakeOutput.instances[-1]
        assert second is not first and first.closed
        out = np.zeros((16, 1), np.float32)
        second.callback(out, 16, None, None)
        assert out[:10, 0].tolist() == [1.0] * 10
        player.release()
