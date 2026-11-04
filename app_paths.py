"""Keep installed app data outside executable files and synchronized folders."""
import os
import sys
from pathlib import Path

# Product name for the installed app: data folder, exe, registry keys, mutex.
APP_NAME = "CopyThat"


def data_directory():
    if os.environ.get("COPYTHAT_DATA_DIR"):
        return Path(os.environ["COPYTHAT_DATA_DIR"]).resolve()
    if getattr(sys, "frozen", False):
        return Path(os.environ["LOCALAPPDATA"]) / APP_NAME
    return Path.home() / ".copythat"
