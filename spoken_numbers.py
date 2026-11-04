"""Spoken numbers as digits, the way a style guide writes them.

Digits for 10 and up, decimals and versions, lists, labels ("phase 2"), units
("5 seconds", "10%"), years and clock times. "One of the", "the one" and lone
small numbers stay words, and ordinals are never touched. Parakeet writes
almost every number as words (19 of 549 saved takes had a digit).
"""
import re

SMALL = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen"
    " fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * i for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)}
SCALES = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9}
NUMBER = "|".join(sorted({*SMALL, *TENS, *SCALES}, key=len, reverse=True))
# Number words joined by spaces, hyphens, commas, "and" or "point".
RUN = re.compile(rf"\b(?:{NUMBER})\b(?:(?:,?\s+(?:(?:and|point)\s+)?|-)(?:{NUMBER})\b)*", re.I)
WORD = re.compile(r"[A-Za-z]+")
# "phase two", "PR eight". Issue keys ("OPS twenty three" -> OPS-23) come from the
# issue_keys setting.
LABELS = {"phase", "step", "number", "item", "option", "version", "issue", "pr", "line",
          "page", "section", "chapter", "part", "level", "round", "sprint", "ticket", "stage"}
UNITS = {"second", "seconds", "minute", "minutes", "hour", "hours", "day", "days", "week", "weeks",
         "month", "months", "year", "years", "ms", "millisecond", "milliseconds", "percent", "gig",
         "gigs", "gigabytes", "gb", "megabytes", "mb", "dollars", "bucks", "cents", "times", "takes",
         "inches", "feet", "miles"}
# A clock time needs a cue; "twelve forty five" alone could be a count.
TIME_CUES = {"at", "by", "until", "till", "around", "from", "before", "after"}
AMPM = re.compile(r"\s*[ap]\.?\s?m\b\.?", re.I)
PREVIOUS = re.compile(r"([A-Za-z0-9]+)\s+$")
NEXT = re.compile(r"\s*([A-Za-z%]+)")
# "one or two" stays words, "two to 3 weeks" becomes "2 to 3 weeks".
RANGE = re.compile(r"\b(" + "|".join(w for w, v in SMALL.items() if v < 10) + r")(\s+(?:to|or|through)\s+)(?=\d)", re.I)
DIGITS = re.compile(r"\d+(?:[.,:/]\d+)*")
# Dates. Parakeet usually capitalizes months but not always ("october twenty
# second"). "May" and "March" are also verbs, so they match only capitalized,
# and take only ordinal days ("May first"), since they also start sentences.
MONTHS = ("(?i:January|February|April|June|July|August|September|October|November|December)"
          "|May|March")
ORDINALS = {w: i for i, w in enumerate(
    "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth"
    " fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth".split(), 1)} | {"thirtieth": 30}
UNIT_WORDS = "one|two|three|four|five|six|seven|eight|nine"
DAY_ORDINAL = (r"(?:(?:twenty|thirty)[- ](?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth)"
               r"|" + "|".join(sorted(ORDINALS, key=len, reverse=True)) + ")")
DAY_NUMBER = rf"(?:(?:twenty|thirty)[- ](?:{UNIT_WORDS})|{NUMBER})"
# A spoken day ("October twenty two") must end the phrase or precede a year:
# "in August nine people joined" is a count.
MONTH_DAY = re.compile(rf"\b({MONTHS})\s+((?i:{DAY_ORDINAL})\b|(?i:{DAY_NUMBER})\b"
                       rf"(?=\s*(?:[,.!?;]|$)|\s+(?i:twenty|nineteen|two\s+thousand)\b))"
                       rf"(?![- ](?i:{UNIT_WORDS})\b)")
DAY_OF_MONTH = re.compile(rf"\b((?i:the)\s+)((?i:{DAY_ORDINAL}))(\s+of\s+(?:{MONTHS})\b)")
# "the date is ten twenty two twenty six": month, day and year spoken as numbers.
DATE_CUE = re.compile(r"\b(?:date\s+is|dated|date\s+of)\s+", re.I)
CENTURY_WORDS = "eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty"
DECADES = {w: i for i, w in enumerate(
    "twenties thirties forties fifties sixties seventies eighties nineties".split(), 2)}
CENTURY = re.compile(rf"\b({CENTURY_WORDS})\s+hundreds\b", re.I)
DECADE = re.compile(rf"\b({CENTURY_WORDS})\s+({'|'.join(DECADES)})\b", re.I)
WRITTEN_DATE = re.compile(r"(\d{1,2}) ?(\d{2})[- ](\d{2}|\d{4})\b")


