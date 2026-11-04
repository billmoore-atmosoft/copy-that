"""Pinned downloads, cancel, removal, and the app's model actions."""
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import model_store
from model_store import Cancelled, Downloads, download, installed, remove


def fake_snapshot(files, block=None):
    """Stand-in for snapshot_download that writes files and reports bytes through tqdm_class."""
    def snapshot_download(repo, revision, local_dir, tqdm_class, ignore_patterns):
        bar = tqdm_class(total=sum(len(body) for body in files.values()), unit="B")
        for name, body in files.items():
            if block:
                block.wait(2)
            (Path(local_dir) / name).write_text(body)
            bar.update(len(body))
        return local_dir
    return snapshot_download


@pytest.fixture
def hub(monkeypatch):
    import huggingface_hub
    calls = {}

    def install(files, block=None):
        snapshot = fake_snapshot(files, block)

        def recording(*args, **kwargs):
            calls.update(kwargs, repo=args[0])
            return snapshot(*args, **kwargs)
        monkeypatch.setattr(huggingface_hub, "snapshot_download", recording)
        return calls
    return install


def test_download_pins_revision_and_writes_manifest_last(hub, tmp_path):
    calls = hub({"model.xml": "graph", "model.bin": "weights"})
    progress = []
    manifest = download("org/model", tmp_path / "m", revision="abc", progress=progress.append)
    assert calls["revision"] == "abc" and calls["repo"] == "org/model"
    assert manifest["files"] == {"model.xml": 5, "model.bin": 7}
    assert installed(tmp_path / "m") and progress[-1] == 1.0
    model_store.verify(tmp_path / "m")


def test_cancel_deletes_partial_download(hub, tmp_path):
    hub({"model.xml": "graph", "model.bin": "weights"})
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        download("org/model", tmp_path / "m", revision="abc", cancel=cancel)
    assert not (tmp_path / "m").exists()


def test_snapshot_without_graphs_is_not_installed(hub, tmp_path):
    hub({"readme.txt": "hello"})
    with pytest.raises(RuntimeError, match="no model graphs"):
        download("org/model", tmp_path / "m", revision="abc")
    assert not installed(tmp_path / "m")


def test_downloads_report_progress_and_completion(tmp_path):
    release, finished = threading.Event(), threading.Event()
    results = []

    def slow_download(repo, directory, revision, cancel, progress):
        progress(0.5)
        release.wait(2)

    jobs = Downloads(on_done=lambda key, error: (results.append((key, error)), finished.set()),
                     download_fn=slow_download)
    jobs.start("speech:parakeet", "org/model", "abc", tmp_path)
    jobs.start("speech:parakeet", "org/model", "abc", tmp_path)  # Ignored while running
    for _ in range(100):
        if jobs.fraction("speech:parakeet") == 0.5:
            break
        threading.Event().wait(0.01)
    assert jobs.fraction("speech:parakeet") == 0.5 and jobs.active()
    release.set()
    assert finished.wait(2)
    assert results == [("speech:parakeet", None)] and jobs.fraction("speech:parakeet") is None


def test_remove_deletes_folder(tmp_path):
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "model.xml").write_text("x")
    remove(tmp_path / "m")
    assert not (tmp_path / "m").exists()


# -- App model actions -------------------------------------------------------

def installed_model(directory):
    directory.mkdir(parents=True)
    (directory / "model.xml").write_text("x")
    (directory / "model-manifest.json").write_text('{"files": {"model.xml": 1}}')


@pytest.fixture
def app(monkeypatch, tmp_path):
    import app as app_module
    from dictation_engine import DEFAULT_CONFIG, AppState
    monkeypatch.setattr(app_module, "MODEL_DIR", tmp_path)
    monkeypatch.setattr("dictation_engine.MODEL_DIR", tmp_path)
    monkeypatch.setattr(app_module, "save_config", lambda config: None)
    gui = app_module.GUIApp.__new__(app_module.GUIApp)
    gui._config = {**DEFAULT_CONFIG, "model_size": "small",
                   "cleanup_enabled": True, "cleanup_model_path": str(tmp_path / "Qwen3-8B-int4-ov")}
    gui._downloads = MagicMock(fraction=MagicMock(return_value=None))
    gui._engine = MagicMock(active=False, state=AppState.READY)
    gui._engine_started, gui._offer_delete, gui._first_run, gui._closing = True, [], False, False
    gui._settings_win = gui._welcome = None
    gui._overlay, gui._tray, gui._theme_controller = MagicMock(), MagicMock(), MagicMock()
    gui._root = MagicMock()
    gui._restart_engine = MagicMock()
    return gui


