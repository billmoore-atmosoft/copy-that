import pytest
from cleanup import apply_rules, drift_reason
from spoken_numbers import number_values, to_digits


@pytest.mark.parametrize("spoken, written", [
    # Compound and large numbers.
    ("within twenty-four hours", "within 24 hours"),
    ("as far as ninety days", "as far as 90 days"),
    ("Start twenty three and thirty", "Start 23 and 30"),
    ("from four hundred and fifty pages", "from 450 pages"),
    ("two thousand", "2000"),
    ("eleven people", "11 people"),
    # Units make small numbers digits; percent becomes a sign.
    ("the last five seconds", "the last 5 seconds"),
    ("three weeks old", "3 weeks old"),
    ("sixteen gig of memory", "16 gig of memory"),
    ("ten percent", "10%"),
    ("one hundred percent", "100%"),
    ("two or three days", "2 or 3 days"),
    ("between two and three weeks", "between 2 and 3 weeks"),
    # Spoken lists of three or more.
    ("testing one, two, three, four, five.", "testing 1, 2, 3, 4, 5."),
    ("renders numbers one two three as words", "renders numbers 1 2 3 as words"),
    # Labels.
    ("a phase two solution", "a phase 2 solution"),
    ("the value of number two", "the value of number 2"),
    ("step three", "step 3"),
    ("PR eight", "PR 8"),
    ("PR five seventy eight", "PR 578"),
    # Decimals and versions.
    ("two point five", "2.5"),
    ("zero point five", "0.5"),
    ("version two point one", "version 2.1"),
    ("shows one point zero point one point one three.", "shows 1.0.1.13."),
    # Years, and clock times only with a cue or am/pm.
    ("in twenty twenty six", "in 2026"),
    ("my call at twelve forty-five and", "my call at 12:45 and"),
    ("again at six fourteen PM", "again at 6:14 PM"),
    ("nine thirty p.m.", "9:30 p.m."),
    ("at nine am", "at 9 am"),
])
def test_spoken_numbers_become_digits(spoken, written):
    assert to_digits(spoken) == written


@pytest.mark.parametrize("text", [
    "one of the things", "a couple of tests", "the one I want", "one thing", "no one", "someone",
    "the first one", "the second take", "I have nine things", "one or two", "one, two",
    "a hundred things", "the one and only", "at one point we", "fifty-fifty", "one-on-one",
    # Without a cue, a pair could be a count or a code: leave it to the reader.
    "twelve forty five", "a code review on Five Seventy Eight", "one second please",
])
def test_casual_numbers_stay_words(text):
    assert to_digits(text) == text


def test_rules_convert_numbers_but_not_protected_spans():
    assert apply_rules("wait ten seconds then run python three twenty two") == "Wait 10 seconds then run python three twenty two"
    assert apply_rules("um is KO twenty three done.", issue_keys=["KO"]) == "Is KO-23 done?"


def test_number_drift_compares_values():
    assert number_values("twenty three and ten percent") == ["23", "10"]
    assert number_values("one of the 1,000 takes") == ["1000"]
    source = "We have twenty three open issues and five builds left"
    assert drift_reason(source, "We have 23 open issues and 5 builds left.") is None
    assert drift_reason(source, "We have 32 open issues and 5 builds left.") == "numbers"
    assert drift_reason("Please send 15 copies today", "Please send fifty copies today") == "numbers"


@pytest.mark.parametrize("spoken, written", [
    # "twenty second" was read as a unit of time.
    ("it's October twenty second, two thousand twenty six", "it's October 22nd, 2026"),
    ("actually October twenty second, not October twentieth.", "actually October 22nd, not October 20th."),
    ("the date is ten twenty two twenty six.", "the date is 10/22/26."),
    ("dated three fifteen twenty twenty five", "dated 3/15/2025"),
    ("on the twenty first of March", "on the 21st of March"),
    ("by October twenty two.", "by October 22."),
    ("May first or March third", "May 1st or March 3rd"),
    ("from June eleventh", "from June 11th"),
    ("if it's in the eighteen hundreds and", "if it's in the 1800s and"),
    ("music from the nineteen nineties", "music from the 1990s"),
    ("the twenty twenties so far", "the 2020s so far"),
    ("The date is 1022-26.", "The date is 10/22/26."),
    ("the date is 2026-10-22", "the date is 2026-10-22"),
    ("the launch is october twenty second, two thousand twenty six", "the launch is October 22nd, 2026"),
])
def test_spoken_dates(spoken, written):
    assert to_digits(spoken) == written


@pytest.mark.parametrize("text", [
    "in August nine people joined",   # a count after a month, not a day
    "you may two-step it",            # lowercase "may" is a verb
    "they march nine abreast",        # and so is "march"
    "May one day work",               # May and March need an ordinal day
    "the date is next week",
])
def test_month_words_that_are_not_dates(text):
    assert to_digits(text) == text


def test_sentence_after_a_number_is_capitalized():
    assert apply_rules("numbers one, two, three, four, five. it's late") == "Numbers 1, 2, 3, 4, 5. It's late"


def test_spelled_letters_join_before_numbers():
    assert apply_rules("put this in the PR for K O twenty three", issue_keys=["KO"]) == "Put this in the PR for KO-23"
    assert apply_rules("L O L, it wrote T H U Z Z") == "LOL, it wrote THUZZ"
    assert apply_rules("So I I think A better plan") == "So I I think A better plan"


def test_issue_keys_come_from_the_setting():
    assert to_digits("link KO forty nine") == "link KO 49"
    assert to_digits("link KO forty nine", issue_keys=["KO"]) == "link KO-49"
    assert to_digits("a PR for K0 twenty three and", issue_keys=["KO"]) == "a PR for KO-23 and"
    assert to_digits("KO forty four is done", issue_keys=["KO"]) == "KO-44 is done"
    assert to_digits("link ENG forty nine", issue_keys=["ENG"]) == "link ENG-49"
    assert to_digits("link KO forty nine", issue_keys=["ENG"]) == "link KO 49"


def test_spoken_underscore_and_file_dash():
    assert apply_rules("the file is dictation underscore runtime.py") == "The file is dictation_runtime.py"
    assert apply_rules("open requirements dash build.txt") == "Open requirements-build.txt"
    assert apply_rules("see test dash scripts dash final.md and add a dash of salt") == \
        "See test-scripts-final.md and add a dash of salt"
