"""The dev-only reference encoding of the diary conventions documented in
``skills/diary/`` (the two-operation adapter interface, the template-vs-
matched-recent-structure format resolution, the empty-diary minimal default)
and pinned in ``specs/008-diary-adapter/data-model.md``.

This module IS: the dev-only CI instrument that lets those documented rules
be *exercised* by hermetic tests (Constitution VIII) instead of merely
asserted on prose. Nothing here ships (Constitution I; FR-008) — the diary
skill ships no adapter code, and at runtime the "formatter" is an agent
reading entries through the diary capability's operations, guided by the
skill's prose, not this module.

This module is NOT: proof that a live agent actually follows that prose when
it drafts a real close-time entry. That is design §10's scenario-harness
territory — a live-agent exercise with fixture incidents and a deterministic
assertion script over artifacts, never a hermetic unit/contract test. This
module only pins what "correct" looks like for the fixtures a hermetic test
can run against; it says nothing about agent behavior.

House style mirrors ``tests/helpers/catalog_reference.py``: plain functions
over plain dicts (no classes, no dataclasses), each step's comment citing the
prose section it encodes.
"""

import re

# ---------------------------------------------------------------------------
# Module-level vocabularies (data-model.md §3, §4, §6, §9), exported so later
# gates can assert against them rather than a test-local copy.
# ---------------------------------------------------------------------------

# data-model.md §4 "Notice vocabulary" — closed, four kinds. The
# prose↔encoding agreement gate (T023) asserts this equal, BOTH WAYS, to the
# kinds `skills/diary/references/format.md` names — a doc naming a notice
# the encoding never emits, or the encoding emitting one the doc never
# names, are equally wrong.
NOTICE_KINDS = frozenset(
    {
        "template_malformed",
        "entries_inconsistent",
        "date_ambiguous",
        "template_candidate",
    }
)

# data-model.md §9 / research R8 — the FR-003 instrument: format resolution's
# complete declared input set. T011's input-signature gate asserts this set,
# together with `inspect.signature(resolve_format).parameters`, disjoint from
# the session row's field names (parsed dynamically from
# skills/session-store/references/schema.md's column table) — data-model §9's
# own accepted-weak instrument, recorded there as such.
FORMAT_INPUT_KEYS = frozenset({"template", "entries", "content"})

# data-model.md §3 — the four named parts of a Structure. Exported so T023's
# both-ways gate can assert this list against the parts
# `skills/diary/references/format.md` documents, same reasoning as
# NOTICE_KINDS above.
STRUCTURE_PARTS = ("title", "sections", "date_format", "field_order")

# research R2 — read depth `n` defaults to 5, overridable by the additive
# workspace-config key `battleBuddy.diary.recentEntries` (integer >= 1). This
# slice documents the default and the knob; it does not read config itself
# (no code ships). Research R14(1) records, plainly, that this is a
# deferral, not a wired feature: no landed consumer reads that key yet —
# slice 5's close-flow encoding (`tests/helpers/lifecycle_flows.py`,
# `draft_close`) hardcodes the depth at 5 rather than reading the key. The
# default happens to equal that hardcoded value, so behavior today is
# identical either way; only a team that sets the key would notice, and no
# team can set it yet.
DEFAULT_READ_DEPTH = 5

# data-model.md §6 "The empty-diary minimal default" — the skeleton text,
# VERBATIM. T023's prose↔encoding agreement gate asserts this constant
# byte-identical to the copy quoted in skills/diary/references/format.md, so
# its exact characters (including blank-line placement and the em dash) are
# load-bearing, not incidental formatting.
MINIMAL_DEFAULT_TEXT = """# YYYY-MM-DD — <services>: <short title>

## What happened
## Timeline
## Resolution
## Root cause (proposal)
## Contributing factors (proposals)
## Action items (proposals)
## Evidence
"""

# data-model.md §6 — MINIMAL_DEFAULT_TEXT's Structure. HAND-WRITTEN, and
# deliberately NOT derived from MINIMAL_DEFAULT_TEXT by running
# extract_structure over it (that function does not even exist yet in this
# Phase-2 module — see T006), even though extract_structure(MINIMAL_DEFAULT_TEXT)
# does reproduce this constant exactly (data-model.md §6's pattern-language
# rule makes the skeleton's "YYYY-MM-DD" title line date-bearing, so nothing
# below is undiscoverable by extraction — an earlier draft of this comment
# claimed otherwise; that claim was wrong and has been removed). The
# remaining reason is phase ordering, not a gap in what extraction can find:
# deriving this constant at import time would make this Phase-2 module
# (T004/T005 — module + constants only) depend on extract_structure, a
# Phase-3 function (T006) — a circular dependency the phase split forbids.
#
# T023 gates the two constants' agreement instead, at test time rather than
# import time: it asserts extract_structure(MINIMAL_DEFAULT_TEXT) equals
# MINIMAL_DEFAULT IN FULL — every part, including `title` and `date_format`
# (data-model.md §6 "Two names, deliberately").
MINIMAL_DEFAULT = {
    "title": {"marker": "atx", "level": 1, "text": "YYYY-MM-DD — <services>: <short title>"},
    "sections": [
        {"marker": "atx", "level": 2, "text": "What happened"},
        {"marker": "atx", "level": 2, "text": "Timeline"},
        {"marker": "atx", "level": 2, "text": "Resolution"},
        {"marker": "atx", "level": 2, "text": "Root cause (proposal)"},
        {"marker": "atx", "level": 2, "text": "Contributing factors (proposals)"},
        {"marker": "atx", "level": 2, "text": "Action items (proposals)"},
        {"marker": "atx", "level": 2, "text": "Evidence"},
    ],
    "date_format": {"pattern": "YYYY-MM-DD", "ambiguous": False},
    "field_order": [
        "what happened",
        "timeline",
        "resolution",
        "root cause (proposal)",
        "contributing factors (proposals)",
        "action items (proposals)",
        "evidence",
    ],
}


# ---------------------------------------------------------------------------
# extract_structure (data-model.md §3) — heading recognition, date-format
# detection and field_order, plus their shared regex primitives.
# ---------------------------------------------------------------------------

