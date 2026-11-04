import json
import sys
import pytest
from app_paths import data_directory
from installed_setup import import_models


def test_frozen_data_is_local_and_environment_override_is_respected(monkeypatch, tmp_path):
    monkeypatch.delenv("COPYTHAT_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert data_directory() == tmp_path / "CopyThat"
    monkeypatch.setenv("COPYTHAT_DATA_DIR", str(tmp_path / "verification"))
    assert data_directory() == tmp_path / "verification"


def model_pack(path):
    for name in ("parakeet-tdt-openvino", "Qwen3-4B-int4-ov"):
        folder = path / name
        folder.mkdir(parents=True)
        (folder / "model.xml").write_text("model")
        (folder / "model-manifest.json").write_text(json.dumps({
            "repo": name, "revision": "fixed", "files": {"model.xml": 5}}))


def test_model_import_preserves_existing_models_and_settings(monkeypatch, tmp_path):
    import dictation_engine as engine
    source, installed = tmp_path / "pack", tmp_path / "data"
    model_pack(source)
    monkeypatch.setattr(engine, "MODEL_DIR", installed / "models")
    monkeypatch.setattr(engine, "CONFIG_DIR", installed)
    monkeypatch.setattr(engine, "CONFIG_FILE", installed / "config.json")
    import_models(source)
    config = engine.load_config()
    assert config["model_size"] == "parakeet"
    config["dictionary"] = {"name": "Alex"}
    engine.save_config(config)
    (source / "parakeet-tdt-openvino/model.xml").write_text("other")
    import_models(source)
    assert engine.load_config()["dictionary"] == {"name": "Alex"}
    assert (installed / "models/parakeet-tdt-openvino/model.xml").read_text() == "model"


def test_incomplete_pack_does_not_create_installed_models(monkeypatch, tmp_path):
    import dictation_engine as engine
    source = tmp_path / "pack"
    model_pack(source)
    (source / "Qwen3-4B-int4-ov/model.xml").unlink()
    monkeypatch.setattr(engine, "MODEL_DIR", tmp_path / "models")
    with pytest.raises(FileNotFoundError):
        import_models(source)
    assert not engine.MODEL_DIR.exists()
