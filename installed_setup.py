"""Explicit offline model import and packaged-runtime verification."""
import json
import shutil
import time
import uuid
from pathlib import Path


def import_models(source):
    from dictation_engine import MODEL_DIR, CONFIG_FILE, load_config, save_config
    from model_store import verify
    source = Path(source).resolve()
    names = ("parakeet-tdt-openvino", "Qwen3-4B-int4-ov")
    for name in names:
        verify(source / name)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name in names:
        manifest = verify(source / name)
        target = MODEL_DIR / name
        if target.exists():
            # Updates never overwrite an existing installed model or user data.
            verify(target)
            continue
        staging = MODEL_DIR / (name + ".install-" + uuid.uuid4().hex)
        try:
            staging.mkdir()
            for filename in [*manifest["files"], "model-manifest.json"]:
                relative = Path(filename)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("Invalid model file path")
                dest = staging / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / name / relative, dest)
            verify(staging)
            staging.rename(target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    if not CONFIG_FILE.exists():
        config = load_config()
        config.update(model_size="parakeet", cleanup_enabled=True,
                      cleanup_model_path=str(MODEL_DIR / names[1]))
        save_config(config)


def self_test(report_path, audio_path, test_paste=False):
    import socket
    import sys
    from dictation_engine import CONFIG_DIR, MODEL_DIR, MODEL_REGISTRY, load_config, create_model
    from model_store import verify
    from scripts.benchmark import read_audio
    from cleanup import Cleanup
    def reject_network(*args, **kwargs):
        raise AssertionError("Runtime attempted network access")
    socket.create_connection = reject_network
    socket.socket.connect = reject_network
    report = {"frozen": bool(getattr(sys, "frozen", False)), "executable": sys.executable,
              "data_directory": str(CONFIG_DIR), "network_calls_blocked": True,
              "module_paths": sys.path}
    try:
        config = load_config()
        info = MODEL_REGISTRY[config["model_size"]]
        verify(MODEL_DIR / info["local_dir"])
        start = time.monotonic()
        speech = create_model(MODEL_DIR / info["local_dir"], config["device"], info["backend"])
        cleaner = Cleanup(config)
        cleaner.load()
        if cleaner.load_error:
            raise RuntimeError("Cleanup model unavailable")
        report.update(load_seconds=time.monotonic() - start, speech_device=speech.device,
                      decoder_device=getattr(speech, "decoder_device", None),
                      cleanup_prompt_lookup=getattr(cleaner.model, "prompt_lookup", False))
        if audio_path:
            audio = read_audio(Path(audio_path))
            speech.transcribe(audio)  # Warm native inference
            start = time.monotonic()
            raw = speech.transcribe(audio)
            result = cleaner.run(raw, "cursor.exe")
            report.update(raw=raw, cleaned=result.text, fallback=result.fallback,
                          processing_seconds=time.monotonic() - start)
        # Exercise packaged GUI resources and audio DLLs without opening the mic.
        import sounddevice
        report["input_devices"] = sum(d["max_input_channels"] > 0 for d in sounddevice.query_devices())
        from app import GUIApp
        del speech, cleaner
        gui = GUIApp(config)
        failures = []
        from dictation_engine import AppState
        def check():
            if gui._engine.state == AppState.ERROR:
                failures.append("Tray model load failed")
                gui._quit()
            elif gui._engine._model_ready.is_set():
                report["idle_overlay_hidden"] = gui._overlay._win.state() == "withdrawn"
                report["keyboard_hook_running"] = gui._engine._hook is not None
                if gui._engine._cleanup.load_error:
                    failures.append("Tray cleanup unavailable")
                gui._quit()
            else:
                gui._root.after(100, check)
        def timeout():
            failures.append("Tray startup timed out")
            gui._quit()
        gui._root.after(100, check)
        gui._root.after(120000, timeout)
        gui.run()
        if failures:
            raise RuntimeError("; ".join(failures))
        if test_paste:
            from scripts.smoke_paste import main as paste_smoke
            paste_smoke()
            report["disposable_paste_passed"] = True
        report["passed"] = report["idle_overlay_hidden"] and report["keyboard_hook_running"]
    except Exception as error:
        report.update(passed=False, error=f"{type(error).__name__}: {error}")
        raise
    finally:
        Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