# §3 "Heading recognition" — exactly two shapes, both anchored to the WHOLE
# line (re.match, not re.search): a line that merely contains bold text is
# not a heading.
_ATX_RE = re.compile(r"^(#{1,6}) +(\S.*)$")
_BOLD_RE = re.compile(r"^\*\*(.+)\*\*$")

# §3 "field_order" inline fields — letter-anchored per the pinned regex
# ^[A-Za-z][^:\n]{0,39}:, PLUS one refinement beyond that literal pattern: a
# negative lookbehind rejecting a digit immediately before the colon.
#
# JUDGMENT CALL, flagged for review: the literal regex alone still treats a
# clock time embedded after a word prefix (e.g. "At 14:12 the alert fired.")
# as a label ("at 14"), because the letter anchor only blocks a BARE
# "14:12..." line (first char a digit) — it says nothing about a colon that
# shows up a few words in. Every entries-*.json timeline paragraph in this
# fixture roster opens exactly that way ("At HH:MM ..."), and the
# data-model's own rationale for the anchor — "a clock time... is the one
# thing that looks like a label while varying per entry, and admitting it
# would make an otherwise-uniform diary classify as inconsistent" — applies
# just as much to the prefixed form as to the bare one; without this
# refinement entries-consistent.json would extract a different "at hh" field
# per entry and spuriously trip entries_inconsistent. The lookbehind is the
# smallest change that honors that stated rationale, and it costs nothing
# against a genuine label: none in this roster ends its label text in a
# digit (they end in letters or a closing paren, e.g. "(proposals)").
_INLINE_FIELD_RE = re.compile(r"^[A-Za-z][^:\n]{0,39}(?<!\d):")

# §3 date_format tokens — worked cases: "2026-07-21" -> "YYYY-MM-DD";
# "21 Jul 2026" -> "DD Mon YYYY"; "July 4, 2026" -> "Month D, YYYY";
# "07/21/2026" -> "MM/DD/YYYY". Four shapes, tried in a fixed priority
# order per line so a line only ever yields one reading. Concrete years in
# shape 1 (year-first / ISO) are matched only as 4 written digits (never a
# bare 2-digit number) — requiring 4 digits keeps that shape from ever
# mistaking a numeric day/month component (e.g. the "09" in "09/08/2026")
# for a year. Shapes 2/3/4 — every shape whose year sits in the TRAILING
# position — accept a written 2-digit year too; see _YEAR_TRAILING_ALT
# below for why all three are safe.
_MONTH_FULL = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_YEAR_ALT = r"\d{4}|YYYY|YY"
# F4 (review round) — the token table (format.md, data-model.md §3) declares
# YY as a real 2-digit-year token, but only the year-last shape's regex
# used to require 4 written digits, so a title like "07/21/26" carried no
# date-bearing line at all.
#
# G2 (round 2) — F4 scoped the fix to the year-last shape alone, but the
# NAMED-MONTH shapes below (day-monthname-year, monthname-day-year) still
# required 4 written digits too, so "# 21 Jul 26 — payments: outage" and
# "July 4, 26" carried no date-bearing title line either — the exact F4
# failure mode, just reached through a different shape. G2's fix widened
# both named-month shapes unconditionally, and its comment justified that
# by arguing neither shape can "mistake a component for a year" — true,
# but beside the point: that argument is about confusion INSIDE a date
# (which component is the year), and says nothing about ordinary prose
# that merely happens to contain the same token shapes with no date
# intended at all ("On Jul 4, 15 nodes went down." reads as Mon D, YY once
# a 2-digit year is accepted unconditionally).
#
# H1 (round 3, REGRESSION fix) — the year-last numeric shape below
# (_YEAR_LAST_RE) keeps G2's unconditional widening: three bare numeric
# components joined by "-"/"/" is not a shape ordinary English prose
# produces, so _YEAR_TRAILING_ALT is untouched and still serves that shape
# alone.
_YEAR_TRAILING_ALT = r"\d{4}|\d{2}|YYYY|YY"
#
# J1/J2 (round 4, REPLACES H1's named-month gate) — H1 gated the two
# NAMED-MONTH shapes' 2-digit-year alternative on what followed the year (a
# trailing-punctuation whitelist: end-of-line or one of "— – : , ) ]").
# Round 4 proved that gate wrong in BOTH directions: it REJECTED real diary
# titles whose trailing punctuation was not on the list (a plain ASCII
# hyphen, an opening "(" or "[", a bold closer "**"), and it still ADMITTED
# prose that happened to punctuate its trailing digits with something on
# the list — "On Jul 4, 15: nodes went down." reads as "Mon D, YY" once ","
# and ":" are both whitelisted, exactly the prose H1 itself set out to
# reject.
#
# The reason no trailing-punctuation rule can ever separate the two: a
# 2-digit year is genuinely ambiguous with an ordinary count in prose ("Jul
# 4, 15 nodes"), and prose can be punctuated however the writer likes, so
# there is no fixed set of "safe" trailing characters. What actually
# differs is POSITION, not punctuation: a diary entry's title *leads* with
# its date, and prose does not. `_named_month_2digit_match` below encodes
# that directly — see its docstring — rather than trying yet another
# trailing-context whitelist. A 4-digit year needs none of this: it is
# distinctive enough on its own to stay positionally free, exactly as
# before.
_YEAR_4DIGIT_ALT = r"\d{4}|YYYY"
_YEAR_2DIGIT_ALT = r"\d{2}|YY"
_MONTHNUM_ALT = r"\d{1,2}|MM|M"
_DAYNUM_ALT = r"\d{1,2}|DD|D"
_DAYMONTHNUM_ALT = r"\d{1,2}|MM|M|DD|D"
# H6 (round 3) — month-name matching is case-insensitive ("3 jul 2026",
# "JULY 4, 2026" now recognized), scoped to this one alternation via the
# inline `(?i:...)` group rather than a whole-pattern re.IGNORECASE, so the
# surrounding day/year alternatives (MM/DD/etc. pattern-language tokens,
# case-sensitive by design) are untouched. Rendering stays canonical
# regardless of how the month was written: _month_name_token below keys
# off the matched text's LENGTH, not its case, so "jul" and "JUL" both
# still render "Mon".
_MONTHNAME_ALT = (
    r"(?i:" + "|".join(_MONTH_FULL + _MONTH_ABBR + ("Month", "Mon")) + r")\b"
)

