"""Conservative voice detection before ASR, without trimming the recorded take."""
import numpy as np


def has_speech(audio, sample_rate=16000, detector=None):
    if sample_rate != 16000:
        raise ValueError("Voice detection expects 16kHz mono audio")
    samples = np.asarray(audio, dtype=np.float32).flatten()
    if not len(samples) or not np.isfinite(samples).all():
        return False
    if float(np.sqrt(np.mean(samples * samples))) < 0.0001:
        return False
    if detector is None:
        import webrtcvad
        detector = webrtcvad.Vad(1)
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    frame_samples = 480  # 30ms; do not pad an incomplete last frame.
    voiced = 0
    for start in range(0, len(pcm) - frame_samples + 1, frame_samples):
        if detector.is_speech(pcm[start:start + frame_samples].tobytes(), sample_rate):
            voiced += 1
            if voiced >= 6:  # 180ms avoids the detector's initial noise hangover.
                return True
    return False
