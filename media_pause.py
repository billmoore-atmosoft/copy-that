"""Pause playing media while the user dictates, then resume it.

Uses Windows' media sessions (the ones the volume flyout shows), so only
players that are actually playing are paused, and only those are resumed.
Never sends the play/pause key, which would start paused players. Calls run
in order on one thread, off the hotkey and recording paths.
"""
import queue
import threading


def _sessions():
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    return list(GlobalSystemMediaTransportControlsSessionManager.request_async().get().get_sessions())


def _playing(session):
    from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionPlaybackStatus
    return session.get_playback_info().playback_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING


class MediaPause:
    def __init__(self, log, sessions=None, playing=None):
        self.log = log
        self._sessions, self._is_playing = sessions or _sessions, playing or _playing
        self._paused = []
        self._jobs = queue.SimpleQueue()
        self._thread = None

    def pause(self):
        self._submit(self._pause)

    def resume(self):
        self._submit(self._resume)

    def _submit(self, job):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="media-pause", daemon=True)
            self._thread.start()
        self._jobs.put(job)

    def _run(self):
        while True:
            job = self._jobs.get()
            try:
                job()
            except Exception as error:
                self.log(f"Media pause failed ({type(error).__name__})")

    def _pause(self):
        for session in self._sessions():
            try:
                if self._is_playing(session) and session.try_pause_async().get():
                    self._paused.append(session)
            except Exception:
                pass  # A player that closed or refuses is left alone.
        if self._paused:
            self.log(f"Media: paused {len(self._paused)} player(s)")

    def _resume(self):
        paused, self._paused = self._paused, []
        for session in paused:
            try:
                session.try_play_async().get()
            except Exception:
                pass
        if paused:
            self.log(f"Media: resumed {len(paused)} player(s)")