# F12 (review round) — a numeric run glued to more digits/dots on either
# side is not a date component; it is far more likely a fragment of
# something else entirely (a version string, a build number). These are
# match BOUNDARIES only, never a calendar-validity check: a genuinely
# standalone "1234-56-78" still reads as YYYY-MM-DD (data-model.md §3's own
# "we extract a format, not a valid date" posture is untouched by this).
# The leading guard is two separate fixed-width negative lookbehinds
# (Python's `re` only allows fixed-width lookbehind, so "adjacent to a
# digit/dot" and "adjacent to a separator that is itself glued to a
# digit/dot" — e.g. the "3-" in "1.2.3-4/5/2026" — are stated as two rather
# than one variable-width assertion); the trailing guard has no such
# restriction since lookahead may be any width.
#
# G1 (REGRESSION, round 2) — F12's original trailing guard, `(?![\d.])`,
# blocked a bare "." right after the date, not just a "." that is itself
# glued to more digits. A sentence-final date — "See 07/21/2026.",
# "July 4, 2026.", "2026-07-21." — carried no date-bearing line at all,
# because the guard could not tell a genuine trailing period from a
# version-string dot. The fix narrows the guard to what F12 actually needs
# to reject: a digit immediately after (still bare, e.g. the "5" in
# "2026.5"), or a "." immediately followed by a digit (the ".5" in
# "2026.5"); a "." followed by nothing or by a non-digit now passes. The
# `(?![-/][\d.])` half is untouched — it is what still rejects
# "2026-07-21-3" and the "3-" boundary in "1.2.3-4/5/2026".
_NOT_PRECEDED_BY_DIGIT_RUN = r"(?<![\d.])(?<![\d.][-/])"
_NOT_FOLLOWED_BY_DIGIT_RUN = r"(?!\d)(?!\.\d)(?![-/][\d.])"

# Shape 1 — year-first numeric (ISO-shaped): "2026-07-21", or the
# pattern-language line "YYYY-MM-DD" itself (MINIMAL_DEFAULT_TEXT's title).
# The leading year anchors month-then-day order by convention, so this
# shape is never ambiguous — §3.1 only concerns the year-LAST shape below.
_ISO_YEAR_FIRST_RE = re.compile(
    _NOT_PRECEDED_BY_DIGIT_RUN
    + r"(?P<year>{year})(?P<sep>[-/])(?P<c1>{mnum})(?P=sep)(?P<c2>{dnum})".format(
        year=_YEAR_ALT, mnum=_MONTHNUM_ALT, dnum=_DAYNUM_ALT
    )
    + _NOT_FOLLOWED_BY_DIGIT_RUN
)
# Shape 2 — year-last, two bare numeric components: "07/21/2026". This is
# the shape §3.1's ambiguity pass concerns — see _date_format_for_line.
_YEAR_LAST_RE = re.compile(
    _NOT_PRECEDED_BY_DIGIT_RUN
    + r"(?P<c1>{dm})(?P<sep1>[-/])(?P<c2>{dm})(?P<sep2>[-/])(?P<year>{year})".format(
        dm=_DAYMONTHNUM_ALT, year=_YEAR_TRAILING_ALT
    )
    + _NOT_FOLLOWED_BY_DIGIT_RUN
)
# Shape 3 — "21 Jul 2026" / "21 Month 2026": day, named month, year. Split
# into a 4-digit variant (positionally free, matched with .search() like
# every other shape) and a 2-digit variant (position-gated — see
# _named_month_2digit_match, J1/J2 round 4).
_DAY_MONTHNAME_YEAR_4DIGIT_RE = re.compile(
    _NOT_PRECEDED_BY_DIGIT_RUN
    + r"(?P<day>{dnum})(?P<sep1>\s+)(?P<month>{mname})(?P<sep2>\s+)(?P<year>{year})".format(
        dnum=_DAYNUM_ALT, mname=_MONTHNAME_ALT, year=_YEAR_4DIGIT_ALT
    )
    + _NOT_FOLLOWED_BY_DIGIT_RUN
)
_DAY_MONTHNAME_YEAR_2DIGIT_RE = re.compile(
    _NOT_PRECEDED_BY_DIGIT_RUN
    + r"(?P<day>{dnum})(?P<sep1>\s+)(?P<month>{mname})(?P<sep2>\s+)(?P<year>{year})".format(
        dnum=_DAYNUM_ALT, mname=_MONTHNAME_ALT, year=_YEAR_2DIGIT_ALT
    )
    + _NOT_FOLLOWED_BY_DIGIT_RUN
)
# Shape 4 — "July 4, 2026": named month, day, comma, year. Same 4-digit /
# 2-digit split as shape 3.
_MONTHNAME_DAY_YEAR_4DIGIT_RE = re.compile(
    r"(?P<month>{mname})(?P<sep1>\s+)(?P<day>{dnum}),(?P<sep2>\s*)(?P<year>{year})".format(
        mname=_MONTHNAME_ALT, dnum=_DAYNUM_ALT, year=_YEAR_4DIGIT_ALT
    )
    + _NOT_FOLLOWED_BY_DIGIT_RUN
)
_MONTHNAME_DAY_YEAR_2DIGIT_RE = re.compile(
    r"(?P<month>{mname})(?P<sep1>\s+)(?P<day>{dnum}),(?P<sep2>\s*)(?P<year>{year})".format(
        mname=_MONTHNAME_ALT, dnum=_DAYNUM_ALT, year=_YEAR_2DIGIT_ALT
    )
    + _NOT_FOLLOWED_BY_DIGIT_RUN
)

