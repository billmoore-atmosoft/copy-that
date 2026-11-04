"""Where dictated text will land: the focused field and its caret.

Uses UI Automation, which covers Chromium and Electron apps (VS Code, Chrome,
Slack, Teams) where the classic Win32 caret is never set, plus the Win32
caret for older apps. Coordinates are physical screen pixels; the app is
per-monitor DPI aware. Probes run on one thread that owns the COM objects.
"""
import ctypes
import ctypes.wintypes as wintypes
import queue
import threading
import time
from dataclasses import dataclass

EDIT, DOCUMENT = 50004, 50030


@dataclass(frozen=True)
class FieldInfo:
    editable: bool | None            # None: unknown, so never warn
    caret: tuple | None = None       # (left, top, right, bottom)
    control: int = 0
    ms: float = 0.0
    field: str = ""                  # Which box in the window, for the take log


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT)]


def win32_caret(hwnd):
    """Caret of a classic Win32 control, or None (never set by Chromium)."""
    user32 = ctypes.windll.user32
    thread = user32.GetWindowThreadProcessId(hwnd, None)
    info = _GUITHREADINFO(cbSize=ctypes.sizeof(_GUITHREADINFO))
    if not thread or not user32.GetGUIThreadInfo(thread, ctypes.byref(info)) or not info.hwndCaret:
        return None
    rect = info.rcCaret
    points = (wintypes.POINT * 2)((rect.left, rect.top), (rect.right, rect.bottom))
    user32.MapWindowPoints(info.hwndCaret, None, points, 2)
    return points[0].x, points[0].y, max(points[1].x, points[0].x + 1), points[1].y


def classify(control, has_value, read_only, has_text):
    """Editable verdict. False only when confident, since False shows a warning."""
    if has_value and read_only:
        return False
    if control == EDIT or (has_value and not read_only):
        return True
    if control == DOCUMENT or has_text:
        return None  # Page bodies and terminals look alike; do not guess.
    return False


def caret_from_rects(rects, bounds):
    """First caret box inside the field; UIA rects are left, top, width, height."""
    left, top, right, bottom = bounds
    for i in range(0, len(rects) - 3, 4):
        x, y, w, h = rects[i:i + 4]
        if h > 0 and left - 2 <= x <= right + 2 and top - 2 <= y <= bottom + 2:
            return int(x), int(y), int(x + max(w, 1)), int(y + h)
    return None


class FocusProbe:
    def __init__(self, log=lambda message: None):
        self._log = log
        self._requests = queue.SimpleQueue()
        self._thread = None
        self._uia = None

    def probe(self, hwnd, callback, retry_after=0.3):
        """Report FieldInfo for the focused element without blocking the caller."""
        self._submit((hwnd, callback, retry_after))

    def read_screen(self, hwnd, callback, limit=3000):
        """Report (control type, name) pairs for the window and the selected
        text, after any field probe already queued."""
        def run():
            start = time.monotonic()
            try:
                items, selection = self._screen(hwnd, limit)
            except Exception as error:
                self._log(f"Screen read failed ({type(error).__name__})")
                items, selection = [], ""
            callback(items, selection, (time.monotonic() - start) * 1000)
        self._submit(run)

    def warm(self):
        """Load UI Automation now: the first load holds the GIL for seconds, which
        delayed the keyboard hook enough to leave the Win key stuck down."""
        self._submit(None)

    def _submit(self, request):
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="focus-probe", daemon=True)
            self._thread.start()
        self._requests.put(request)

    def _run(self):
        import sys
        # UI Automation prefers a multithreaded apartment; importing comtypes
        # initializes the importing thread with these flags.
        sys.coinit_flags = 0
        try:
            import comtypes
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except OSError:
            pass  # Already initialized on this thread.
        except Exception as error:
            self._log(f"Focus probe unavailable ({type(error).__name__})")
        while True:
            request = self._requests.get()
            if request is None:
                try:
                    self._automation()
                except Exception:
                    pass  # The first real probe reports what is wrong.
                continue
            if callable(request):
                try:
                    request()
                except Exception:
                    self._log("Screen read callback failed")
                continue
            hwnd, callback, retry_after = request
            info = self._probe(hwnd)
            if info.editable is not True and retry_after:
                # The first query switches Chromium's accessibility tree on; until
                # then it reports a bare pane.
                time.sleep(retry_after)
                info = self._probe(hwnd)
            try:
                callback(info)
            except Exception:
                self._log("Focus probe callback failed")

    def _automation(self):
        if self._uia is None:
            import comtypes.client
            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen import UIAutomationClient as uia
            self._mod = uia
            self._uia = comtypes.client.CreateObject(uia.CUIAutomation8, interface=uia.IUIAutomation)
        return self._uia, self._mod

    def _screen(self, hwnd, limit):
        auto, uia = self._automation()
        cache = auto.CreateCacheRequest()
        cache.AddProperty(uia.UIA_NamePropertyId)
        cache.AddProperty(uia.UIA_ControlTypePropertyId)
        # One cross-process call for the whole tree; about 80 ms for VS Code.
        found = auto.ElementFromHandle(hwnd).FindAllBuildCache(
            uia.TreeScope_Descendants, auto.CreateTrueCondition(), cache)
        items = []
        for i in range(min(found.Length if found else 0, limit)):
            element = found.GetElement(i)
            items.append((element.CachedControlType, element.CachedName or ""))
        selection = ""
        try:
            text = auto.GetFocusedElement().GetCurrentPattern(uia.UIA_TextPatternId)
            if text:
                ranges = text.QueryInterface(uia.IUIAutomationTextPattern).GetSelection()
                if ranges and ranges.Length:
                    selection = ranges.GetElement(0).GetText(2000) or ""
        except Exception:
            pass  # Many fields have no text pattern; the walk still counts.
        return items, selection

    def _probe(self, hwnd):
        start = time.monotonic()
        caret = win32_caret(hwnd) if hwnd else None
        try:
            auto, uia = self._automation()
            element = auto.GetFocusedElement()
            control = element.CurrentControlType
            r = element.CurrentBoundingRectangle
            bounds = (r.left, r.top, r.right, r.bottom)
            value = element.GetCurrentPattern(uia.UIA_ValuePatternId)
            read_only = bool(value and value.QueryInterface(uia.IUIAutomationValuePattern).CurrentIsReadOnly)
            text = element.GetCurrentPattern(uia.UIA_TextPatternId)
            editable = classify(control, bool(value), read_only, bool(text))
            # Labels, not contents: Name is the field's caption (e.g. a chat box's
            # aria-label); the typed text lives in the Value and Text patterns.
            field = "|".join((str(control), element.CurrentAutomationId or "",
                              element.CurrentClassName or "", (element.CurrentName or "")[:80]))
            if text and caret is None and editable is not False:
                selection = text.QueryInterface(uia.IUIAutomationTextPattern).GetSelection()
                if selection and selection.Length:
                    span = selection.GetElement(0)
                    rects = list(span.GetBoundingRectangles() or ())
                    if not rects:
                        # A collapsed caret can have no box; use the next character's.
                        span.ExpandToEnclosingUnit(uia.TextUnit_Character)
                        rects = list(span.GetBoundingRectangles() or ())
                    caret = caret_from_rects(rects, bounds)
        except Exception as error:
            self._log(f"Focus probe failed ({type(error).__name__})")
            return FieldInfo(True if caret else None, caret, 0, (time.monotonic() - start) * 1000)
        if caret and editable is None:
            editable = True
        return FieldInfo(editable, caret, control, (time.monotonic() - start) * 1000, field)
