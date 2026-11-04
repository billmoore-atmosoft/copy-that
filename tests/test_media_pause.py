"""Pause only what is playing; resume only what was paused."""
from media_pause import MediaPause


class Done:
    def __init__(self, value=True):
        self.value = value

    def get(self):
        return self.value


class Player:
    def __init__(self, playing):
        self.playing = playing
        self.calls = []

    def try_pause_async(self):
        self.calls.append("pause")
        self.playing = False
        return Done()

    def try_play_async(self):
        self.calls.append("play")
        self.playing = True
        return Done()


def media(players):
    pauser = MediaPause(lambda message: None, lambda: players, lambda player: player.playing)
    return pauser


def test_pauses_only_playing_and_resumes_only_those():
    music, stopped = Player(True), Player(False)
    pauser = media([music, stopped])
    pauser._pause()
    pauser._resume()
    assert music.calls == ["pause", "play"]
    assert stopped.calls == []


def test_resume_without_pause_does_nothing():
    music = Player(True)
    pauser = media([music])
    pauser._resume()
    assert music.calls == []


def test_a_broken_player_does_not_stop_the_rest():
    class Closed(Player):
        def try_pause_async(self):
            raise OSError("closed")
    music = Player(True)
    pauser = media([Closed(True), music])
    pauser._pause()
    assert music.calls == ["pause"]
    assert pauser._paused == [music]
