from ui.tray import TrayManager


def test_left_click_opens_settings_not_recording():
    opened = []
    tray = TrayManager(on_toggle=lambda: opened.append("toggle"), on_quit=lambda: None,
                       on_settings=lambda: opened.append("settings"))
    defaults = [item for item in tray._build_menu().items if item.default]
    assert [item.text for item in defaults] == ["Settings"]
    defaults[0](None)
    assert opened == ["settings"]
