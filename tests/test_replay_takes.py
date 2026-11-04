import json
from scripts.replay_takes import load_takes, report, word_diff


def save(folder, take_id, **take):
    (folder / take_id).mkdir(parents=True)
    (folder / take_id / "take.json").write_text(json.dumps({"id": take_id, **take}), encoding="utf-8")


def test_takes_load_oldest_first_and_filter(tmp_path):
    save(tmp_path, "b", raw="second", timestamp="2026-10-20T10:00", process="code.exe")
    save(tmp_path, "a", raw="first", timestamp="2026-10-19T10:00", process="Grok Bot.exe")
    save(tmp_path, "c", raw="", timestamp="2026-10-21T10:00", process="code.exe")
    assert [t["id"] for t in load_takes(tmp_path)] == ["a", "b"]
    assert [t["id"] for t in load_takes(tmp_path, process="grok")] == ["a"]
    assert [t["id"] for t in load_takes(tmp_path, since="2026-10-20")] == ["b"]
    assert [t["id"] for t in load_takes(tmp_path, limit=1)] == ["b"]


def test_word_diff_marks_changes_and_shortens_unchanged_runs():
    assert word_diff("PR for K0 twenty three", "PR for KO-23") == "PR for [-K0 twenty three-] {+KO-23+}"
    long = " ".join(f"w{i}" for i in range(20))
    assert word_diff(long + " old", long + " new") == "w0 w1 w2 w3 w4 w5 … w14 w15 w16 w17 w18 w19 [-old-] {+new+}"


def test_report_counts_polish_edits_and_lists_changed_takes():
    row = dict(timestamp="2026-10-22T18:00:00", process="code.exe", duration=3.0, raw="r",
               saved_rules="Same.", fallback=None, polished=True, polish_seconds=0.3)
    rows = [dict(row, rules="Same.", text="Same.", compare="Same."),
            dict(row, rules="Phase two.", text="Phase 2.", compare="Phase two.")]
    text = report(rows, "saved output", polish=True)
    assert "- Output differs from saved output: 1" in text
    assert "Polish ran: 2, changed the rules text: 1" in text
    assert "[-two.-] {+2.+}" in text
