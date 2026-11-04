"""Replay local 16kHz mono WAV takes without recording or injecting input."""
import argparse
import importlib.metadata
import json
import platform
import statistics
import subprocess
import ctypes
from ctypes import wintypes
import sys
import time
import wave
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from cleanup import Cleanup, words
from speech_gate import has_speech
from dictation_engine import load_config, create_model, MODEL_DIR, MODEL_REGISTRY
from model_store import verify


def word_error_rate(reference, result):
    a, b = words(reference), words(result)
    row = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        nxt = [i]
        for j, right in enumerate(b, 1):
            nxt.append(min(row[j] + 1, nxt[-1] + 1, row[j - 1] + (left != right)))
        row = nxt
    return row[-1] / max(1, len(a))


def read_audio(path):
    with wave.open(str(path), "rb") as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
            raise ValueError("Replay requires 16kHz mono PCM16 WAV")
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768


def environment():
    import openvino as ov
    drivers = None
    if sys.platform == "win32":
        try:
            command = "Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName -match 'Intel.*(NPU|AI Boost|Arc)' } | Select-Object DeviceName,DriverVersion | ConvertTo-Json -Compress"
            result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout.strip():
                drivers = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
    return {"python": platform.python_version(), "platform": platform.platform(), "drivers": drivers,
            "packages": {name: importlib.metadata.version(name) for name in ("openvino", "openvino-genai", "numpy")},
            "available_devices": ov.Core().available_devices}


def memory_bytes():
    if sys.platform != "win32":
        return None
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ("peak", "working_set", "peak_paged", "paged", "peak_nonpaged", "nonpaged", "pagefile", "peak_pagefile")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32")
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    api = ctypes.WinDLL("psapi")
    api.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if api.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return counters.working_set
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("takes", type=Path, help="Folder containing audio.wav takes and optional reference.txt / expected.txt")
    parser.add_argument("--model", choices=MODEL_REGISTRY, default=None)
    parser.add_argument("--device", choices=["NPU", "GPU", "CPU"], default="NPU")
    parser.add_argument("--cleanup-path", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True, help="Local result JSON; contains transcripts")
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be positive")
    config = load_config()
    model_name = args.model or config["model_size"]
    config.update(model_size=model_name, device=args.device)
    info = MODEL_REGISTRY[model_name]
    path = MODEL_DIR / info["local_dir"]
    manifest = verify(path)
    start = time.monotonic()
    model = create_model(path, args.device, info["backend"])
    config["cleanup_enabled"] = bool(args.cleanup_path)
    if args.cleanup_path:
        config["cleanup_model_path"] = str(args.cleanup_path)
    cleaner = Cleanup(config)
    cleaner.load()
    if args.cleanup_path and cleaner.load_error:
        raise RuntimeError("Cleanup model failed to load")
    loaded = time.monotonic() - start
    resident_memory = memory_bytes()
    files = sorted(args.takes.rglob("audio.wav"))
    if not files:
        parser.error("No audio.wav files found")
    model.transcribe(read_audio(files[0]), 16000, config["language"])
    if cleaner.model:
        cleaner.model.generate("Please check the current build and tell me why it failed", "", lambda: False)
    results = []
    for file in files:
        audio = read_audio(file)
        ref = file.with_name("reference.txt")
        expected = file.with_name("expected.txt")
        metadata = file.with_name("take.json")
        process = json.loads(metadata.read_text(encoding="utf-8")).get("process", "") if metadata.exists() else ""
        for repeat in range(args.repeat):
            start = time.monotonic()
            raw = model.transcribe(audio, 16000, config["language"]) if has_speech(audio) else ""
            stt_seconds = time.monotonic() - start
            result = cleaner.run(raw, process)
            total = time.monotonic() - start
            entry = {"take": file.parent.name, "repeat": repeat, "raw": raw, "rules": result.rules,
                     "cleaned": result.text, "fallback": result.fallback, "process": process,
                     "audio_seconds": len(audio) / 16000, "transcribe_seconds": stt_seconds,
                     "cleanup_seconds": total - stt_seconds, "processing_seconds": total}
            if ref.exists():
                entry["raw_wer"] = word_error_rate(ref.read_text(encoding="utf-8"), raw)
            if expected.exists():
                entry["cleaned_wer"] = word_error_rate(expected.read_text(encoding="utf-8"), result.text)
            results.append(entry)
    timings = sorted(row["processing_seconds"] for row in results)
    report = {"environment": environment(), "model": model_name, "requested_device": args.device,
              "actual_device": model.device, "model_revision": manifest["revision"],
              "actual_decoder_device": getattr(model, "decoder_device", None),
              "cleanup_revision": verify(args.cleanup_path)["revision"] if args.cleanup_path else None,
              "load_seconds": loaded, "median_processing_seconds": statistics.median(timings),
              "resident_process_working_set_bytes": resident_memory,
              "p95_processing_seconds": timings[min(len(timings)-1, int(len(timings)*0.95))],
              "note": "Replay processing time excludes capture, modifier waiting, and paste. Review meaning and correction effort manually.",
              "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(results)} results. Median processing: {report['median_processing_seconds']:.2f}s")


if __name__ == "__main__":
    main()
