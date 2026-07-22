# Data Model: Diary Adapter (slice 8)

The shapes this slice pins. Nothing here is a runtime type — no code ships (FR-008). These
are (a) the shapes the skill's prose is normative about and (b) the shapes
`tests/helpers/diary_reference.py` produces, so tests can assert on artifacts rather than
prose (Constitution VIII).

Contract-owned shapes (`Entry`, the op envelopes) are **cited, never redefined**: the
operation contract at `tools/bb-mock-mcp/contract.json` and its shipped projection
`manifest/capabilities.json` are the authority, and slice 1's `tests/contract/test_diary.py`
is where their raw behavior is already gated.

---

## 1. Adapter interface (FR-001)

The skill-level contract — the diary's entire surface to the rest of the system:

```
read_recent(n) -> entries[]        # most recent first; n defaults to 5 (R2)
write_entry(content) -> url        # the dual-write's first write
```

**Realization onto operation contract v1** (the bridge the spec pins):

| Skill-level name | Contract operation | Notes |
|---|---|---|
| `read_recent(n)` | `diary.read_recent(n) -> {entries}` | same name; `n` integer ≥ 1 |
| `write_entry(content)` | `diary.append_entry(content) -> {link}` | `url` ≡ the contract's `link` |

Failures surface the contract's uniform error envelope
(`{"error": {"op", "code", "message"}}`) to the close flow unchanged. The adapter attempts
and reports; **retry policy belongs to the close flow** (slice 5 / slice 3's
`diary_pending`), not here.

The op-set is **closed**: append and read, exactly two. That closure is what makes "never
creates diaries" a pin derived from the contract rather than an aspiration (spec
Assumptions), and it is asserted as an **equality** against the contract file — a subset
assertion would go quiet in exactly the case that matters, a future `create_diary` op.

---

## 2. `Entry` (contract-owned)

```
Entry { link, content, at }
```

Defined by operation contract v1. Two consumption rules this slice is normative about:

- **`content` is the extraction surface.** Structure comes from `content` and nothing else.
- **`at` is machine ordering metadata, never the team's date format** (FR-002). It is not
  read by extraction at all — `extract_structure` does not take it as a parameter.

`read_recent(n)` returns **most recent first** (design §6.2 v1.2.1). Short reads and empty
reads are already gated by slice 1's conformance suite (`tests/contract/test_diary.py`);
what this slice adds is how those results are **consumed**.

---

## 3. `Structure` — the extracted shape of an entry (FR-002, R4)

```
Structure {
  title:       Heading | null,   # the first heading, when it is the date-bearing line
  sections:    [Heading],        # every other heading, in document order
  date_format: DateFormat | null,
  field_order: [str],            # normalized section labels, first-occurrence-wins
}

Heading   { marker: "atx" | "bold", level: int | null, text: str }
DateFormat { pattern: str, ambiguous: bool }
```

**Why `title` is split out.** A diary entry's title line carries that entry's own date and
incident name, so it differs across every entry by construction. Folding it into the compared
shape would make every real diary "inconsistent" (§5) and make the freshest-wins fixture
undiscriminating. The title's *shape* is still captured — through `date_format` and the
title `Heading`'s marker/level — it is just not compared by its literal text, and it is **not**
a member of `field_order`.

**Heading recognition** — exactly two shapes:

| marker | Line shape | `level` |
|---|---|---|
| `atx` | `#{1,6} <text>` | count of `#` (1–6) |
| `bold` | the **whole** line is `**<text>**` | `null` |

A line that merely *contains* bold is not a heading; the anchored match is the rule.

**`date_format.pattern`** is built from the first date-bearing line (the title line when it
carries a date, else the first line that does), by replacing recognized components with
tokens and keeping every other character literal:

| Token | Matches |
|---|---|
| `YYYY` / `YY` | 4-digit / 2-digit year |
| `MM` / `M` | numeric month, padded / unpadded |
| `DD` / `D` | numeric day, padded / unpadded |
| `Mon` / `Month` | abbreviated / full month name |

**Padding rule (pinned, because it is otherwise undecidable).** A numeric component is
`MM`/`DD` when it is written with two digits, and `M`/`D` when written with one. Padding is
a property of *how the component is written*, not of its value — so `07` and `21` are both
two-digit and both take the padded token, while `4` takes the unpadded one.