def test_model_state_marks_models_in_use(app, tmp_path):
    installed_model(tmp_path / "whisper-small-openvino")
    installed_model(tmp_path / "whisper-base-openvino")
    installed_model(tmp_path / "Qwen3-8B-int4-ov")
    assert app.model_state("speech", "small") == ("installed", 1.0)
    assert app.model_state("speech", "base") == ("removable", 1.0)
    assert app.model_state("speech", "parakeet") == ("available", 0.0)
    assert app.model_state("cleanup", "8b") == ("installed", 1.0)
    app._downloads.fraction.return_value = 0.25
    assert app.model_state("speech", "parakeet") == ("downloading", 0.25)


def test_download_uses_pinned_revision(app, tmp_path):
    from dictation_engine import MODEL_REGISTRY
    app.download_model("speech", "parakeet")
    info = MODEL_REGISTRY["parakeet"]
    app._downloads.start.assert_called_once_with(
        "speech:parakeet", info["ov_repo"], info["revision"], tmp_path / info["local_dir"])


def test_switching_models_offers_old_ones_for_deletion(app, tmp_path, monkeypatch):
    for name in ("whisper-small-openvino", "parakeet-tdt-openvino", "Qwen3-8B-int4-ov", "Qwen3-4B-int4-ov"):
        installed_model(tmp_path / name)
    offered = []
    monkeypatch.setattr("ui.dialogs.confirm", lambda root, title, message, yes, no, on_yes: offered.append((message, on_yes)))
    app._on_settings_apply({**app._config, "model_size": "parakeet", "device": "GPU",
                            "cleanup_model_path": str(tmp_path / "Qwen3-4B-int4-ov")})
    app._restart_engine.assert_called_once()
    assert app._offer_delete == [("speech", "small"), ("cleanup", "8b")]
    app._offer_deletes()
    message, delete = offered[0]
    assert "Whisper Small and Thorough polish (Qwen3 8B)" in message and "5.1 GB" in message
    delete()
    assert not (tmp_path / "whisper-small-openvino").exists()
    assert not (tmp_path / "Qwen3-8B-int4-ov").exists()
    assert (tmp_path / "parakeet-tdt-openvino").exists()


def test_models_in_use_are_never_deleted(app, tmp_path):
    installed_model(tmp_path / "whisper-small-openvino")
    app._delete_models([("speech", "small")])
    assert (tmp_path / "whisper-small-openvino").exists()


def test_first_run_starts_speech_then_cleanup(app, tmp_path):
    app._config.update(model_size="base", cleanup_enabled=False)
    app._start_first_run()
    app._downloads.start.assert_called_once()
    assert app._downloads.start.call_args[0][0] == "speech:parakeet"
    installed_model(tmp_path / "parakeet-tdt-openvino")
    app._download_finished("speech:parakeet", None)
    assert app._config["model_size"] == "parakeet" and app._config["device"] == "GPU"
    app._restart_engine.assert_called_once()
    assert app._downloads.start.call_args[0][0] == "cleanup:4b"
    installed_model(tmp_path / "Qwen3-4B-int4-ov")
    app._download_finished("cleanup:4b", None)
    assert app._config["cleanup_enabled"] is True
    assert Path(app._config["cleanup_model_path"]) == tmp_path / "Qwen3-4B-int4-ov"


def test_failed_download_stops_first_run(app):
    app._first_run = True
    app._download_finished("speech:parakeet", "connection reset")
    assert app._first_run is False and app._config["model_size"] == "small"


def test_a_missing_polish_model_falls_back_to_rules(tmp_path):
    from cleanup import Cleanup
    cleaner = Cleanup({"cleanup_enabled": True, "cleanup_model_path": str(tmp_path / "models" / "gone")})
    cleaner.load(tmp_path / "models")
    assert cleaner.model is None and cleaner.load_error == "FileNotFoundError"


def test_settings_say_an_undownloaded_polish_model_needs_downloading(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    import app as app_module
    import dictation_engine
    monkeypatch.setattr(dictation_engine, "MODEL_DIR", tmp_path)
    config = {**dictation_engine.DEFAULT_CONFIG, "cleanup_enabled": True,
              "cleanup_model_path": str(tmp_path / "not-downloaded")}
    status = Mock()
    fake = SimpleNamespace(_settings_status=status, _config=dict(config),
                           _engine=SimpleNamespace(active=False, state=None))
    app_module.GUIApp._on_settings_apply(fake, config)
    assert "isn't downloaded" in status.call_args.args[0]


def test_polish_path_must_live_under_models_root(tmp_path):
    models = tmp_path / "models"
    allowed = models / "Qwen3-4B-int4-ov"
    allowed.mkdir(parents=True)
    (allowed / model_store.MANIFEST).write_text('{"files": {"model.xml": 1}}', encoding="utf-8")
    (allowed / "model.xml").write_text("x", encoding="utf-8")
    model_store.validate_polish_model_directory(allowed, models)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / model_store.MANIFEST).write_text('{"files": {"model.xml": 1}}', encoding="utf-8")
    (outside / "model.xml").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="models folder"):
        model_store.validate_polish_model_directory(outside, models)