# J1/J2 (round 4) — the leading marker a 2-digit-year named-month date must
# sit right after, once stripped: an ATX heading marker ("#" x1-6 plus
# required space, data-model.md §3 "Heading recognition") or a bold
# wrapper's opening "**". Only the LEADING marker matters here — the
# function below never requires a matching bold closer — this is a
# position rule, not a re-implementation of heading recognition.
_LEADING_ATX_MARKER_RE = re.compile(r"^#{1,6} +")


def _strip_leading_marker(line):
    """Strips one leading ATX marker or bold-wrapper opener, plus
    surrounding whitespace, per the decision's own wording ("after
    stripping any leading heading marker and bold wrapper (#{1,6}, **, and
    surrounding whitespace)"). Returns (remainder, had_marker).

    A line with neither marker passes through with only its own leading
    whitespace trimmed, and had_marker=False — a bare line can still carry
    a title-shaped date (see _named_month_2digit_match), it just gets the
    stricter, whole-line half of that rule rather than the free-trailing
    half a marked line gets.
    """
    text = line.lstrip()
    atx_match = _LEADING_ATX_MARKER_RE.match(text)
    if atx_match:
        return text[atx_match.end():].lstrip(), True
    if text.startswith("**"):
        return text[2:].lstrip(), True
    return text, False


def _named_month_2digit_match(regex, line):
    """The J1/J2 (round 4) start-of-line rule for a named-month shape's
    2-digit-year alternative: recognized only when the date sits at the
    START of the line's text, after stripping any leading heading marker or
    bold wrapper and surrounding whitespace (_strip_leading_marker) — never
    by what follows it.

    That "start of line's text" requirement has two different shapes
    depending on what, if anything, was stripped:

    - **A marker was present** (this line is heading-shaped): the date only
      has to LEAD the heading's own text; anything may follow it, since
      that is what a real diary title looks like — "21 Jul 26 - checkout:
      latency", "21 Jul 26 (checkout)", "21 Jul 26 [P1]" are all one
      heading's worth of text with the date first.
    - **No marker was present** (a bare line): there is no heading marker
      to signal "this line is a title", so the date must be the line's
      ENTIRE content (aside from trailing whitespace) for position alone to
      carry that signal. Without this half, "Dec 25, 10 alerts fired."
      would satisfy a naive "starts at position 0" check — the date really
      is the first thing on the line — and still fabricate a date out of
      ordinary prose, the exact failure mode this whole rule exists to
      close. "21 Jul 26" and "July 4, 26" (nothing else on the line) pass;
      "Dec 25, 10 alerts fired." (trailing prose after the date) does not.

    Returns the match object or None.
    """
    remainder, had_marker = _strip_leading_marker(line)
    match = regex.match(remainder)
    if match is None:
        return None
    if not had_marker and remainder[match.end():].strip() != "":
        return None
    return match


def _normalize_label(text):
    """§3 field_order normalization: lowercase, one trailing ':' stripped,
    internal whitespace collapsed. Shared by extract_structure's field_order
    and apply_format's label matching (data-model.md §8) so both sides
    agree on what "the same label" means."""
    text = text.strip()
    if text.endswith(":"):
        text = text[:-1].strip()
    return re.sub(r"\s+", " ", text).lower()


def _pad_or_token(value, letter):
    """§3 padding rule: a numeric component written with two digits takes
    the padded token (MM/DD); one digit takes the unpadded token (M/D).
    Padding is a property of how the component is WRITTEN, not its value.
    A value already written in the pattern language (the literal token
    itself, e.g. "MM") passes through unchanged — this is what makes a
    pattern-language line's own tokens reproduce as themselves."""
    if value in (letter, letter * 2):
        return value
    return letter * 2 if len(value) == 2 else letter


def _year_token(value):
    """§3 padding rule applied to the year component: YYYY for four
    written digits (or the literal YYYY token), YY for two written digits
    (or the literal YY token — G2/F4: the year-last shape and both
    named-month shapes accept a written 2-digit year; see
    _YEAR_TRAILING_ALT / _YEAR_2DIGIT_ALT above)."""
    if value in ("YYYY", "YY"):
        return value
    return "YYYY" if len(value) == 4 else "YY"


def _month_name_token(value):
    """Mon for a 3-letter written abbreviation (or the literal "Mon"
    token), Month for a full written name (or the literal "Month" token)."""
    if value in ("Mon", "Month"):
        return value
    return "Mon" if len(value) <= 3 else "Month"