Worked cases: `2026-07-21` → `YYYY-MM-DD`; `21 Jul 2026` → `DD Mon YYYY`;
`July 4, 2026` → `Month D, YYYY`; `07/21/2026` → `MM/DD/YYYY`.

**A line already written in the pattern language is date-bearing, and its pattern is itself**
(unambiguous). A run of these tokens with literal separators — `YYYY-MM-DD` — reads as the
pattern `YYYY-MM-DD`. This exists because a *template* renders its date slot in the pattern
language rather than as a date, and `MINIMAL_DEFAULT_TEXT` is exactly such a template: without
this rule its title line is not date-bearing, `title` is `null`, all eight headings fall into
`sections`, and §6's declared structure is unreachable. A real entry containing the literal
string `YYYY-MM-DD` is a template line by any reading, so the rule costs nothing.

**`field_order`** normalization: lowercase, trailing `:` stripped, internal whitespace
collapsed. Sources, in document order: every `sections` heading's `text`, plus every
line-initial `Label:` inline field, where a label must start with an ASCII letter **and its
colon must not be preceded by a digit** (`^[A-Za-z][^:\n]{0,39}(?<!\d):`). Both halves are
load-bearing, not tidiness: a clock time is the one thing that looks like a label while varying
per entry, and admitting it would make an otherwise-uniform diary classify as inconsistent. The
letter anchor alone is **not sufficient** — `At 14:12 the alert fired` starts with a letter and
yields the label `at 14`. The digit lookbehind is what actually excludes it. (Found during
implementation: the letter-anchor-only rule an earlier draft pinned would have broken the
baseline fixture.) Duplicates keep their first occurrence. The `title` is
excluded.

An entry with no headings and no inline fields yields empty lists and whatever `date_format`
was found — a legal empty-shaped structure, never an exception.

### 3.1 Date ambiguity is a *pass*-level property

A two-numeric-component date whose components are both ≤ 12 cannot have its day/month order
read from that entry alone. So ambiguity resolves in two steps, and the split is explicit
because a single-entry function cannot answer a cross-entry question:

1. **Per entry** — `extract_structure` sets `date_format.ambiguous = true` provisionally, and
   records the pattern with the components labelled **in the order they appear**
   (first → `MM`, second → `DD`). The labelling is provisional; the flag says so.
2. **Per pass** — `resolve_date_ambiguity(structures)` scans every structure from this read.
   If **any** carries an unambiguous numeric date (a component > 12 fixes the order), that
   order is adopted for all of them and every `ambiguous` flag is cleared. If none does, the
   flags stand and `date_ambiguous` is emitted so the responder confirms it.

The pass-level resolution runs **before** §5's comparison, so a resolved and an unresolved
entry never disagree on `pattern` and trip a spurious `entries_inconsistent`.

No silent pick: the provisional labelling is recorded so goldens are writable, and the flag
plus the notice are what stop it from being trusted (the D-22 posture applied to a second
surface).

---

## 4. `FormatResolution` — the decision (FR-002, US1)

```
FormatResolution {
  source:    "template" | "matched" | "default",
  structure: Structure | null,   # null when source == "template"
  template:  str | null,         # the skeleton, when source == "template"
  notices:   [Notice],
}

Notice { kind, detail }
```

**Decision rule**, in order:

1. **Template present and well-formed** → `source: "template"`. **No recent-entry read is
   needed for formatting** (US1 AS-1) — the template wins outright, and the function returns
   before touching `entries` at all.
2. **Template present but malformed** — value not a string, or empty/whitespace-only (R3) →
   fall through to (3), emitting `template_malformed`. A broken template never blocks the
   draft.

   *Absent vs malformed*: the key being absent, or its value being null, means **no template
   configured** — rule 1 simply does not apply and nothing is surfaced. A *configured* value
   that is not a string, or is blank, is **malformed** and surfaces. The distinction matters
   because one is the ordinary case and the other is a defect worth telling the team about.
3. **Entries available** → `source: "matched"`, `structure` per §5.
4. **No entries** → `source: "default"`, `structure` = `MINIMAL_DEFAULT` (§6), emitting
   `template_candidate`.

**Notice vocabulary** — closed, and asserted both ways against the prose:

