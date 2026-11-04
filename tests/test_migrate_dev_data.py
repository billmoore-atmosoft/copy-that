import json
from scripts.migrate_dev_data import migrate


def model(path):
    path.mkdir(parents=True)
    (path / "model.xml").write_text("model")
    (path / "model-manifest.json").write_text(json.dumps({
        "repo": path.name, "revision": "fixed", "files": {"model.xml": 5}}))


def dev_checkout(tmp_path):
    source = tmp_path / "dev"
    model(source / "models/parakeet-tdt-openvino")
    model(source / "models/Qwen3-4B-int4-ov")
    model(source / "models/Qwen3-8B-int4-ov")
    (source / "config.json").write_text(json.dumps({
        "model_size": "parakeet", "dictionary": {"e meet": "EMEET"},
        "cleanup_model_path": str(source / "models/Qwen3-4B-int4-ov")}))
    return source


def test_copies_settings_and_only_active_models(tmp_path):
    source, target = dev_checkout(tmp_path), tmp_path / "installed"
    migrate(source, target)
    config = json.loads((target / "config.json").read_text())
    assert config["dictionary"] == {"e meet": "EMEET"}
    assert config["cleanup_model_path"] == str(target / "models/Qwen3-4B-int4-ov")
    assert (target / "models/parakeet-tdt-openvino/model.xml").read_text() == "model"
    assert (target / "models/Qwen3-4B-int4-ov/model-manifest.json").exists()
    assert not (target / "models/Qwen3-8B-int4-ov").exists()


def test_keeps_existing_installed_settings(tmp_path):
    source, target = dev_checkout(tmp_path), tmp_path / "installed"
    target.mkdir()
    (target / "config.json").write_text(json.dumps({"dictionary": {"mine": "Mine"}}))
    migrate(source, target)
    assert json.loads((target / "config.json").read_text())["dictionary"] == {"mine": "Mine"}
    migrate(source, target, replace_config=True)
    assert json.loads((target / "config.json").read_text())["dictionary"] == {"e meet": "EMEET"}
