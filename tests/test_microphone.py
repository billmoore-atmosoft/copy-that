from unittest.mock import Mock, patch
from dictation_engine import AudioRecorder, DictationApp, DEFAULT_CONFIG


def test_recorder_uses_selected_input_device():
    recorder = AudioRecorder(input_device=7)
    with patch("sounddevice.InputStream") as stream:
        recorder.start()
        assert stream.call_args.kwargs["device"] == 7
        recorder.stop()


def test_saved_device_identity_is_resolved_after_index_changes():
    app = DictationApp({**DEFAULT_CONFIG, "input_device": 7,
                       "input_device_key": "WASAPI:USB Mic", "beep_on_start": False})
    app._model_ready.set()
    app.recorder = Mock()
    with patch.object(app, "list_input_devices", return_value=[{"index": 12, "key": "WASAPI:USB Mic"}]):
        assert app.start_recording()
        assert app.recorder.input_device == 12
    app.cancel()
    app.stop()


def test_unplugged_selected_mic_does_not_silently_use_another():
    app = DictationApp({**DEFAULT_CONFIG, "input_device_key": "WASAPI:USB Mic", "beep_on_start": False})
    app._model_ready.set()
    app.recorder = Mock()
    with patch.object(app, "list_input_devices", return_value=[]):
        assert not app.start_recording()
    app.recorder.start.assert_not_called()
    app.stop()


def test_mic_list_shows_each_device_once_with_full_names():
    devices = [
        {"name": "Microsoft Sound Mapper - Input", "hostapi": 0, "max_input_channels": 2},
        {"name": "Microphone (EMEET OfficeCore M0", "hostapi": 0, "max_input_channels": 2},
        {"name": "Speakers", "hostapi": 2, "max_input_channels": 0},
        {"name": "Microphone (EMEET OfficeCore M0 Plus)", "hostapi": 1, "max_input_channels": 2},
        {"name": "Microphone (EMEET OfficeCore M0 Plus)", "hostapi": 2, "max_input_channels": 2},
    ]
    hosts = [{"name": "MME"}, {"name": "Windows DirectSound"}, {"name": "Windows WASAPI"}]
    with patch("sounddevice.query_devices", return_value=devices), \
         patch("sounddevice.query_hostapis", side_effect=lambda i: hosts[i]):
        listed = DictationApp.list_input_devices()
    assert [(d["index"], d["label"]) for d in listed] == [(4, "Microphone (EMEET OfficeCore M0 Plus)")]


def test_key_saved_from_truncated_mme_name_finds_the_wasapi_device():
    from dictation_runtime import find_input_device
    devices = [{"index": 28, "name": "Microphone (EMEET OfficeCore M0 Plus)",
                "key": "Windows WASAPI:Microphone (EMEET OfficeCore M0 Plus)"},
               {"index": 27, "name": "Microphone (BY-V)", "key": "Windows WASAPI:Microphone (BY-V)"}]
    assert find_input_device(devices, "MME:Microphone (EMEET OfficeCore M0")["index"] == 28
    assert find_input_device(devices, "MME:Microphone (BY-V)")["index"] == 27
    assert find_input_device(devices, "MME:Microphone (Other)") is None


def test_wasapi_mic_opens_with_rate_conversion():
    recorder = AudioRecorder(input_device=4)
    with patch("sounddevice.InputStream") as stream, \
         patch("sounddevice.query_devices", return_value={"hostapi": 2}), \
         patch("sounddevice.query_hostapis", return_value={"name": "Windows WASAPI"}):
        recorder.start()
        assert stream.call_args.kwargs["extra_settings"] is not None
        recorder.stop()