| kind | Emitted when |
|---|---|
| `template_malformed` | rule 2 fired; carries what was wrong |
| `entries_inconsistent` | §5's comparison found drift; freshest won |
| `date_ambiguous` | §3.1's pass-level resolution could not fix the order |
| `template_candidate` | rule 4 fired; the minimal default is offered to the team |

Notices are **surfaced**, never fatal. Emitting them is this slice's; *executing* the
surfacing interaction is the close flow's (FR-002) — and see R14 on the fact that no landed
consumer reads them yet.

---

## 5. Consistency and freshest-wins (R5)

After §3.1's pass-level ambiguity resolution, each structure is compared on the triple
`(sections' heading texts in order, date_format.pattern, field_order)` — note the title is
not in it, per §3:

- **All equal** → that structure is the result.
- **Any difference** → the **most recent** entry's structure is the result, and
  `entries_inconsistent` is emitted.

The comparison is why the read depth is > 1: freshest-wins alone would be satisfied by a
depth-1 read, so the extra entries exist to make drift *observable*.

---

## 6. The empty-diary minimal default (R6)

`MINIMAL_DEFAULT_TEXT` — the skeleton, verbatim:

```
# YYYY-MM-DD — <services>: <short title>

## What happened
## Timeline
## Resolution
## Root cause (proposal)
## Contributing factors (proposals)
## Action items (proposals)
## Evidence
```

`MINIMAL_DEFAULT` — its `Structure`: one `atx` level-1 `title`, **seven** `atx` level-2
`sections`, `date_format` `{pattern: "YYYY-MM-DD", ambiguous: false}`, and the seven
corresponding `field_order` labels.

**Two names, deliberately** — but for one reason only, and it is not the one an earlier draft
gave. `extract_structure(MINIMAL_DEFAULT_TEXT)` *does* reproduce `MINIMAL_DEFAULT` exactly,
including `date_format`, thanks to §3's pattern-language rule. They are still two hand-written
constants because deriving one from the other **at import time** would make this Phase-2
module depend on a Phase-3 function — a circular dependency. The agreement is gated instead:
T023 asserts `extract_structure(MINIMAL_DEFAULT_TEXT)` equals `MINIMAL_DEFAULT` **in full**,
every part including `title` and `date_format`. That is a strictly stronger gate than the
partial comparison an earlier draft settled for, and it is available precisely because the
skeleton is written in the pattern language.

The three causal sections carry their proposal labels **in the heading text itself**, so the
labels survive any transform that preserves heading text (Constitution V). The `Evidence`
section carries the in-session evidence links **as gathered** — `{url, excerpt}` pairs per
Constitution IV, never a prose summary.

---

## 7. `DraftInputs` — the drafting handoff (FR-005)

What the close flow supplies to drafting. Every item is a **computed close-time value
available before any write**:

| Input | Notes |
|---|---|
| in-session evidence links | dashboards, searches, PRs — the links gathered during the session |
| services, severity | factual |
| resolution | factual |
| labeled causal proposals | root cause, contributing factors, action items — carrying the close flow's proposal labels |
| locally staged artifact content (pre-upload) | including the **tool trace** and **checkpoint history** |

**Not an input:** the **close-time row update**. Drafting precedes the dual-write, so the row
state the close writes does not exist when the draft is assembled; the diary skill reads no
session-row field and writes none.

**On the timeline — stated precisely, because the two landed accounts differ.** The diary
skill **never derives the structured timeline**. Where an entry carries a timeline section it
is rendered from the same staged sources the row's `timeline` field derives from — the tool
trace and the checkpoint history. This slice deliberately does **not** assert *when* that
derivation happens: design §4 places it at close step 4 (after the diary write) while
`commands/close.md` produces it before the dual-write. Nothing here depends on which, because
the sources are staged either way — and asserting either ordering would put a second source
of truth on a rule slice 5 owns (see R14).

**Output** is entry content in the resolved format. Causal proposal labels pass through
format matching **verbatim** — the adapter never strips, rewords, or promotes them.

---

## 8. `apply_format(structure, sections) -> content` (R7)

Mechanical arrangement only: it places already-authored section blocks into the resolved
structure — heading markers and levels, and section order. Blocks are **opaque strings in,
byte-identical strings out**. It never authors, rewords, summarizes, or re-labels.

