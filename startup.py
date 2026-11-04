"""Per-user, opt-in startup for the installed executable."""
import sys
import winreg
from app_paths import APP_NAME

KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
NAME = APP_NAME


def enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            value, _ = winreg.QueryValueEx(key, NAME)
        return value == f'"{sys.executable}"'
    except FileNotFoundError:
        return False


def set_enabled(value):
    if not getattr(sys, "frozen", False):
        raise ValueError("Start with Windows requires the installed executable")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        if value:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
