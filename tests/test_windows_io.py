import threading
from unittest.mock import Mock, patch
from windows_io import paste_text, settle_clipboard


def test_restore_does_not_overwrite_new_user_copy():
    clip = Mock()
    clip.paste.side_effect = ["original", "new user copy"]
    with patch.dict("sys.modules", {"pyperclip": clip}), patch("windows_io.modifiers_down", return_value=False), \
         patch("windows_io.clipboard_sequence", side_effect=[1, 2]), patch("windows_io.send_keys"), patch("windows_io.time.sleep"):
        assert paste_text("dictated")
        assert settle_clipboard()
    clip.copy.assert_called_once_with("dictated")


def test_restore_own_clipboard_and_guard_checked_after_copy():
    clip = Mock()
    clip.paste.side_effect = ["original", "dictated"]
    guard = Mock(side_effect=[True, False])
    with patch.dict("sys.modules", {"pyperclip": clip}), patch("windows_io.modifiers_down", return_value=False), \
         patch("windows_io.clipboard_sequence", return_value=1), patch("windows_io.send_keys") as keys, patch("windows_io.time.sleep"):
        assert not paste_text("dictated", guard=guard)
        assert settle_clipboard()
        keys.assert_not_called()
    assert [c.args[0] for c in clip.copy.call_args_list] == ["dictated", "original"]


def test_paste_returns_before_restore_and_next_paste_waits_for_it():
    clip = Mock()
    clip.paste.side_effect = ["original", "first", "original", "second"]
    restoring, release = threading.Event(), threading.Event()
    def sleep(seconds):
        if seconds == 0.35 and not release.is_set():
            restoring.set()
            release.wait(2)
    with patch.dict("sys.modules", {"pyperclip": clip}), patch("windows_io.modifiers_down", return_value=False), \
         patch("windows_io.clipboard_sequence", return_value=1), patch("windows_io.send_keys"), \
         patch("windows_io.time.sleep", side_effect=sleep):
        assert paste_text("first")
        assert restoring.wait(2)
        assert [c.args[0] for c in clip.copy.call_args_list] == ["first"]
        second = threading.Thread(target=paste_text, args=("second",))
        second.start()
        second.join(0.1)
        assert second.is_alive()  # The next paste must save the restored original.
        release.set()
        second.join(2)
        assert settle_clipboard()
    assert [c.args[0] for c in clip.copy.call_args_list] == ["first", "original", "second", "original"]


def test_own_windows_are_never_a_paste_destination():
    import os
    from windows_io import Destination, same_destination
    own = Destination(1234, os.getpid(), "pythonw.exe")
    with patch("windows_io.foreground", return_value=own):
        assert not same_destination(own)
