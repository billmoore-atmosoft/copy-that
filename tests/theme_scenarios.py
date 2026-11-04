"""Theme changes must not interrupt a take or lose unsaved settings."""
from unittest.mock import patch, MagicMock

import customtkinter as ctk
import pytest

from dictation_engine import DEFAULT_CONFIG, validate_config
from ui.theme import ThemeController
from ui.settings import SettingsWindow
from ui.history import HistoryWindow
from ui.overlay import OverlayWindow


@pytest.fixture(scope="module")
def root():
    # A single Tcl interpreter avoids stale native CTk callbacks across roots.
    root = ctk.CTk()
    root.withdraw()
    yield root
    root.destroy()
    ctk.set_appearance_mode("system")


def test_follow_system_and_manual_override(root):
    changes = []
    with patch.object(ctk.AppearanceModeTracker, "detect_appearance_mode", return_value=0) as detect:
        controller = ThemeController(root, "system", changes.append)
        assert changes == ["light"]
        detect.return_value = 1
        ctk.AppearanceModeTracker.update()
        controller._refresh()
        assert changes == ["light", "dark"]
        controller.set_mode("light")
        ctk.AppearanceModeTracker.update()
        controller._refresh()
        assert changes == ["light", "dark", "light"]
        controller.set_mode("system")
        assert changes[-1] == "dark"
        controller.close()
        assert controller._timer is None


def test_settings_survive_appearance_change(root):
    saved = []
    settings = SettingsWindow(root, {**DEFAULT_CONFIG, "device": "CPU"}, [], saved.append)
    settings.show()
    settings._dictionary_box.insert("end", "\ncopy that = CopyThat")
    for mode in ("dark", "light"):
        ctk.set_appearance_mode(mode)
        settings.refresh_theme()
        for page in settings._pages:
            settings._select_page(page)
            root.update_idletasks()
            assert settings._pages[page]._parent_frame.pack_info()["fill"] == "both"
        settings._theme_var.set(mode.title())
        settings._apply()
        assert saved[-1]["theme"] == mode
        assert saved[-1]["device"] == "CPU"
        assert saved[-1]["dictionary"]["copy that"] == "CopyThat"
        validate_config(saved[-1])
    settings._win.destroy()


def test_theme_keeps_active_pill_geometry_and_state(root):
    overlay = OverlayWindow(root)
    overlay.show_recording()
    overlay.set_field(True, (400, 200, 402, 220))
    overlay.set_recording_mode("locked")
    overlay.set_live_text("Let's move the review to Thursday.")
    root.update_idletasks()
    original = (overlay._win.geometry(), overlay._rec_start,
                overlay._bubble_text, overlay._rec_hint, overlay._state)
    for mode in ("light", "dark"):
        ctk.set_appearance_mode(mode)
        overlay.set_theme(mode)
        root.update_idletasks()
        assert (overlay._win.geometry(), overlay._rec_start,
                overlay._bubble_text, overlay._rec_hint, overlay._state) == original
    overlay.show_ready()
    overlay._win.destroy()


def test_history_both_themes_and_empty_state(root):
    for entries in ([], [{"text": "Sample transcript " * 80, "raw": "raw", "duration": 3}]):
        history = HistoryWindow(root, entries)
        history.show()
        for mode in ("light", "dark"):
            ctk.set_appearance_mode(mode)
            history.refresh_theme()
            root.update_idletasks()
            assert history.is_open
        history._win.destroy()


def test_theme_validation():
    assert DEFAULT_CONFIG["theme"] == "system"
    with pytest.raises(ValueError, match="theme"):
        validate_config({**DEFAULT_CONFIG, "theme": "automatic"})


def test_apply_theme_does_not_reload_engine():
    from app import GUIApp
    from dictation_engine import AppState
    app = GUIApp.__new__(GUIApp)
    app._config = dict(DEFAULT_CONFIG)
    app._engine = MagicMock(active=False, state=AppState.READY)
    app._overlay = MagicMock()
    app._tray = MagicMock()
    app._settings_win = None
    app._engine_started, app._offer_delete = True, []
    app._theme_controller = MagicMock()
    with patch("app.save_config") as save:
        app._on_settings_apply({**DEFAULT_CONFIG, "theme": "dark"})
        save.assert_called_once()
    app._engine.stop.assert_not_called()
    app._theme_controller.set_mode.assert_called_once_with("dark")


class FakeModels:
    """Model provider for card scenarios: parakeet and 4B installed, small downloading."""
    def __init__(self):
        self.calls = []
        self.states = {("speech", "parakeet"): ("installed", 1.0), ("cleanup", "4b"): ("removable", 1.0),
                       ("speech", "small"): ("downloading", 0.4)}

    def model_state(self, kind, key):
        return self.states.get((kind, key), ("available", 0.0))

    def download_model(self, kind, key):
        self.calls.append(("download", kind, key))

    def cancel_download(self, kind, key):
        self.calls.append(("cancel", kind, key))

    def remove_model(self, kind, key):
        self.calls.append(("remove", kind, key))


def test_model_cards_share_one_design_and_actions(root):
    models = FakeModels()
    saved = []
    settings = SettingsWindow(root, {**DEFAULT_CONFIG, "model_size": "parakeet", "device": "GPU"},
                              [], saved.append, models=models)
    settings.show()
    root.update_idletasks()
    cards = settings._cards
    assert cards[("speech", "parakeet")].state == "installed"
    assert cards[("speech", "small")].state == "downloading"
    assert cards[("speech", "base")].state == "available"
    assert cards[("cleanup", "4b")].state == "removable"
    assert cards[("cleanup", "8b")].state == "available"
    # A model that is not on disk cannot be selected.
    assert cards[("speech", "base")]._radio.cget("state") == "disabled"
    cards[("speech", "base")]._on_download()
    cards[("cleanup", "4b")]._on_remove()
    assert models.calls == [("download", "speech", "base"), ("remove", "cleanup", "4b")]
    settings._cleanup_var.set("4b")
    settings._on_cleanup_change()
    settings._apply()
    assert saved[-1]["cleanup_enabled"] is True and saved[-1]["cleanup_model_path"].endswith("Qwen3-4B-int4-ov")
    settings._cleanup_var.set("off")
    settings._apply()
    assert saved[-1]["cleanup_enabled"] is False
    settings._win.destroy()


def test_welcome_downloads_on_one_click(root):
    from ui.onboarding import WelcomeWindow
    models, started = FakeModels(), []
    models.states = {}
    welcome = WelcomeWindow(root, models, lambda: started.append(True))
    welcome.show()
    root.update_idletasks()
    assert [card.state for card in welcome._cards.values()] == ["queued", "queued"]
    welcome._primary_click()
    assert started == [True]
    models.states = {("speech", "parakeet"): ("installed", 1.0), ("cleanup", "4b"): ("downloading", 0.3)}
    welcome._poll()
    assert welcome._primary.cget("text") == "Close"
    welcome._win.destroy()