def _day(words):
    """1 to 31 from "twenty second" or "twenty two", with its ordinal flag; else None."""
    parts = re.split(r"[- ]", words.lower())
    value = 0
    for part in parts:
        value += ORDINALS.get(part) or SMALL.get(part) or TENS.get(part) or 0
    return (value, parts[-1] in ORDINALS) if 1 <= value <= 31 else (None, False)


def _ordinal(n):
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _dates(text):
    def month_day(m):
        value, ordinal = _day(m.group(2))
        if value is None or (m.group(1) in ("May", "March") and not ordinal):
            return m.group()
        return f"{m.group(1).capitalize()} {_ordinal(value) if ordinal else value}"

    def day_of_month(m):
        value, _ = _day(m.group(2))
        return m.group() if value is None else m.group(1) + _ordinal(value) + m.group(3)

    def numeric(m):
        run = RUN.match(text, m.end())
        if not run:
            return None
        groups = _parse([t.group().lower() for t in WORD.finditer(run.group())])
        if any(g[3] for g in groups):
            return None
        values = [int(g[2]) for g in groups]
        if len(values) == 4 and values[2] in (19, 20) and 10 <= values[3] <= 99:
            values = values[:2] + [values[2] * 100 + values[3]]  # "twenty twenty five"
        if len(values) != 3:
            return None
        month, day, year = values
        if not (1 <= month <= 12 and 1 <= day <= 31 and (year < 100 or 1900 <= year <= 2099)):
            return None
        return run, f"{month}/{day}/{year:02d}" if year < 100 else f"{month}/{day}/{year}"

    def written(m):
        # Parakeet sometimes writes the digits itself, as "1022-26" or "10 22 26".
        found = WRITTEN_DATE.match(text, m.end())
        if not found:
            return None
        month, day, year = (int(g) for g in found.groups())
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return None
        return found, f"{month}/{day}/{found.group(3)}"

    # Centuries and decades: "eighteen hundreds" -> 1800s, "nineteen nineties" -> 1990s.
    text = CENTURY.sub(lambda m: f"{SMALL.get(m.group(1).lower()) or TENS[m.group(1).lower()]}00s", text)
    text = DECADE.sub(lambda m: f"{SMALL.get(m.group(1).lower()) or TENS[m.group(1).lower()]}"
                                f"{DECADES[m.group(2).lower()]}0s", text)
    text = MONTH_DAY.sub(month_day, text)
    text = DAY_OF_MONTH.sub(day_of_month, text)
    out, pos = [], 0
    for cue in DATE_CUE.finditer(text):
        found = numeric(cue) or written(cue)
        if found:
            run, date = found
            out += [text[pos:run.start()], date]
            pos = run.end()
    return "".join(out) + text[pos:]


def _fraction(words, j):
    """Digits spoken after "point": "one three" is 13, "twenty five" is 25."""
    digits = ""
    while j < len(words):
        w = words[j]
        if w in TENS and j + 1 < len(words) and 1 <= SMALL.get(words[j + 1], 0) <= 9:
            digits, j = digits + str(TENS[w] + SMALL[words[j + 1]]), j + 2
        elif w in TENS or w in SMALL:
            digits, j = digits + str(TENS.get(w, SMALL.get(w))), j + 1
        else:
            break
    return digits, j


def _parse(words):
    """Split a run of number words into numbers: [(first, last, text, decimal)]."""
    groups, i = [], 0
    while i < len(words):
        if words[i] in ("and", "point") or words[i] in SCALES:
            # A bare "hundred" or a joiner with no number before it stays a word.
            i += 1
            continue
        total, current, seg, j, decimal = 0, 0, None, i, ""
        while j < len(words):
            w = words[j]
            if w in SMALL and (seg in (None, "scale") or (seg == "tens" and 1 <= SMALL[w] <= 9)):
                current, seg = current + SMALL[w], "tens_small" if seg == "tens" else "small"
            elif w in TENS and seg in (None, "scale"):
                current, seg = current + TENS[w], "tens"
            elif w in SCALES and seg in ("small", "tens", "tens_small"):
                if SCALES[w] == 100:
                    if current >= 100:
                        break
                    current *= 100
                else:
                    total, current = total + current * SCALES[w], 0
                seg = "scale"
            elif w == "and" and seg == "scale" and j + 1 < len(words) and (words[j + 1] in SMALL or words[j + 1] in TENS):
                pass
            elif w == "point" and seg and j + 1 < len(words):
                digits, k = _fraction(words, j + 1)
                if not digits:
                    break
                decimal, j = decimal + "." + digits, k
                # "one point zero point one" is a version; anything else ends it.
                if j < len(words) and words[j] == "point":
                    continue
                break
            else:
                break
            j += 1
        if j == i:
            i += 1
            continue
        last = j - 1
        while words[last] in ("and", "point"):
            last -= 1
        groups.append((i, last, str(total + current) + decimal, bool(decimal)))
        i = last + 1
    return groups


