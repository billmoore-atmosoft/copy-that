"""Copy a development checkout's settings and active models into the installed app's data folder.

Run with the checkout's Python while the installed app is closed:
    .\\.venv\\Scripts\\python.exe scripts\\migrate_dev_data.py
Existing installed settings are kept unless --replace-config is given. Models already
installed are left alone. Compiled caches are not copied; the first launch rebuilds them.
"""
import argparse
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_paths import APP_NAME
from model_store import verify


def copy_model(source, target):
    if target.exists():
        verify(target)
        return False
    manifest = verify(source)
    staging = target.with_name(target.name + ".install-" + uuid.uuid4().hex)
    try:
        for filename in [*manifest["files"], "model-manifest.json"]:
            relative = Path(filename)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Invalid model file path")
            dest = staging / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, dest)
        verify(staging)
        staging.rename(target)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return True


def migrate(source_dir, target_dir, replace_config=False):
    from dictation_engine import MODEL_REGISTRY
    config = json.loads((source_dir / "config.json").read_text(encoding="utf-8"))
    models = target_dir / "models"
    models.mkdir(parents=True, exist_ok=True)
    wanted = [MODEL_REGISTRY[config["model_size"]]["local_dir"]]
    cleanup = config.get("cleanup_model_path")
    if cleanup:
        wanted.append(Path(cleanup).name)
        config["cleanup_model_path"] = str(models / Path(cleanup).name)
    for name in wanted:
        copied = copy_model(source_dir / "models" / name, models / name)
        print(f"{name}: {'copied' if copied else 'already installed'}")
    target_config = target_dir / "config.json"
    if target_config.exists() and not replace_config:
        print(f"Kept existing settings: {target_config}")
    else:
        target_config.write_text(json.dumps(config, indent=2), encoding="utf-8")
        print(f"Settings and dictionary copied: {target_config}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", type=Path, default=ROOT / ".runtime")
    parser.add_argument("--target", type=Path, default=Path(os.environ["LOCALAPPDATA"]) / APP_NAME)
    parser.add_argument("--replace-config", action="store_true")
    args = parser.parse_args()
    migrate(args.source.resolve(), args.target.resolve(), args.replace_config)


if __name__ == "__main__":
    main()
