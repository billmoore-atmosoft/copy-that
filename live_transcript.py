"""Recognize a take while it is being recorded.

Windows that are complete are recognized during the take, so release only
waits for the last one. A provisional pass over the open tail feeds the live
text display and keeps the accelerators clocked up; it never affects the
final transcript and yields the devices as soon as the take is released.
"""
import threading

from audio_chunks import Cancelled


class LiveTranscript:
    def __init__(self, model, snapshot, sample_rate=16000, language="en", on_text=None,
                 interval=0.3, log=lambda message: None):
        self._model, self._snapshot, self._sample_rate = model, snapshot, sample_rate
        self._on_text, self._interval, self._log = on_text, interval, log
        self._stopped, self._preempt = threading.Event(), threading.Event()
        self._transcript = model.windowed_transcript(sample_rate, language, cancelled=self._preempt.is_set)
        self._seen = 0
        self.windows_while_recording = 0
        self._thread = threading.Thread(target=self._run, name="live-transcript", daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stopped.wait(self._interval):
            audio = self._snapshot()
            # Short gaps keep the GPU clocked up: after a 1s idle gap a pass
            # took 0.5-0.7s, back to back 0.02-0.07s for the decoder.
            if len(audio) - self._seen < self._sample_rate * 0.3:
                continue
            # An earlier take may still be recognized; never delay it.
            if not self._model.infer_lock.acquire(blocking=False):
                continue
            try:
                self.windows_while_recording += self._transcript.advance(audio)
                if self._on_text and not self._stopped.is_set():
                    words = self._transcript.preview(audio)
                    if not self._stopped.is_set():
                        self._on_text(" ".join(word.text for word in words))
                self._seen = len(audio)
            except Cancelled:
                return
            except Exception as error:
                self._log(f"Live recognition stopped ({type(error).__name__})")
                return
            finally:
                self._model.infer_lock.release()

    def stop(self):
        """Stop live passes without waiting; safe to call more than once."""
        self._stopped.set()
        self._preempt.set()

    def finish(self, audio):
        """Final transcript of the whole take; identical to recognizing it at once."""
        self.stop()
        self._thread.join()
        self._preempt.clear()
        with self._model.infer_lock:
            self._transcript.advance(audio, final=True)
        return self._transcript.text