def _issue_keys(keys):
    """Lowercase spelling -> key; Parakeet can hear an O in a key as a zero."""
    return {spelling: key.upper() for key in keys for spelling in (key.lower(), key.lower().replace("o", "0"))}


def _convert(text, aggressive, keys):
    issue_keys = _issue_keys(keys)
    labels = LABELS | set(issue_keys)
    out, pos = [], 0
    for run in RUN.finditer(text):
        tokens = list(WORD.finditer(run.group()))
        words = [t.group().lower() for t in tokens]
        groups = _parse(words)
        if not groups:
            continue
        span = lambda g: (run.start() + tokens[g[0]].start(), run.start() + tokens[g[1]].end())
        before = PREVIOUS.search(text, 0, run.start())
        prev = before.group(1).lower() if before and before.end() == run.start() else ""
        after = NEXT.match(text, run.end())
        nxt = after.group(1).lower() if after else ""
        ampm = bool(AMPM.match(text, run.end()))
        seps = [text[span(a)[1]:span(b)[0]] for a, b in zip(groups, groups[1:])]
        values = [int(g[2]) if not g[3] else None for g in groups]
        replace = {}  # group index -> digits
        start = run.start()
        if len(groups) >= 3 and all(re.fullmatch(r",?\s+(?:and\s+)?|-", s) for s in seps):
            replace = {k: g[2] for k, g in enumerate(groups)}
        elif len(groups) == 2 and None not in values and re.fullmatch(r"\s+|-", seps[0]):
            a, b = values
            single = groups[0][0] == groups[0][1]
            if (prev in TIME_CUES or ampm) and 1 <= a <= 12 and 10 <= b <= 59:
                replace = {0: f"{a}:{b}", 1: ""}
            elif single and a in (19, 20) and 10 <= b <= 99:
                replace = {0: f"{a}{b}", 1: ""}
            elif prev in labels and 1 <= a <= 9 and 10 <= b <= 99:
                replace = {0: f"{a}{b}", 1: ""}
            elif aggressive:
                replace = {0: str(a), 1: str(b)}
        else:
            for k, g in enumerate(groups):
                value = values[k]
                # "one of the" may become "a" in Polish without changing a number.
                lone_one = len(groups) == 1 and g[0] == g[1] and words[g[0]] == "one"
                if (g[3] or value >= 10 or (k == 0 and prev in labels)
                        or (k == len(groups) - 1 and (ampm or nxt == "percent" or (nxt in UNITS and value >= 2)))
                        or (aggressive and not lone_one)):
                    replace[k] = g[2]
            # "two and three weeks": the unit covers every number in the run.
            if len(groups) - 1 in replace and nxt in UNITS:
                replace = {k: g[2] for k, g in enumerate(groups)}
        if not replace:
            continue
        if 0 in replace and prev in issue_keys and before.end() == run.start():
            start = before.start()
            replace[0] = issue_keys[prev] + "-" + replace[0]
        out.append(text[pos:start])
        cursor = start
        for k, g in enumerate(groups):
            a, b = span(g)
            if k not in replace:
                continue
            if replace[k] == "":
                # Merged into the previous number ("12:45"): drop the space too.
                out.append(replace.pop(k))
                cursor = b
                continue
            # The issue key is rewritten with the number: "K0 twenty three" -> "KO-23".
            out.append("" if k == 0 and start != run.start() else text[cursor:a])
            out.append(replace[k])
            cursor = b
        pos = cursor
        if len(groups) - 1 in replace and nxt == "percent" and replace[len(groups) - 1]:
            out.append("%")
            pos = after.end()
    out.append(text[pos:])
    result = "".join(out)
    return RANGE.sub(lambda m: str(SMALL[m.group(1).lower()]) + m.group(2), result)


def to_digits(text, issue_keys=()):
    """Write spoken numbers as digits where a style guide would."""
    return _convert(_dates(text), False, issue_keys)


def number_values(text, issue_keys=()):
    """Every number in text by value, spoken or written, for drift checks."""
    return [n.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+", n) else n
            for n in DIGITS.findall(_convert(_dates(text), True, issue_keys))]
