from unittest.mock import Mock
import numpy as np
from speech_gate import has_speech


def test_silence_and_invalid_audio_never_reach_detector():
    detector = Mock()
    for audio in ([], np.zeros(16000), [np.nan], [np.inf]):
        assert not has_speech(audio, detector=detector)
    detector.is_speech.assert_not_called()


def test_requires_multiple_voiced_frames_and_does_not_pad_short_tail():
    audio = np.full(480 * 3 + 100, 0.05, dtype=np.float32)
    detector = Mock()
    detector.is_speech.side_effect = [True, False, True]
    assert not has_speech(audio, detector=detector)
    assert detector.is_speech.call_count == 3
    for call in detector.is_speech.call_args_list:
        assert len(call.args[0]) == 960
        assert call.args[1] == 16000
    detector.is_speech.side_effect = [True] * 6
    assert has_speech(np.tile(audio[:480], 6), detector=detector)


def test_real_detector_rejects_quiet_background_noise():
    audio = np.random.default_rng(73).normal(0, 0.0005, 32000).astype(np.float32)
    assert not has_speech(audio)
