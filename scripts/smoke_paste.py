"""Exercise real Windows paste and overlay focus in disposable test text fields."""
import os
import sys
import threading
import tkinter as tk
import ctypes
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pyperclip
from windows_io import foreground, same_destination, paste_text, settle_clipboard
from ui.overlay import OverlayWindow


def main():
    root = tk.Tk()
    root.title("CopyThat paste verification")
    root.geometry("460x230")
    tk.Label(root, text="Temporary single-line and multiline paste checks").pack(pady=10)
    entry = tk.Entry(root, width=55)
    entry.pack(pady=10)
    text = tk.Text(root, width=55, height=5)
    text.pack()
    overlay = OverlayWindow(root)
    saved_clipboard = pyperclip.paste()
    failures = []
    results = []
    finished = threading.Event()
    errors = []
    expected = "Dictation works here: café, 42, do not deploy."

    def fail(error):
        failures.append(str(error))
        root.destroy()

    def paste_in_worker(destination, value):
        results.clear()
        errors.clear()
        finished.clear()
        def run():
            try:
                results.append(paste_text(value, guard=lambda: same_destination(destination)))
                settle_clipboard()
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()
        threading.Thread(target=run, daemon=True).start()

    def focus_window(window, widget):
        window.update_idletasks()
        user = ctypes.WinDLL("user32")
        user.GetParent.argtypes = [wintypes.HWND]
        user.GetParent.restype = wintypes.HWND
        user.SetForegroundWindow.argtypes = [wintypes.HWND]
        user.SetForegroundWindow(user.GetParent(window.winfo_id()))
        window.focus_force()
        widget.focus_set()

    def wait_for_paste(next_check):
        if not finished.is_set():
            root.after(20, lambda: wait_for_paste(next_check))
        elif errors:
            fail(errors[0])
        else:
            try:
                next_check()
            except Exception as error:
                fail(error)

    def check_entry():
        assert results == [True], "Single-line paste was rejected"
        assert entry.get() == expected, "Single-line text differed"
        assert pyperclip.paste() == saved_clipboard, "Clipboard text was not restored"
        text.focus_set()
        root.after(100, paste_multiline)

    def paste_multiline():
        paste_in_worker(foreground(), expected + "\nSecond paragraph.")
        wait_for_paste(check_multiline)

    def check_multiline():
        assert results == [True], "Multiline paste was rejected"
        assert text.get("1.0", "end-1c") == expected + "\nSecond paragraph.", "Multiline text differed"
        destination = foreground()
        other = tk.Toplevel(root)
        other.title("CopyThat changed destination")
        other.geometry("320x100")
        target = tk.Entry(other)
        target.pack(pady=20)
        focus_window(other, target)
        def check_changed():
            try:
                assert not same_destination(destination), "Test could not switch foreground windows"
                paste_in_worker(destination, "This must not paste")
                def check_retained():
                    assert results == [False], "Changed destination accepted a paste"
                    assert target.get() == "", "Changed destination received text"
                    assert pyperclip.paste() == saved_clipboard, "Rejected paste changed clipboard"
                    print("Real single-line/multiline Unicode paste, clipboard restore, overlay focus, and changed-window rejection passed", flush=True)
                    root.destroy()
                wait_for_paste(check_retained)
            except Exception as error:
                fail(error)
        root.after(150, check_changed)

    def start():
        try:
            destination = foreground()
            assert destination.pid == os.getpid(), "Test window could not get foreground focus"
            overlay.show_recording()
            root.update_idletasks()
            assert same_destination(destination), "Recording overlay stole focus"
            paste_in_worker(destination, expected)
            wait_for_paste(check_entry)
        except Exception as error:
            fail(error)

    focus_window(root, entry)
    root.after(400, start)
    root.after(15000, lambda: fail("Paste verification timed out"))
    root.mainloop()
    if failures:
        raise AssertionError("; ".join(failures))


if __name__ == "__main__":
    main()