def _date_format_for_line(line):
    """The DateFormat a single line carries, per §3's four shapes tried in
    priority order — or None when the line carries no recognizable date.
    "A line already written in the pattern language is date-bearing and its
    pattern is itself, unambiguous" falls out for free here: the token
    alternatives (YYYY, MM, DD, ...) are accepted anywhere a concrete
    component is, and when matched they pass straight through
    _pad_or_token/_year_token/_month_name_token unchanged.
    """
    match = _ISO_YEAR_FIRST_RE.search(line)
    if match:
        sep = match.group("sep")
        pattern = (
            _year_token(match.group("year")) + sep
            + _pad_or_token(match.group("c1"), "M") + sep
            + _pad_or_token(match.group("c2"), "D")
        )
        return {"pattern": pattern, "ambiguous": False}

    match = _YEAR_LAST_RE.search(line)
    if match:
        c1, c2 = match.group("c1"), match.group("c2")
        year_tok = _year_token(match.group("year"))
        if c1.isdigit() and c2.isdigit():
            v1, v2 = int(c1), int(c2)
            if v1 <= 12 and v2 <= 12:
                # §3.1 step 1 — provisional labelling: first -> MM, second
                # -> DD, in the order the components appear. The flag below
                # is what marks this labelling provisional, not a silent pick.
                c1_tok, c2_tok, ambiguous = _pad_or_token(c1, "M"), _pad_or_token(c2, "D"), True
            elif v1 > 12 and v2 <= 12:
                # A component > 12 can only be a day (months run 1-12) —
                # fixes THIS entry's own order without any cross-entry help.
                c1_tok, c2_tok, ambiguous = _pad_or_token(c1, "D"), _pad_or_token(c2, "M"), False
            elif v2 > 12 and v1 <= 12:
                c1_tok, c2_tok, ambiguous = _pad_or_token(c1, "M"), _pad_or_token(c2, "D"), False
            else:
                # Both > 12 — not a real calendar date. Never raise; fall
                # back to the provisional labelling like the truly-ambiguous
                # case, rather than guessing.
                c1_tok, c2_tok, ambiguous = _pad_or_token(c1, "M"), _pad_or_token(c2, "D"), True
        else:
            # Already written in the pattern language — date-bearing and
            # unambiguous by definition (§3's pattern-language rule).
            c1_tok, c2_tok, ambiguous = c1, c2, False
        pattern = c1_tok + match.group("sep1") + c2_tok + match.group("sep2") + year_tok
        return {"pattern": pattern, "ambiguous": ambiguous}

    # Shape 3, 4-digit year — positionally free, same as every other shape.
    match = _DAY_MONTHNAME_YEAR_4DIGIT_RE.search(line)
    if match:
        pattern = (
            _pad_or_token(match.group("day"), "D") + match.group("sep1")
            + _month_name_token(match.group("month")) + match.group("sep2")
            + _year_token(match.group("year"))
        )
        return {"pattern": pattern, "ambiguous": False}

    # Shape 3, 2-digit year — J1/J2 (round 4): position-gated, not
    # trailing-context-gated. See _named_month_2digit_match.
    match = _named_month_2digit_match(_DAY_MONTHNAME_YEAR_2DIGIT_RE, line)
    if match:
        pattern = (
            _pad_or_token(match.group("day"), "D") + match.group("sep1")
            + _month_name_token(match.group("month")) + match.group("sep2")
            + _year_token(match.group("year"))
        )
        return {"pattern": pattern, "ambiguous": False}

    # Shape 4, 4-digit year — positionally free.
    match = _MONTHNAME_DAY_YEAR_4DIGIT_RE.search(line)
    if match:
        pattern = (
            _month_name_token(match.group("month")) + match.group("sep1")
            + _pad_or_token(match.group("day"), "D") + ","
            + match.group("sep2") + _year_token(match.group("year"))
        )
        return {"pattern": pattern, "ambiguous": False}

    # Shape 4, 2-digit year — same position gate as shape 3 above.
    match = _named_month_2digit_match(_MONTHNAME_DAY_YEAR_2DIGIT_RE, line)
    if match:
        pattern = (
            _month_name_token(match.group("month")) + match.group("sep1")
            + _pad_or_token(match.group("day"), "D") + ","
            + match.group("sep2") + _year_token(match.group("year"))
        )
        return {"pattern": pattern, "ambiguous": False}

    return None


def _first_date_bearing(lines):
    """§3 — "the first date-bearing line (the title line when it carries a
    date, else the first line that does)". A single top-to-bottom scan over
    EVERY line, independent of heading status. Returns
    (line_index, DateFormat), or (None, None) when no line in the entry
    carries a date."""
    for index, line in enumerate(lines):
        date_format = _date_format_for_line(line)
        if date_format is not None:
            return index, date_format
    return None, None


def extract_structure(content):
    """data-model.md §3 — the extracted shape of one diary entry's
    ``content`` -> ``{title, sections, date_format, field_order}``.
    ``at`` is machine ordering metadata (FR-002) and is never consulted —
    assert-worthy enough that this function does not take it as a
    parameter at all."""
    lines = content.splitlines()

    # §3 "Heading recognition" — collect every heading in document order,
    # keeping each one's line index so title-splitting (below) and
    # field_order (below) can locate it again without re-scanning.
    headings = []
    for index, line in enumerate(lines):
        atx_match = _ATX_RE.match(line)
        if atx_match:
            marker_hashes, text = atx_match.group(1), atx_match.group(2).rstrip()
            headings.append((index, {"marker": "atx", "level": len(marker_hashes), "text": text}))
            continue
        bold_match = _BOLD_RE.match(line)
        if bold_match:
            headings.append((index, {"marker": "bold", "level": None, "text": bold_match.group(1)}))

    date_line_index, date_format = _first_date_bearing(lines)

    # §3 "title" — the first heading, ONLY when it sits on the date-bearing
    # line; otherwise title is null and every heading (including that
    # first one) is an ordinary section. Folding a per-entry title into the
    # compared shape would make every real diary "inconsistent" (R4(a)) —
    # this split is why it doesn't.
    if headings and headings[0][0] == date_line_index:
        title = headings[0][1]
        section_headings = headings[1:]
    else:
        title = None
        section_headings = headings

    sections = [heading for _, heading in section_headings]
    heading_text_by_line = dict((index, heading["text"]) for index, heading in section_headings)

    # §3 "field_order" — one top-to-bottom pass over every line, combining
    # both sources (a non-title section heading's text, or a line-initial
    # "Label:" inline field) in document order, first-occurrence-wins. The
    # title line needs no explicit exclusion: it is always a heading line
    # (starts with "#" or "**"), which can never satisfy the
    # letter-anchored inline-field pattern.
    field_order = []
    seen = set()
    for index, line in enumerate(lines):
        if index in heading_text_by_line:
            candidate = heading_text_by_line[index]
        else:
            inline_match = _INLINE_FIELD_RE.match(line)
            candidate = inline_match.group(0)[:-1] if inline_match else None
        if candidate is None:
            continue
        normalized = _normalize_label(candidate)
        if normalized not in seen:
            seen.add(normalized)
            field_order.append(normalized)

    # No headings and no inline fields -> empty lists (never an exception);
    # `sections` and `field_order` above are already `[]` in that case.
    return {
        "title": title,
        "sections": sections,
        "date_format": date_format,
        "field_order": field_order,
    }


# ---------------------------------------------------------------------------
# resolve_date_ambiguity (data-model.md §3.1 step 2)
# ---------------------------------------------------------------------------

