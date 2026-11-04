import pytest
from hotkeys import Gesture, SPACE, ESCAPE


@pytest.mark.parametrize("first,second", [(0xA2, 0x5B), (0x5B, 0xA2)])
@pytest.mark.parametrize("release_first", [True, False])
def test_hold_balances_forwarded_modifiers_and_finalizes_once(first, second, release_first):
    g = Gesture()
    assert g.event(first, True) == (False, [])
    assert g.event(second, True) == (True, ["mask", "start"])
    assert g.event(second, True)[1] == []  # repeat
    order = (first, second) if release_first else (second, first)
    actions = [g.event(vk, False) for vk in order]
    assert sum(a.count("stop") for _, a in actions) == 1
    assert not g.chord
    assert not g.down
    assert not g.swallowed
    # Only the modifier whose down was swallowed has its up swallowed.
    assert dict(zip(order, [s for s, _ in actions])) == {first: False, second: True}


def test_hands_free_stop_does_not_restart_on_same_chord():
    g = Gesture()
    g.event(0xA2, True)
    g.event(0x5B, True)
    assert g.event(SPACE, True) == (True, ["lock"])
    g.event(SPACE, False)
    assert g.event(0xA2, False)[1] == []
    g.event(0x5B, False)
    g.event(0x5B, True)
    assert g.event(0xA2, True)[1] == ["mask", "stop"]
    assert g.event(0xA2, True)[1] == []
    assert g.event(0xA2, False)[1] == []
    assert g.event(0x5B, False)[1] == []


def test_timeout_does_not_restart_until_modifiers_are_up():
    g = Gesture()
    g.event(0xA2, True)
    g.event(0x5B, True)
    g.finish()
    assert g.event(0x5B, True)[1] == []
    assert g.event(0xA2, False)[1] == []
    g.event(0x5B, False)
    g.event(0xA2, True)
    assert g.event(0x5B, True)[1] == ["mask", "start"]


def test_space_is_normal_outside_chord_and_escape_repeat_cancels_once():
    g = Gesture()
    assert g.event(SPACE, True) == (False, [])
    g.event(SPACE, False)
    assert g.event(ESCAPE, True, True) == (True, ["cancel"])
    assert g.event(ESCAPE, True, False) == (True, [])
    assert g.event(ESCAPE, False, False) == (True, [])
    assert g.event(ESCAPE, True, False) == (False, [])


def test_shortcuts_during_hold_are_swallowed_with_balanced_releases():
    g = Gesture()
    g.event(0x5B, True)
    g.event(0xA2, True)
    assert g.event(0x44, True)[0]
    g.event(0xA2, False)
    g.event(0x5B, False)
    assert g.event(0x44, False)[0]


def test_key_forwarded_before_chord_keeps_its_release_after_suppressed_repeat():
    g = Gesture()
    assert not g.event(0x44, True)[0]
    g.event(0xA2, True)
    g.event(0x5B, True)
    assert g.event(0x44, True)[0]
    assert not g.event(0x44, False)[0]


def test_shift_alt_z_pastes_last_and_swallows_only_z():
    g = Gesture()
    assert g.event(0xA0, True) == (False, [])
    assert g.event(0xA4, True) == (False, [])
    assert g.event(0x5A, True) == (True, ["mask", "paste_last"])
    assert g.event(0x5A, True) == (True, [])  # auto-repeat pastes once
    assert g.event(0x5A, False) == (True, [])
    assert g.event(0xA4, False) == (False, [])
    assert g.event(0xA0, False) == (False, [])


@pytest.mark.parametrize("modifiers", [(), (0xA0,), (0xA4,), (0xA2, 0xA4), (0xA0, 0xA4, 0x5B)])
def test_z_without_exact_shift_alt_is_ordinary_typing(modifiers):
    g = Gesture()
    for vk in modifiers:
        g.event(vk, True)
    swallow, actions = g.event(0x5A, True)
    assert "paste_last" not in actions


def test_late_chord_press_lets_its_release_through():
    # Windows passed the Win press on while the hook stalled; hiding its
    # release would leave Win held down for every app.
    g = Gesture()
    g.event(0xA2, True)
    assert g.event(0x5B, True, late=True) == (True, ["mask", "start"])
    assert 0x5B not in g.swallowed
    swallow, actions = g.event(0x5B, False)
    assert not swallow and actions == ["stop"]


def test_swallowed_release_windows_still_holds_is_reported_once():
    g = Gesture()
    g.event(0xA2, True)
    g.event(0x5B, True)
    g.event(0xA2, False)
    assert g.event(0x5B, False)[0]  # Its press was swallowed, so the release is too.
    assert g.hidden_releases == {0x5B}
    assert g.stuck(lambda vk: vk == 0x5B) == {0x5B}
    assert g.stuck(lambda vk: vk == 0x5B) == set()


def test_hidden_release_is_forgotten_when_windows_agrees_or_key_is_pressed_again():
    g = Gesture()
    g.event(0xA2, True)
    g.event(0x5B, True)
    g.event(0xA2, False)
    g.event(0x5B, False)
    assert g.stuck(lambda vk: False) == set()
    assert not g.hidden_releases
    g.hidden_releases = {0x5B}
    g.event(0x5B, True)  # Held again on purpose: not stuck.
    assert g.stuck(lambda vk: True) == set()
    assert g.hidden_releases == {0x5B}