`sections` is an **ordered list of `[label, block]` pairs** (a list, not a map, so order is
carried by the data rather than by dict insertion luck). Emission rules:

- Sections are emitted in `structure.field_order` order, matched by normalized label.
- A label in `field_order` with no matching section is **omitted** — no empty headings.
- A section with no matching label is **appended after** the structured ones, at the modal
  level of `structure.sections` (level 2 when `sections` is empty), so **no content is ever
  dropped**.

Date rendering is **not** here: the title line's date is the caller's to render via
`render_date(date_format, date)`, which is deliberately outside the resolution path.

This opacity **is** FR-005's label pass-through property, stated in its strongest form: it
holds for every block, not only for the ones a fixture happens to carry labels in.

---

## 9. `FORMAT_INPUT_KEYS` — the FR-003 instrument (R8)

The complete declared input set of format resolution:

```
FORMAT_INPUT_KEYS = {"template", "entries", "content"}
```

FR-003 is instrumented as the property that this set — and `resolve_format`'s signature
parameters — are **disjoint from the session row's field names**, parsed dynamically from
`skills/session-store/references/schema.md`'s column table.

**Stated honestly** (Constitution II): this is a *weak* gate. The two vocabularies are
disjoint by ordinary English, not by construction, so no plausible edit makes it fire; its
real value is the non-vacuity half — it proves the row-field parser works and that the
declared input set is what the prose says. It is recorded as an accepted-weak instrument
rather than presented as strong instrumentation. End-to-end row independence remains a
**consumed** slice-5 property, not this slice's to prove.

---

## 10. Fixture roster (`tests/fixtures/diary/`)

Each entry-set file is `{"description": str, "entries": [Entry]}`, entries **newest-first**
(the shape `read_recent` returns) with `at` strictly decreasing.

| Fixture | Shape | Exercises |
|---|---|---|
| `entries-consistent.json` | 5 entries; per-entry titles, identical section headings and order, ISO dates | matched structure; the happy path |
| `entries-bold.json` | 5 entries using bold-only section labels | the `bold` heading marker |
| `entries-inconsistent.json` | 5 entries whose **newest** differs in the compared triple | freshest-wins + `entries_inconsistent` |
| `entries-ambiguous-date.json` | 5 entries, every date `03/04/2026`-shaped, both components ≤ 12 throughout | `date_ambiguous`, no silent pick |
| `entries-disambiguating.json` | same style; the **third-newest** entry carries a component > 12 | §3.1's pass-level resolution |
| `entries-short.json` | 2 entries | fewer-than-`n` consumption |
| `entries-empty.json` | `[]` | `MINIMAL_DEFAULT` + `template_candidate` |
| `entries-labeled-causal.json` | 1+ entries with proposal-labeled sections, **plus a `sections` key** (the `[label, block]` pairs `apply_format` consumes) | label pass-through, byte-preserved |
| `golden-structures.json` | fixture name → **list of `Structure`, one per entry, in fixture order** | SC-003 |
| `resolution-matrix.json` | `(template state, entry set) -> expected source + exact notice set + expected resolved structure` | SC-002 |

`golden-structures.json` is per-entry because extraction is per-entry; the *resolved* (pass-
level) structure is an expectation of `resolution-matrix.json` instead, which is where the
consistency comparison and ambiguity resolution have already run.

Template states covered by the matrix: absent (`null`), well-formed string, non-string as a
number, non-string as an object, empty string, whitespace-only.

---

## 11. What this model deliberately does not contain

- **Row shapes.** `diary_url` / `diary_pending` are slice 3's schema; cited, never restated.
- **Write ordering and diary-failure handling.** Slice 3 / slice 5 (§4 close steps).
- **The drafting *interaction*** — presenting, approving, editing. Slice 5's close flow.
- **The raw contract behavior of the two diary ops** — slice 1's `tests/contract/test_diary.py`
  already gates append→link, newest-first, short/empty reads, `n` validation, and the error
  envelope. This slice consumes those, and adds only the consumption layer.
- **Untrusted-telemetry delimiting inside drafts.** Slice 6.
- **Any concrete document product or MCP server.** Constitution VII; spec Assumptions.