# Parses a year-last numeric DateFormat.pattern back into its two
# day/month-shaped components, so resolve_date_ambiguity can read off which
# position an unambiguous entry resolved as the day.
_PATTERN_DAYMONTH_RE = re.compile(
    r"^(?P<c1>MM|M|DD|D)(?P<sep1>[-/])(?P<c2>MM|M|DD|D)(?P<sep2>[-/])(?P<year>YYYY|YY)$"
)
_FLIP_DAY_MONTH_TOKEN = {"MM": "DD", "M": "D", "DD": "MM", "D": "M"}


def _day_month_first_type(pattern):
    """"day" or "month" when `pattern` is a year-last day/month numeric
    pattern (e.g. "DD/MM/YYYY") telling which type occupies the FIRST
    position; None when `pattern` isn't that shape at all (a different
    date shape entirely, e.g. ISO or a named month) or pairs two
    same-typed components (malformed)."""
    match = _PATTERN_DAYMONTH_RE.match(pattern or "")
    if not match:
        return None
    c1, c2 = match.group("c1"), match.group("c2")
    if c1 in ("DD", "D") and c2 in ("MM", "M"):
        return "day"
    if c1 in ("MM", "M") and c2 in ("DD", "D"):
        return "month"
    return None


def _flip_day_month(pattern):
    """Swap the two components' TYPE labels in place, keeping each
    position's own written width (padded/unpadded) and every separator
    untouched — "DD/MM/YYYY" <-> "MM/DD/YYYY", "D-M-YYYY" <-> "M-D-YYYY".

    F6 (review round): guarded against a pattern that isn't this shape at
    all (or is ``None``) — the pattern is returned UNCHANGED rather than
    raising. ``.match(pattern)`` used to be indexed with no None check:
    ``pattern=None`` raised ``TypeError`` before ``.match`` even ran, and a
    non-matching pattern (e.g. an ISO ``"YYYY-MM-DD"`` marked ambiguous by
    a malformed caller) made ``.match(...)`` return ``None``, and
    ``None.group(...)`` raised ``AttributeError``. data-model.md is
    explicit that extraction — and everything downstream of it — never
    raises.

    G7 (round 2): F6's own guard, ``pattern or ""``, only rescues FALSY
    values — ``None`` and ``""`` — leaving a non-string, truthy pattern
    (e.g. ``_flip_day_month(42)``) to reach ``.match(42)`` and raise
    ``TypeError`` anyway, contradicting this docstring's "returned
    UNCHANGED rather than raising" claim. The guard now checks the type
    directly, so anything that isn't a string — ``None``, ``42``, a list —
    is returned unchanged before ``.match`` is ever called.
    """
    if not isinstance(pattern, str):
        return pattern
    match = _PATTERN_DAYMONTH_RE.match(pattern)
    if not match:
        return pattern
    return (
        _FLIP_DAY_MONTH_TOKEN[match.group("c1")] + match.group("sep1")
        + _FLIP_DAY_MONTH_TOKEN[match.group("c2")] + match.group("sep2")
        + match.group("year")
    )


def resolve_date_ambiguity(structures):
    """data-model.md §3.1 step 2 — the pass-level ambiguity resolution.
    Scans every Structure from ONE read: if any carries an unambiguous
    numeric (year-last, day/month-shaped) date, that component ORDER is
    adopted for every structure in the pass and every ``ambiguous`` flag is
    cleared; if none does, the flags stand.

    Runs BEFORE §5's consistency comparison (resolve_format) — a resolved
    and an unresolved entry would otherwise disagree on ``pattern`` and
    trip a spurious ``entries_inconsistent``.

    Adoption REWRITES the provisional pattern when the true order flips it
    (first -> DD, not first -> MM) — merely clearing the flag while leaving
    a "MM/DD/YYYY" pattern standing when the adopted order is day-first is
    the exact defect entries-disambiguating.json exists to catch.

    F5 (review round): a pass can also carry two-plus UNAMBIGUOUS entries
    that disagree with each other (one clearly day-first, another clearly
    month-first) — a genuine formatting conflict, not a missing signal.
    The previous version scanned structures in order and adopted the FIRST
    unambiguous entry's order (via an early ``break``), so read order
    silently picked a winner and no notice fired — exactly the silent pick
    the slice's own posture forbids (data-model.md §3.1's "no silent
    pick"). Every unambiguous entry's vote is collected below instead of
    stopping at the first one; a conflict (more than one distinct order
    voted for) is treated the SAME as "no entry resolves it" — the flags
    stand, and resolve_format's own downstream scan for a surviving
    ``ambiguous: true`` is what surfaces ``date_ambiguous`` either way (no
    new notice kind is introduced; ``NOTICE_KINDS`` stays closed).
    """
    day_first_votes = set()
    for structure in structures:
        date_format = structure.get("date_format") if isinstance(structure, dict) else None
        if not date_format or date_format.get("ambiguous"):
            continue
        first_type = _day_month_first_type(date_format.get("pattern"))
        if first_type is not None:
            day_first_votes.add(first_type == "day")

    if len(day_first_votes) != 1:
        # Either nothing in the pass resolves the order (§3.1 step 2's "if
        # none does" — zero votes) or two-plus entries resolve it to
        # CONFLICTING orders (both True and False present) — both cases
        # decline to guess. The flags stand, untouched.
        return structures

    adopt_day_first = next(iter(day_first_votes))

    resolved = []
    for structure in structures:
        structure = dict(structure) if isinstance(structure, dict) else structure
        date_format = structure.get("date_format") if isinstance(structure, dict) else None
        if isinstance(date_format, dict) and date_format.get("ambiguous"):
            pattern = date_format.get("pattern")
            new_pattern = _flip_day_month(pattern) if adopt_day_first else pattern
            structure["date_format"] = {"pattern": new_pattern, "ambiguous": False}
        resolved.append(structure)
    return resolved


# ---------------------------------------------------------------------------
# resolve_format / apply_format / render_date (data-model.md §4, §5, §8)
# ---------------------------------------------------------------------------


