"""Tests for config validation."""
import json

import pytest

import dictation_engine
from dictation_engine import log, validate_config, validate_settings, DEFAULT_CONFIG


def test_the_log_keeps_one_older_file_at_its_size_limit(tmp_path, monkeypatch):
    path = tmp_path / "dictation.log"
    monkeypatch.setattr(dictation_engine, "LOG_FILE", path)
    monkeypatch.setattr(dictation_engine, "LOG_MAX_BYTES", 100)
    for i in range(20):
        log(f"line {i} of the log, long enough to fill it quickly")
    assert sorted(f.name for f in tmp_path.iterdir()) == ["dictation.log", "dictation.log.1"]
    assert path.stat().st_size < 200 and (tmp_path / "dictation.log.1").stat().st_size < 200
    assert "line 19" in path.read_text(encoding="utf-8")


class TestConfigValidation:
    def test_valid_config_passes(self):
        config = DEFAULT_CONFIG.copy()
        validate_config(config)  # should not raise

    def test_invalid_device_raises(self):
        config = {**DEFAULT_CONFIG, "device": "TPU"}
        with pytest.raises(ValueError, match="device"):
            validate_config(config)

    def test_invalid_model_size_raises(self):
        config = {**DEFAULT_CONFIG, "model_size": "huge"}
        with pytest.raises(ValueError, match="model_size"):
            validate_config(config)

    def test_invalid_sample_rate_raises(self):
        config = {**DEFAULT_CONFIG, "sample_rate": "banana"}
        with pytest.raises(ValueError, match="sample_rate"):
            validate_config(config)

    def test_invalid_max_record_seconds_raises(self):
        config = {**DEFAULT_CONFIG, "max_record_seconds": -5}
        with pytest.raises(ValueError, match="max_record_seconds"):
            validate_config(config)

    def test_oversized_dictionary_is_refused_in_settings(self):
        config = {**DEFAULT_CONFIG, "dictionary": {f"k{i}": "v" for i in range(501)}}
        with pytest.raises(ValueError, match="500"):
            validate_settings(config)

    def test_settings_refuse_a_polish_folder_outside_the_models_folder(self, tmp_path):
        config = {**DEFAULT_CONFIG, "cleanup_enabled": True, "cleanup_model_path": str(tmp_path / "elsewhere")}
        with pytest.raises(ValueError, match="models folder"):
            validate_settings(config)

    def test_settings_refuse_a_synced_take_folder(self):
        config = {**DEFAULT_CONFIG, "take_log_enabled": True, "take_log_dir": "C:/Users/someone/OneDrive/takes"}
        with pytest.raises(ValueError, match="cloud-synced"):
            validate_settings(config)


@pytest.mark.parametrize("saved", [
    {"cleanup_enabled": True},  # Polish on, model folder missing
    {"cleanup_enabled": True, "cleanup_model_path": "D:/elsewhere/model"},
    {"take_log_enabled": True, "take_log_dir": "C:/Users/someone/OneDrive/takes"},
    {"dictionary": {f"k{i}": "v" for i in range(501)}},
])
def test_a_bad_saved_config_still_starts(tmp_path, monkeypatch, saved):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(saved), encoding="utf-8")
    monkeypatch.setattr(dictation_engine, "CONFIG_FILE", path)
    config = dictation_engine.load_config()
    validate_config(config)  # main() checks again before opening the app
    assert all(config[key] == value for key, value in saved.items())
