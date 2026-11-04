import threading
import time
import pytest
from cleanup import OpenVINOCleanup


def test_deadline_returns_without_allowing_concurrent_native_generation():
    model = OpenVINOCleanup.__new__(OpenVINOCleanup)
    model.config = {"cleanup_timeout_seconds": 0.05}
    model._generation_lock = threading.Lock()
    release = threading.Event()
    model._generate = lambda *args: release.wait(1) or "text"
    start = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            model.generate("text", "cursor.exe", lambda: False)
        assert time.monotonic() - start < 0.25
        assert model.busy
        with pytest.raises(TimeoutError):
            model.generate("second", "cursor.exe", lambda: False)
    finally:
        release.set()
    deadline = time.monotonic() + 1
    while model.busy and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not model.busy
