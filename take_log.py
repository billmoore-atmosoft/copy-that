"""Opt-in local replay files. Never called with logging disabled."""
import json
import wave
from pathlib import Path
import numpy as np

TAKE_FILES = {"audio.wav", "take.json"}
_SYNC_MARKERS = ("onedrive", "dropbox", "icloud", "google drive", "box sync", "sharepoint", "synology drive")


def private_directory(directory):
    directory = Path(directory).expanduser().resolve()
    repo = Path(__file__).resolve().parent
    # Do not allow personal dictations into tracked project paths or DriveFS.
    if directory == repo or repo in directory.parents:
        raise ValueError("Take logs must live outside the repository")
    if directory.drive.upper() == "G:" or any("google drive" in part.lower() for part in directory.parts):
        raise ValueError("Take logs must live outside Google Drive")
    if any(marker in part.lower() for part in directory.parts for marker in _SYNC_MARKERS):
        raise ValueError("Take logs must not live in a cloud-synced folder")
    return directory


def write_take(directory, take, entry):
    root = private_directory(directory)
    folder = root / take.id
    folder.mkdir(parents=True, exist_ok=False)
    audio = (np.clip(take.audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(folder / "audio.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(take.config["sample_rate"])
        wav.writeframes(audio.tobytes())
    (folder / "take.json").write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    prune_takes(root, take.config.get("take_log_keep", 200))


def prune_takes(directory, keep):
    """Delete the oldest takes past keep; 0 keeps them all. A folder holding
    anything more (a checked reference.txt) stays and does not count."""
    if not keep:
        return 0
    takes = [f for f in Path(directory).iterdir()
             if f.is_dir() and {p.name for p in f.iterdir()} == TAKE_FILES]
    takes.sort(key=lambda f: f.stat().st_mtime)
    removed = 0
    for folder in takes[:-keep]:
        try:
            for name in TAKE_FILES:
                (folder / name).unlink()
            folder.rmdir()
            removed += 1
        except OSError:
            continue  # Open elsewhere: the next take tries again.
    return removed
