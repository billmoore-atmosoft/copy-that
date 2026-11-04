from cleanup import drift_reason
from context import RecentTerms, merge_terms, near_miss, number_names, respell, relevant, screen_terms, terms_in, title_terms


def test_terms_are_identifiers_acronyms_and_interior_names():
    text = "Okay, so I asked Jordan about OPS-49 and the PR. Merge cleanup.py into take_log via OpenVINO."
    assert terms_in(text) == ["Jordan", "OPS-49", "PR", "cleanup.py", "take_log", "OpenVINO"]


def test_window_titles_lose_the_app_name():
    assert title_terms("cleanup.py - copy-that - Visual Studio Code") == ["cleanup.py", "copy-that"]
    assert title_terms("Notepad") == ["Notepad"]


def test_recent_terms_stay_with_their_box_and_expire():
    recent = RecentTerms(minutes=30)
    recent.add((1, "chat"), "Ask Jordan about OPS-23", when=0)
    recent.add((2, "editor"), "Rename take_log", when=10)
    assert recent.terms((1, "chat"), when=60) == ["Jordan", "OPS-23"]
    assert recent.terms((1, "chat"), when=31 * 60) == []
    assert recent.terms((2, "editor"), "app.py - copy-that - Visual Studio Code", when=20) == [
        "app.py", "copy-that", "take_log"]


def test_a_misheard_name_may_become_a_context_term():
    source = "Link OBS 49 to the PR for the release today."
    output = "Link OPS-49 to the PR for the release today."
    assert drift_reason(source, output) == "names"
    assert drift_reason(source, output, terms=["OPS-23"]) is None
    # Losing a name with nothing from the terms in its place is still drift.
    assert drift_reason("Ask Jordan about the OBS build today.", "Ask about the build today.", terms=["OPS-23"]) is not None


def test_screen_terms_drop_possessives_and_web_addresses():
    assert screen_terms([(50020, "Notes from Alex's call, example.org and alex.doe@example.com")]) == ["Alex"]


def test_exact_letter_matches_are_respelled_without_the_model():
    assert respell("I have the Quick Notes bot and the hubspot import", ["QuickNotes", "HubSpot"]) ==         "I have the QuickNotes bot and the HubSpot import"
    # Under six letters is too easily an ordinary phrase.
    assert respell("how to fix it", ["How-to"]) == "how to fix it"
    assert number_names(["Seven", "Harbor"], "email from Alex at seven") == ["Seven"]


def test_screen_spellings_replace_an_earlier_takes_misspelling():
    assert merge_terms(["Cobolt", "Grog", "OPS-49"], ["Kobalt", "Grok"]) == ["Kobalt", "Grok", "OPS-49"]


def test_a_name_may_become_a_term_that_looks_like_it():
    terms = ["Taylor", "HubSpot", "BlueHarbor"]
    assert drift_reason("Tell Tayler that the Hubspot import from Blue Harbor finished today.",
                        "Tell Taylor that the HubSpot import from BlueHarbor finished today.", terms=terms) is None
    # A dropped name is still drift when the gained term looks nothing like it.
    assert drift_reason("Ask Alex about the Grog plan for the release tomorrow morning.",
                        "Ask about the Grok plan for the release tomorrow morning.", terms=["Grok"]) == "names"


def test_a_term_slipped_in_beside_a_fix_is_drift():
    assert drift_reason("the other bots like quick notes and how to notes and quick puzzles but what about it",
                        "the other bots like QuickNotes and HowToNotes and How-to and QuickPuzzles but what about it",
                        terms=["QuickNotes", "HowToNotes", "How-to", "QuickPuzzles"]) == "added_terms"


def test_terms_appended_from_nowhere_are_drift():
    # A long take, so the five extra words stay under the expansion limit.
    source = ("That's an example of the copy I mean. It reads as a list of claims, it sounds redundant "
              "and kind of cheesy, and nobody would say it out loud, so let's rewrite it together.")
    output = source + " Team-Workspace About Us Archive HTML"
    assert drift_reason(source, output, terms=["Team-Workspace", "About", "Us", "Archive", "HTML"]) == "added_terms"
    # A term may replace a word that looks like it, not a different thing:
    # "G notes" is a folder, not Google Drive.
    assert drift_reason("Create folders in that G notes shared space for the new teams today.",
                        "Create folders in that Google Drive shared space for the new teams today.",
                        terms=["Google", "Drive"]) == "term_mismatch"
    assert drift_reason("Please update the open veeno runtime before the release today.",
                        "Please update the OpenVINO runtime before the release today.",
                        terms=["OpenVINO"]) is None


def test_numbers_and_short_labels_are_not_terms():
    assert terms_in("We moved it to October 22nd, version 2.5, script 1A, then OPS-49.") == ["October", "OPS-49"]


def test_screen_terms_keep_content_and_drop_app_chrome():
    items = [(50024, "HANDOFF.md"), (50000, "Minimize"), (50011, "Selection"),
             (50019, "Explorer (Ctrl+Shift+E)"), (50020, ""), (50005, "focus_probe.py"),
             (50007, "Ask Jordan about OPS-49"), (50024, "HANDOFF.md")]
    # One-word labels are names (a tab, a folder like "Recipes"), not sentence starts.
    assert screen_terms(items + [(50024, "Recipes 2")], "the OpenVINO runtime") == [
        "OpenVINO", "HANDOFF.md", "Explorer", "focus_probe.py", "Jordan", "OPS-49", "Recipes"]
    assert len(screen_terms([(50020, f"Item{i}x") for i in range(500)], limit=300)) == 300


def test_near_miss_finds_terms_the_take_misspells():
    assert near_miss("OpenVINO", "update the open veeno runtime")
    assert near_miss("HANDOFF.md", "open the handoff md file")
    assert near_miss("context.py", "edit context dot pie")
    assert near_miss("OPS-49", "link OBS 49 to it")
    # Spelled right already, unrelated, too short, or a plain word in lower case.
    assert not near_miss("OpenVINO", "update the OpenVINO runtime")
    assert not near_miss("Google", "the G notes folder")
    assert not near_miss("PR", "open a pr")
    assert not near_miss("Explorer", "open the explorer")


def test_only_screen_terms_the_take_seems_to_say_are_relevant():
    terms = ["HANDOFF.md", "Parakeet", "OpenVINO", "TEST-SCRIPTS.md"]
    assert relevant(terms, "check the handoff md and the open veeno notes") == ["HANDOFF.md", "OpenVINO"]
    assert relevant(terms, "nothing related here at all") == []
    # Closest first: a noisy partial match can't crowd out the real name.
    assert relevant(["Jane", "Kobalt"], "email from Alex Kobolt about the June notes", limit=1) == ["Kobalt"]
