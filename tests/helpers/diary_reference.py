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
# Phase-2 module — see T006). Two reasons, both recorded here because a
# later author will be tempted to "fix" this into a derivation:
#
# 1. The skeleton's title line contains the LITERAL TOKENS "YYYY-MM-DD"
#    rather than an actual date. extract_structure looks for a date-bearing
#    line to build date_format from; the token string is not one, so
#    extraction would find none and yield date_format: None — contradicting
#    the value declared below. The text is a template FOR humans to fill in
#    a date; it is not itself a dated line.
# 2. Deriving this constant at import time would make this Phase-2 module
#    (T004/T005 — module + constants only) depend on extract_structure, a
#    Phase-3 function (T006) — a circular dependency the phase split forbids.
#
# T023 gates the two constants' agreement instead, at test time rather than
# import time: it asserts extract_structure(MINIMAL_DEFAULT_TEXT)'s
# `sections` and `field_order` equal MINIMAL_DEFAULT's, with `date_format`
# compared separately for the reason above (data-model.md §6 "Two names,
# deliberately").
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
# order per line so a line only ever yields one reading. Concrete years are
# matched only as 4 written digits (never a bare 2-digit number) — the
# worked cases never need a concrete 2-digit year, and requiring 4 digits
# keeps the year-first shape from ever mistaking a numeric day/month
# component (e.g. the "09" in "09/08/2026") for a year.
_MONTH_FULL = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
_MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

_YEAR_ALT = r"\d{4}|YYYY|YY"
_MONTHNUM_ALT = r"\d{1,2}|MM|M"
_DAYNUM_ALT = r"\d{1,2}|DD|D"
_DAYMONTHNUM_ALT = r"\d{1,2}|MM|M|DD|D"
_MONTHNAME_ALT = r"(?:" + "|".join(_MONTH_FULL + _MONTH_ABBR + ("Month", "Mon")) + r")\b"

# Shape 1 — year-first numeric (ISO-shaped): "2026-07-21", or the
# pattern-language line "YYYY-MM-DD" itself (MINIMAL_DEFAULT_TEXT's title).
# The leading year anchors month-then-day order by convention, so this
# shape is never ambiguous — §3.1 only concerns the year-LAST shape below.
_ISO_YEAR_FIRST_RE = re.compile(
    r"(?P<year>{year})(?P<sep>[-/])(?P<c1>{mnum})(?P=sep)(?P<c2>{dnum})".format(
        year=_YEAR_ALT, mnum=_MONTHNUM_ALT, dnum=_DAYNUM_ALT
    )
)
# Shape 2 — year-last, two bare numeric components: "07/21/2026". This is
# the shape §3.1's ambiguity pass concerns — see _date_format_for_line.
_YEAR_LAST_RE = re.compile(
    r"(?P<c1>{dm})(?P<sep1>[-/])(?P<c2>{dm})(?P<sep2>[-/])(?P<year>{year})".format(
        dm=_DAYMONTHNUM_ALT, year=_YEAR_ALT
    )
)
# Shape 3 — "21 Jul 2026" / "21 Month 2026": day, named month, year.
_DAY_MONTHNAME_YEAR_RE = re.compile(
    r"(?P<day>{dnum})(?P<sep1>\s+)(?P<month>{mname})(?P<sep2>\s+)(?P<year>{year})".format(
        dnum=_DAYNUM_ALT, mname=_MONTHNAME_ALT, year=_YEAR_ALT
    )
)
# Shape 4 — "July 4, 2026": named month, day, comma, year.
_MONTHNAME_DAY_YEAR_RE = re.compile(
    r"(?P<month>{mname})(?P<sep1>\s+)(?P<day>{dnum}),(?P<sep2>\s*)(?P<year>{year})".format(
        mname=_MONTHNAME_ALT, dnum=_DAYNUM_ALT, year=_YEAR_ALT
    )
)


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
    written digits, YY for a literal YY token (never a bare 2-digit
    number — see the shape-regex comment above)."""
    if value in ("YYYY", "YY"):
        return value
    return "YYYY"


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

    match = _DAY_MONTHNAME_YEAR_RE.search(line)
    if match:
        pattern = (
            _pad_or_token(match.group("day"), "D") + match.group("sep1")
            + _month_name_token(match.group("month")) + match.group("sep2")
            + _year_token(match.group("year"))
        )
        return {"pattern": pattern, "ambiguous": False}

    match = _MONTHNAME_DAY_YEAR_RE.search(line)
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
    untouched — "DD/MM/YYYY" <-> "MM/DD/YYYY", "D-M-YYYY" <-> "M-D-YYYY"."""
    match = _PATTERN_DAYMONTH_RE.match(pattern)
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
    """
    adopt_day_first = None
    for structure in structures:
        date_format = structure.get("date_format") if isinstance(structure, dict) else None
        if not date_format or date_format.get("ambiguous"):
            continue
        first_type = _day_month_first_type(date_format.get("pattern"))
        if first_type is not None:
            adopt_day_first = first_type == "day"
            break

    if adopt_day_first is None:
        # No unambiguous numeric date anywhere in the pass — §3.1 step 2's
        # "if none does": the flags stand, untouched.
        return structures

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
            marker, level, text = heading["marker"], heading["level"], heading["text"]
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
    """
    result = invoke("diary", "append_entry", {"content": content})
    if "error" in result:
        return {"url": None, "error": result["error"]}
    return {"url": result["link"], "error": None}


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


_DATE_TOKEN_RE = re.compile(r"YYYY|YY|MM|M|DD|D|Month|Mon")


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