def _structure_triple(structure):
    """§5's compared triple — sections' heading texts in order,
    date_format.pattern, field_order. The title is deliberately absent
    (§3: it differs by construction across every real entry)."""
    return (
        tuple(heading["text"] for heading in structure.get("sections", [])),
        (structure.get("date_format") or {}).get("pattern"),
        tuple(structure.get("field_order", [])),
    )


def resolve_format(template, entries):
    """data-model.md §4 — the format-resolution decision, in order ->
    ``{"source", "structure", "template", "notices"}``."""
    # Step 1/2 — template presence and well-formedness. `None` is ABSENT:
    # rule 1 simply does not apply, nothing is surfaced. A configured value
    # that is not a string, or is empty/whitespace-only, is MALFORMED (R3)
    # and falls through to steps 3/4 after surfacing the notice.
    if template is not None:
        if isinstance(template, str) and template.strip() != "":
            # US1 AS-1 — a real early return: `entries` is never touched on
            # this path, not even a truthiness/length check, so a template
            # configured with no recent-entry read available still resolves.
            return {"source": "template", "structure": None, "template": template, "notices": []}
        notices = [
            {
                "kind": "template_malformed",
                "detail": "configured template is not a non-blank string (got {})".format(
                    type(template).__name__
                ),
            }
        ]
    else:
        notices = []

    # Step 4 — no entries at all: offer the minimal default as a template
    # candidate rather than blocking the draft.
    if not entries:
        notices.append(
            {
                "kind": "template_candidate",
                "detail": "no recent entries to match; offering the minimal default as a template candidate",
            }
        )
        return {"source": "default", "structure": MINIMAL_DEFAULT, "template": None, "notices": notices}

    # Step 3 — entries available: extract every entry's structure, run the
    # pass-level ambiguity resolution (§3.1) BEFORE comparing, then compare.
    structures = [extract_structure(entry["content"]) for entry in entries]
    structures = resolve_date_ambiguity(structures)

    if any(
        isinstance(structure.get("date_format"), dict) and structure["date_format"].get("ambiguous")
        for structure in structures
    ):
        notices.append(
            {
                "kind": "date_ambiguous",
                "detail": "no entry in this read carries an unambiguous numeric date; day/month order was not resolved",
            }
        )

    # §5 — entries[0] is the newest (read_recent is most-recent-first), so
    # it is both "the common structure" when every entry agrees and "the
    # newest entry's structure" when they don't; either way it is the result.
    newest_triple = _structure_triple(structures[0])
    all_consistent = all(_structure_triple(structure) == newest_triple for structure in structures[1:])
    if not all_consistent:
        notices.append(
            {
                "kind": "entries_inconsistent",
                "detail": "entries read do not share sections/date_format/field_order; the newest entry's structure wins",
            }
        )

    return {"source": "matched", "structure": structures[0], "template": None, "notices": notices}


def _modal_marker_level(sections):
    """The most-common (marker, level) pair among `sections` — level 2
    (atx) when `sections` is empty, per data-model.md §8. Ties keep
    whichever pair occurred first; no `sorted`/`max` needed."""
    if not sections:
        return "atx", 2
    counts = {}
    order = []
    for heading in sections:
        key = (heading.get("marker"), heading.get("level"))
        if key not in counts:
            counts[key] = 0
            order.append(key)
        counts[key] += 1
    best = order[0]
    for key in order[1:]:
        if counts[key] > counts[best]:
            best = key
    return best


def _render_heading(marker, level, text):
    """One heading line in its own marker/level — the inverse of the
    _ATX_RE / _BOLD_RE recognition in extract_structure."""
    if marker == "bold":
        return "**{}**".format(text)
    return "{} {}".format("#" * (level or 1), text)


def apply_format(structure, sections):
    """data-model.md §8 — mechanical arrangement only: places
    already-authored section blocks into `structure`'s headings and order.
    `sections` is an ordered list of ``[label, block]`` pairs; blocks are
    opaque strings IN, byte-identical strings OUT — this function never
    authors, rewords, summarizes or re-labels. Date rendering (the title
    line) is deliberately NOT here; see render_date."""
    structure = structure or {}
    field_order = list(structure.get("field_order") or [])
    struct_sections = structure.get("sections") or []

    # normalized heading text -> its own Heading (marker/level/text),
    # first occurrence wins — mirrors extract_structure's own field_order
    # construction so the two sides agree on "the same label".
    heading_by_label = {}
    for heading in struct_sections:
        key = _normalize_label(heading.get("text", ""))
        if key not in heading_by_label:
            heading_by_label[key] = heading

    # normalized input label -> (original label, block), first occurrence
    # wins; `order_of_input` preserves the caller's own ordering for the
    # no-content-dropped append pass below.
    section_by_label = {}
    order_of_input = []
    for label, block in sections:
        key = _normalize_label(label)
        if key not in section_by_label:
            section_by_label[key] = (label, block)
            order_of_input.append(key)

    modal_marker, modal_level = _modal_marker_level(struct_sections)

    used = set()
    pieces = []
    # Sections are emitted in `field_order` order, matched by normalized
    # label; a field_order label with no matching section is OMITTED (no
    # empty headings).
    for label in field_order:
        if label in used or label not in section_by_label:
            continue
        used.add(label)
        _, block = section_by_label[label]
        heading = heading_by_label.get(label)
        if heading is not None:
            # F8 (review round): `.get(...)`, not `[...]` — a heading dict
            # omitting "level" (e.g. a hand-built Structure a caller passes
            # in) raised KeyError here while every sibling read in this
            # module (_modal_marker_level, extract_structure) already
            # tolerates a missing key via `.get`.
            marker, level, text = heading.get("marker"), heading.get("level"), heading.get("text")
        else:
            # A field_order label with no matching heading (an inline-field
            # -only label): render it at the modal level using the
            # section's own authored label as its heading text, since there
            # is no heading to copy marker/level/text from.
            marker, level, text = modal_marker, modal_level, section_by_label[label][0]
        pieces.append(_render_heading(marker, level, text) + "\n" + block + "\n\n")

    # A section with no matching field_order label is APPENDED after the
    # structured ones, in the caller's own input order, at the modal level
    # — so no content is ever dropped.
    for key in order_of_input:
        if key in used:
            continue
        label, block = section_by_label[key]
        pieces.append(_render_heading(modal_marker, modal_level, label) + "\n" + block + "\n\n")

    return "".join(pieces)


