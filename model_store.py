"""Pinned Hugging Face model downloads. Only an explicit user action goes online."""
import json
import shutil
import threading
import time
from pathlib import Path

MANIFEST = "model-manifest.json"


class Cancelled(Exception):
    pass


def installed(directory) -> bool:
    """A model is installed once its manifest exists; it is written last."""
    return (Path(directory) / MANIFEST).is_file()


def verify(directory):
    directory = Path(directory)
    manifest_path = directory / MANIFEST
    if not manifest_path.exists():
        raise FileNotFoundError("Model snapshot is incomplete; run model setup")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, size in manifest["files"].items():
        path = directory / name
        if not path.is_file() or path.stat().st_size != size:
            raise FileNotFoundError("Model snapshot is incomplete; run model setup")
    return manifest


def polish_path_allowed(path, models_root):
    """Polish models must live under the app models folder."""
    directory = Path(path).expanduser().resolve()
    if Path(models_root).resolve() not in directory.parents:
        raise ValueError("Polish model path must be inside the CopyThat models folder")
    return directory


def validate_polish_model_directory(path, models_root):
    """A complete downloaded snapshot in the app models folder."""
    verify(polish_path_allowed(path, models_root))


class _NullFile:
    def write(self, _):
        pass

    def flush(self):
        pass


def download(repo, directory, revision=None, progress=None, cancel=None):
    """Download one snapshot. Cancel deletes the partial folder; a failure keeps it to resume."""
    from huggingface_hub import HfApi, snapshot_download
    from tqdm.auto import tqdm

    directory = Path(directory)
    if revision is None:
        revision = HfApi().model_info(repo).sha
    directory.mkdir(parents=True, exist_ok=True)
    (directory / MANIFEST).unlink(missing_ok=True)
    bars = []

    class _Bar(tqdm):
        # Hugging Face reports an aggregate byte bar; report its share and stop on cancel.
        def __init__(self, *args, **kwargs):
            kwargs["file"] = _NullFile()
            super().__init__(*args, **kwargs)
            if self.unit == "B":
                bars.append(self)

        def update(self, n=1):
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            result = super().update(n)
            totals = [bar.total for bar in bars if bar.total]
            if progress and totals:
                progress(min(1.0, max(bar.n for bar in bars) / max(totals)))
            return result

    try:
        snapshot_download(repo, revision=revision, local_dir=str(directory), tqdm_class=_Bar,
                          ignore_patterns=["*.md", ".gitattributes", "*.png", "*.jpg"])
        if cancel is not None and cancel.is_set():
            raise Cancelled()
    except BaseException:
        if cancel is not None and cancel.is_set():
            remove(directory)
            raise Cancelled() from None
        raise
    if not list(directory.glob("*.xml")) and not list(directory.glob("*.onnx")):
        raise RuntimeError("Downloaded snapshot has no model graphs")
    manifest = {"repo": repo, "revision": revision,
                "files": {str(p.relative_to(directory)): p.stat().st_size
                          for p in directory.rglob("*") if p.is_file() and ".cache" not in p.parts
                          and p.name != MANIFEST}}
    # Written only after the entire snapshot succeeds.
    (directory / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def remove(directory):
    """Delete a model folder; download workers may still be releasing file handles."""
    directory = Path(directory)
    for _ in range(20):
        shutil.rmtree(directory, ignore_errors=True)
        if not directory.exists():
            return
        time.sleep(0.25)
    raise OSError(f"Could not delete {directory}")


class Downloads:
    """Background downloads keyed by model id. The UI polls fraction(); on_done reports completion."""

    def __init__(self, on_done=None, download_fn=download):
        self._jobs = {}
        self._lock = threading.Lock()
        self._on_done = on_done
        self._download = download_fn

    def start(self, key, repo, revision, directory):
        with self._lock:
            if key in self._jobs:
                return
            job = {"fraction": 0.0, "cancel": threading.Event()}
            self._jobs[key] = job
        threading.Thread(target=self._run, args=(key, job, repo, revision, directory),
                         name=f"download-{key}", daemon=True).start()

    def _run(self, key, job, repo, revision, directory):
        error = None
        try:
            self._download(repo, directory, revision=revision, cancel=job["cancel"],
                           progress=lambda value: job.__setitem__("fraction", value))
        except Cancelled:
            error = "cancelled"
        except Exception as exc:
            error = str(exc) or type(exc).__name__
        with self._lock:
            self._jobs.pop(key, None)
        if self._on_done:
            self._on_done(key, error)

    def fraction(self, key):
        """Download share 0-1, or None when the key is not downloading."""
        job = self._jobs.get(key)
        return None if job is None else job["fraction"]

    def cancel(self, key):
        job = self._jobs.get(key)
        if job:
            job["cancel"].set()

    def cancel_all(self):
        for key in list(self._jobs):
            self.cancel(key)

    def active(self):
        return bool(self._jobs)
