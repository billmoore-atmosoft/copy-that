"""Replay saved take transcripts through the current rules and Polish, offline.

Uses each take's saved raw transcript, so it measures rule and prompt changes
without re-running speech recognition. Reports contain personal dictation and
must be written outside the repository.
"""
import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cleanup import Cleanup
from context import (RecentTerms, destination_key, identifier, merge_terms, number_names, relevant,
                     strong_name)
from take_log import private_directory

INSTALLED_CONFIG = Path(os.environ.get("LOCALAPPDATA", "")) / "CopyThat" / "config.json"


def load_takes(folder, process=None, since=None, limit=None):
    takes = []
    for path in Path(folder).expanduser().glob("*/take.json"):
        take = json.loads(path.read_text(encoding="utf-8"))
        if not take.get("raw"):
            continue
        if process and process.lower() not in take.get("process", "").lower():
            continue
        if since and take.get("timestamp", "") < since:
            continue
        takes.append(take)
    # Oldest first, so later context features can look back at earlier takes.
    takes.sort(key=lambda take: take.get("timestamp", ""))
    return takes[-limit:] if limit else takes


def take_key(take):
    window = take.get("window") or {}
    return destination_key(window.get("hwnd"), take.get("field", ""), take.get("process", ""))


def take_time(take):
    from datetime import datetime
    try:
        return datetime.fromisoformat(take.get("timestamp", "")).timestamp()
    except ValueError:
        return 0.0


def take_terms(recent, take):
    """What TakeQueue._terms would have sent for this take: terms, and spell."""
    found = recent.terms(take_key(take), (take.get("window") or {}).get("title", ""), when=take_time(take))
    screen = relevant(take.get("screen_terms") or [], take["raw"])
    spell = ([term for term in screen if identifier(term) or strong_name(term, take["raw"])]
             + number_names(take.get("screen_terms") or [], take["raw"]))
    return merge_terms(found, screen), spell


def word_diff(old, new, keep=6):
    """Inline word diff: [-removed-] {+added+}, long unchanged runs shortened."""
    a, b = old.split(), new.split()
    out = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            same = a[i1:i2]
            if len(same) > keep * 2:
                same = same[:keep] + ["…"] + same[-keep:]
            out.extend(same)
            continue
        if i1 < i2:
            out.append("[-" + " ".join(a[i1:i2]) + "-]")
        if j1 < j2:
            out.append("{+" + " ".join(b[j1:j2]) + "+}")
    return " ".join(out)


def percentile(values, fraction):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * fraction))] if values else None


def timing_line(label, rows):
    seconds = [row["polish_seconds"] for row in rows if row["polished"]]
    if not seconds:
        return f"- {label}: no Polish runs"
    return (f"- {label}: {len(seconds)} runs, median {statistics.median(seconds):.2f}s, "
            f"p90 {percentile(seconds, 0.9):.2f}s")


def report(rows, compare_label, polish):
    changed = [row for row in rows if row["text"] != row["compare"]]
    polish_edits = sum(row["text"] != row["rules"] for row in rows if row["polished"])
    polished = sum(row["polished"] for row in rows)
    lines = ["# Replay report", "",
             f"- Takes: {len(rows)}",
             f"- Output differs from {compare_label}: {len(changed)}",
             f"- Rules differ from saved rules: {sum(row['rules'] != row['saved_rules'] for row in rows)}"]
    if polish:
        lines += [f"- Polish ran: {polished}, changed the rules text: {polish_edits}",
                  f"- Fallbacks: {dict(Counter(row['fallback'] for row in rows if row['fallback']))}",
                  timing_line("Short takes (<8s)", [row for row in rows if row["duration"] < 8]),
                  timing_line("Long takes (8s+)", [row for row in rows if row["duration"] >= 8])]
    lines += ["", f"## Changed vs {compare_label}", ""]
    for row in changed:
        lines += [f"### {row['timestamp'][:19]} {row['process']} ({row['duration']:.1f}s)"
                  + (f" fallback={row['fallback']}" if row["fallback"] else ""),
                  "", word_diff(row["compare"], row["text"]), ""]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--takes", type=Path, default=Path.home() / ".copythat-takes")
    parser.add_argument("--config", type=Path, default=INSTALLED_CONFIG,
                        help="Config with the dictionary and Polish settings (default: installed app)")
    parser.add_argument("--out", type=Path, required=True, help="Report folder outside the repository")
    parser.add_argument("--polish", action="store_true", help="Run the Polish model (default: rules only)")
    parser.add_argument("--polish-path", type=Path, help="Polish model folder (default: from config)")
    parser.add_argument("--every-take", action="store_true", help="Ignore the 'only when needed' gate")
    parser.add_argument("--baseline", type=Path, help="results.jsonl from an earlier run to compare against")
    parser.add_argument("--process", help="Only takes into this app, e.g. code.exe")
    parser.add_argument("--since", help="Only takes on or after this date, e.g. 2026-10-15")
    parser.add_argument("--limit", type=int, help="Only the newest N takes")
    parser.add_argument("--context", action="store_true",
                        help="Send Polish the terms the app would: window title, earlier takes, screen")
    args = parser.parse_args()
    out = private_directory(args.out)
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config.exists() else {}
    config["cleanup_enabled"] = args.polish
    if args.polish_path:
        config["cleanup_model_path"] = str(args.polish_path)
    if args.every_take:
        config["cleanup_gate"] = False
    cleaner = Cleanup(config)
    if args.polish:
        cleaner.load()
        if cleaner.load_error:
            parser.error(f"Polish model failed to load: {cleaner.load_error}")
        cleaner.model.generate("Please check the current build and tell me why it failed", "", lambda: False)
    # Time only the model call; rules-only takes and early returns record nothing.
    calls = []
    if args.polish:
        generate = cleaner.model.generate
        def timed(*call_args):
            start = time.monotonic()
            try:
                return generate(*call_args)
            finally:
                calls.append(time.monotonic() - start)
        cleaner.model.generate = timed
    baseline = {}
    if args.baseline:
        for line in args.baseline.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            baseline[row["id"]] = row["text"]
    takes = load_takes(args.takes, args.process, args.since, args.limit)
    if not takes:
        parser.error("No saved takes matched")
    rows = []
    recent = RecentTerms()
    for index, take in enumerate(takes, 1):
        before = len(calls)
        terms, spell = take_terms(recent, take) if args.context else ([], [])
        result = cleaner.run(take["raw"], take.get("process", ""), literal=take.get("literal_mode", False),
                             terms=terms, spell=spell)
        if args.context and result.text:
            recent.add(take_key(take), result.text, when=take_time(take))
        polished = len(calls) > before
        rows.append({"id": take["id"], "timestamp": take.get("timestamp", ""), "process": take.get("process", ""),
                     "duration": take.get("duration", 0), "raw": take["raw"],
                     "saved_rules": take.get("rules", ""), "saved_text": take.get("text", ""),
                     "compare": baseline.get(take["id"], take.get("text", "")),
                     "rules": result.rules, "text": result.text, "fallback": result.fallback,
                     "polished": polished, "polish_seconds": calls[-1] if polished else 0.0, "terms": terms})
        if args.polish and index % 25 == 0:
            print(f"{index}/{len(takes)}", file=sys.stderr)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "results.jsonl", "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    compare_label = "baseline" if args.baseline else "saved output"
    (out / "report.md").write_text(report(rows, compare_label, args.polish), encoding="utf-8")
    print(report(rows, compare_label, args.polish).split("\n## ")[0])
    print(f"Report: {out / 'report.md'}")


if __name__ == "__main__":
    main()