def write_entry(invoke, content):
    """data-model.md §1's write flow, encoded as a callable so the linkage
    assertion in ``tests/contract/test_diary_write.py`` has a SUBJECT: without
    this function, "the returned link is what the row receives" would compare
    a value to itself, with no artifact in between that could hold the
    transform the assertion claims to catch.

    This encodes the documented flow, not a shipped adapter — nothing here
    ships (Constitution I; FR-008). At runtime there is no `write_entry`
    function: an agent invokes the diary capability's `append_entry`
    operation directly, guided by `skills/diary/SKILL.md`'s prose.

    ``invoke`` is the same three-arg callable ``bb_mock_mcp.MockMcp.invoke``
    exposes (``invoke(capability, op, payload)``); this function is the only
    place in this module that calls it, and it calls exactly one operation.

    Realizes the skill-level `write_entry(content) -> url` onto the contract
    (data-model.md §1's table): calls `diary.append_entry`, and on success
    returns the contract's `link` AS `url` — the one-line transform the
    linkage assertion exists to catch a regression in. On failure, the
    uniform error envelope (`{"op", "code", "message"}`) passes through
    UNCHANGED under `"error"` — never swallowed, never reshaped, never
    retried (retry policy belongs to the close flow, not here).

    F7 (review round): the failure check is `result.get("error") is not
    None`, not `"error" in result` — key PRESENCE is not the same question
    as whether an error actually happened. A result shaped
    `{"link": ..., "error": None}` (error explicitly nulled to signal
    success, rather than the key being omitted) used to satisfy
    `"error" in result` and fall into the failure branch, returning
    `{"url": None, "error": None}` — failure-shaped, with no error to show
    for it.

    G6 (round 2): the success path read `result["link"]` directly while the
    failure path just above it already used `.get("error")` — an `invoke`
    returning `{}` (no error key, no link key) passed the failure check
    (`{}.get("error") is not None` is `False`) and then raised `KeyError` on
    `result["link"]`, the exact "an unswallowed exception where a graceful
    envelope was expected" class F7's own fix exists to rule out. Both
    lookups now use `.get`.
    """
    result = invoke("diary", "append_entry", {"content": content})
    if result.get("error") is not None:
        return {"url": None, "error": result["error"]}
    return {"url": result.get("link"), "error": None}


def consume_recent(entries):
    """data-model.md §2 / SKILL.md "Interface" — makes "consumed as-is" an
    executable claim rather than a prose one: `read_recent` already returns
    entries most-recent-first (the contract's own ordering guarantee,
    gated by slice 1's `tests/contract/test_diary.py`), so consuming them
    is a matter of reading position 0 and passing the rest through
    UNTOUCHED — never a re-sort, never a re-derivation of "freshest" by any
    other means (e.g. comparing `at` values).

    THIS FUNCTION MUST NEVER GROW A SORT. `tests/contract/test_diary_ordering.py`
    source-scans this function's body (and `extract_structure`'s and
    `resolve_format`'s) for reordering calls — the sort method, the sorted
    builtin, or a reverse-order builtin — and fails the build if any appear
    (deliberately not spelled out literally in this docstring, since the
    scan reads this function's own source text) — the ban is on the
    ENCODING reordering what the contract already ordered, not on test
    setup constructing diary state.
    """
    return {"freshest": entries[0] if entries else None, "considered": entries}


# F1 (BLOCKING, review round) — alternation in `re` is first-match-wins, not
# longest-match-wins, so the token order is load-bearing: every token that
# is a PREFIX of another must be listed after it, or the longer token can
# never win. "YY" is a prefix of "YYYY"; "M" is a prefix of "MM", "Month"
# and "Mon"; "D" is a prefix of "DD"; "Mon" is a prefix of "Month". The
# previous order (YYYY|YY|MM|M|DD|D|Month|Mon) put "M" and "D" ahead of
# "Month"/"Mon"/"DD", so `render_date` corrupted every named-month pattern
# — "DD Mon YYYY" rendered as "21 7on 2026" ("M" ate the first letter of
# "Mon" before "Mon" ever got a chance to match). Longest-first order below
# fixes every token unconditionally, not just the ones a fixture happened
# to exercise.
_DATE_TOKEN_RE = re.compile(r"YYYY|Month|Mon|YY|MM|DD|M|D")


def _coerce_date(date):
    """Accepts anything exposing .year/.month/.day (e.g. datetime.date), a
    (year, month, day) sequence, or an ISO "YYYY-MM-DD" string -> (year,
    month, day) ints. Never guesses silently past that: an unrecognized
    shape raises rather than rendering a wrong date."""
    if hasattr(date, "year") and hasattr(date, "month") and hasattr(date, "day"):
        return date.year, date.month, date.day
    if isinstance(date, (list, tuple)) and len(date) == 3:
        return int(date[0]), int(date[1]), int(date[2])
    if isinstance(date, str):
        parts = date.split("-")
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
    raise ValueError("render_date: unrecognized date value {!r}".format(date))


def render_date(date_format, date):
    """data-model.md §8 — deliberately SEPARATE from both the resolution
    path (resolve_format) and apply_format: the title line's date is the
    caller's to render, not something either of those two computes."""
    pattern = (date_format or {}).get("pattern") or ""
    year, month, day = _coerce_date(date)

    def _replace(match):
        token = match.group(0)
        if token == "YYYY":
            return "{:04d}".format(year)
        if token == "YY":
            return "{:02d}".format(year % 100)
        if token == "MM":
            return "{:02d}".format(month)
        if token == "M":
            return str(month)
        if token == "DD":
            return "{:02d}".format(day)
        if token == "D":
            return str(day)
        if token == "Month":
            return _MONTH_FULL[month - 1]
        return _MONTH_ABBR[month - 1]  # "Mon"

    return _DATE_TOKEN_RE.sub(_replace, pattern)
