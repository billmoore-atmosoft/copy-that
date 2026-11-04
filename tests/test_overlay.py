"""Combined recording bubble: where it opens and what it shows."""
import re
import tkinter as tk
from unittest.mock import patch

import pytest

from ui.overlay import OverlayWindow

AREA = (0, 0, 1920, 1040)


@pytest.fixture(scope="module")
def root():
    # One interpreter for the module: creating a Tk per test failed intermittently.
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def overlay(root):
    with patch("ui.overlay._work_area", return_value=AREA):
        o = OverlayWindow(root)
        placed = []
        real = o._place
        def place(w, h):
            real(w, h)
            x, y = map(int, re.match(r"\d+x\d+\+(-?\d+)\+(-?\d+)", o._win.geometry()).groups())
            placed.append((x, y, w, h))
        o._place = place
        o.placed = placed
        yield o
        o.show_ready()
        o._win.destroy()


def text_x(o):
    return o.LEFT_W + 1 + o.TEXT_PAD_X


def test_opens_below_the_caret_with_live_text_starting_under_it(overlay):
    overlay.show_recording()
    overlay.set_field(True, (800, 300, 802, 320))
    x, y, w, h = overlay.placed[-1]
    assert (x + text_x(overlay), y) == (800, 320 + overlay.CARET_GAP)
    assert overlay._win.state() == "normal"


def test_caret_after_the_bubble_opened_never_moves_it(overlay):
    overlay.show_recording()
    overlay._reveal()  # The wait for the caret ran out: pill spot.
    x, y, w, h = overlay.placed[-1]
    overlay.set_field(False, (800, 300, 802, 320))
    x2, y2, w2, h2 = overlay.placed[-1]
    assert (x2 + w2 // 2, y2) == (x + w // 2, y)  # Still centered at the pill spot.
    assert overlay._anchor is None
    assert overlay.NO_FIELD_HINT in [line[0] for line in overlay._text_lines()]


def test_opens_above_the_line_near_the_bottom_edge(overlay):
    overlay.show_recording()
    overlay.set_field(True, (800, 1010, 802, 1030))
    x, y, w, h = overlay.placed[-1]
    assert y + h == 1010 - overlay.CARET_GAP


def test_no_caret_or_top_setting_opens_at_the_pill_spot(overlay):
    overlay.set_bubble_position("top")
    overlay.show_recording()
    overlay.set_field(True, (800, 300, 802, 320))
    x, y, w, h = overlay.placed[-1]
    assert y == overlay._pos_y
    assert overlay._anchor is None


def test_live_text_widens_without_shrinking_and_wraps_at_the_limit(overlay):
    overlay.show_recording()
    overlay.set_field(True, None)
    overlay.set_live_text("a fairly long first sentence of live words")
    wide = overlay.placed[-1][2]
    overlay.set_live_text("short")
    assert overlay.placed[-1][2] == wide
    overlay.set_live_text("word " * 60)
    x, y, w, h = overlay.placed[-1]
    assert w == overlay.LEFT_W + 1 + overlay.TEXT_MAX_W
    assert h > overlay.BUBBLE_H


def test_pasted_take_closes_and_unpasted_result_stays(overlay):
    overlay.show_recording()
    overlay.set_field(True, (800, 300, 802, 320))
    overlay.show_processing()
    assert overlay._bubble_status == "processing"
    overlay.clear_balloon()
    overlay.show_result("Done.", linger=False)
    assert overlay._win.state() == "withdrawn"
    overlay.show_result("Put this in the notes.", linger=True)
    assert overlay._state == "result" and overlay._win.state() == "normal"
    assert overlay.RETAINED_HINT in [line[0] for line in overlay._text_lines()]


def test_hotkey_while_loading_shows_a_notice_then_returns_to_loading(overlay):
    overlay.show_loading()
    overlay.note_waiting(True)
    overlay.show_notice("Still loading, ready in a moment", "Loading", seconds=0.01)
    assert overlay._state == "notice" and overlay._win.state() == "normal"
    assert "Still loading, ready in a moment" in [line[0] for line in overlay._text_lines()]
    # A second press while the notice shows still returns to loading, not ready.
    overlay.show_notice("Still loading, ready in a moment", "Loading", seconds=0.01)
    overlay._root.after(50, overlay._root.quit)
    overlay._root.mainloop()
    assert overlay._state == "loading" and overlay._win.state() == "withdrawn"
