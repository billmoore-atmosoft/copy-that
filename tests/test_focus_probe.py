from focus_probe import DOCUMENT, EDIT, classify, caret_from_rects


def test_only_confident_verdicts_say_not_editable():
    assert classify(EDIT, True, False, True) is True
    assert classify(EDIT, False, False, False) is True
    assert classify(EDIT, True, True, True) is False          # read-only field
    assert classify(DOCUMENT, False, False, True) is None     # page body or terminal: unknown
    assert classify(50033, False, False, False) is False      # a bare pane
    assert classify(50033, True, False, False) is True        # custom control with a writable value


def test_caret_comes_from_rects_inside_the_field():
    field = (538, 761, 1353, 809)
    # Real VS Code chat input: collapsed caret at 734,774, 22px tall.
    assert caret_from_rects([734.0, 774.0, 1.0, 22.0], field) == (734, 774, 735, 796)
    assert caret_from_rects([0.0, 0.0, 0.0, 0.0, 734.0, 774.0, 1.0, 22.0], field) == (734, 774, 735, 796)
    assert caret_from_rects([20.0, 20.0, 1.0, 22.0], field) is None   # stale box elsewhere
    assert caret_from_rects([], field) is None
