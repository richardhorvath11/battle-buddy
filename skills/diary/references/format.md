# Diary Entry Format Reference

Normative for the `diary` skill (FR-002; data-model.md §3, §3.1, §4, §5, §6, §8, §9). The
decision that turns a close-time draft into entry content shaped like the team's own diary —
when a configured template wins outright, when the diary's recent entries are read and matched
instead, and what "matched" means at the level of headings, dates, and field order. Follow the
decision in the stated order; it is a sequence, not a menu of equal options.

## The resolution decision (normative)

1. **A configured template wins outright.** When the team has configured a template, it is
   used as-is, and **no recent-entry read is needed for formatting** — the decision is made
   without reading a single entry. A configured template is never second-guessed against what
   the diary's recent entries look like.
2. **A malformed template falls back to match-recent, with the problem surfaced.** A template
   that is present but malformed does not block the draft; resolution proceeds exactly as if no
   template were configured, and the malformed-template problem is surfaced alongside the draft
   (never silently dropped).
3. **Entries present → match them.** With no usable template, the diary's recent entries are
   read and the draft's structure matches what they show — headings, date format, field order.
4. **No entries → the minimal default.** An empty diary with no template uses the minimal
   default structure below, offered to the team as a template candidate.

## Read depth

Recent-entry reads go **5 entries deep by default**, overridable by the additive workspace
config key `battleBuddy.diary.recentEntries` (an integer ≥ 1). Reading more than one entry is
what makes drift between entries observable at all — a depth-1 read would always agree with
itself, so freshest-wins (below) would never have anything to detect.

## Absent versus malformed

These are two different states, and only one of them is surfaced:

| State | Condition | Surfaced? |
|---|---|---|
| **Absent** | the template key is missing, or its value is `null` | No — this is the ordinary, unconfigured case |
| **Malformed** | the key is present with a value that is not a string, or is a string that is empty or whitespace-only | Yes — this is a defect worth telling the team about |

A template's value being **present** is what makes it eligible to be malformed. A template
that is absent never reaches the malformed check at all — rule 1 above simply does not apply,
and nothing about it is surfaced.

**A template with no headings is not malformed.** A flat, heading-free entry style is a
legitimate team convention, not a defect. Only the two conditions in the table above make a
template malformed; the shape of a well-formed template's content is never second-guessed.

## Structure extraction

Extraction runs over an entry's `content` and yields exactly four parts, together called a
`Structure`:

| Part | Contents |
|---|---|
| `title` | the first heading, when it is the date-bearing line |
| `sections` | every other heading, in document order |
| `date_format` | the pattern built from the first date-bearing line, plus an ambiguity flag |
| `field_order` | the normalized, first-occurrence-wins list of section and inline-field labels |

`content` is the **extraction surface** — structure comes from `content` and nothing else. `at`
is machine ordering metadata; it is never read by extraction and is never the team's date
format, no matter how it happens to be formatted in the store.

### Heading recognition

Exactly two shapes count as a heading:

| marker | Line shape | `level` |
|---|---|---|
| `atx` | `#{1,6} <text>` | the count of `#` characters (1–6) |
| `bold` | the **whole** line is `**<text>**` | `null` |

A line that merely *contains* bold text partway through is not a heading; the anchored,
whole-line match is the rule, not a loose "has bold in it somewhere" reading.

### Why the entry title is excluded from the compared shape

A diary entry's title line carries that entry's own date and its own incident name, so it
differs across every entry by construction — that is what real diary titles look like. Folding
the title into the compared shape would make every real diary classify as "inconsistent"
regardless of how uniform the team's actual formatting is, which defeats the point of comparing
at all. The title's *shape* is still captured — through `date_format` and through the title
heading's own marker and level — it is simply not compared by its literal text, and it is not a
member of `field_order`.

### Date-format tokens

The date format is derived from the first date-bearing line (the title line, when it carries a
date; otherwise the first line that does) by replacing recognized components with tokens and
keeping every other character literal:

| Token | Matches |
|---|---|
| `YYYY` / `YY` | 4-digit / 2-digit year |
| `MM` / `M` | numeric month, padded / unpadded |
| `DD` / `D` | numeric day, padded / unpadded |
| `Mon` / `Month` | abbreviated / full month name |

Worked examples:

| Written as | `date_format.pattern` |
|---|---|
| `2026-07-21` | `YYYY-MM-DD` |
| `21 Jul 2026` | `DD Mon YYYY` |
| `July 4, 2026` | `Month D, YYYY` |
| `07/21/2026` | `MM/DD/YYYY` |

**Padding rule.** A numeric component written with two digits takes the padded token (`MM`,
`DD`); a component written with one digit takes the unpadded token (`M`, `D`). Padding is a
property of **how the component is written**, not of its value — `07` and `21` are both
two-digit and both take the padded token, while `4` takes the unpadded one even though it is a
perfectly ordinary day-of-month value. Without this rule, padding would be unobservable for any
component ten or above, and two readers of the same entry could disagree on its pattern.

### Field-order normalization

`field_order` is the ordered, first-occurrence-wins list of normalized labels drawn from two
sources, in document order:

- every `sections` heading's text;
- every line-initial inline field of the shape `Label:`.

Normalization: lowercase, trailing `:` stripped, internal whitespace collapsed. Duplicates keep
their first occurrence. The `title` is excluded, for the same reason it is excluded from
`sections` above.

**The inline-label rule has two halves: a label starts with an ASCII letter, and its colon is
not preceded by a digit.** Both are load-bearing, not tidiness. A timeline line carrying a
clock time has exactly the shape a line-initial `Label:` field would have, but the clock time
varies entry to entry by construction, the same way an entry title does. Admitting it would
make an otherwise perfectly uniform diary classify as inconsistent purely because its timeline
entries carry different times.

The leading-letter half alone is **not enough**, and it is worth saying why rather than leaving
a later reader to rediscover it: a line reading `At 14:12 the alert fired` starts with a letter,
so the letter anchor admits it and yields the label `at 14`. It is the digit rule that actually
excludes it. Real labels never end in a digit before their colon, so the two halves together
exclude times without excluding anything a team would write.

An entry with no headings and no inline fields yields empty `sections` and `field_order` lists,
plus whatever `date_format` was found — a legal, empty-shaped structure, never an error.

## Extraction is bounded

Extraction reads an entry only for its title, its headings, its date rendering, and its field
order, and yields only those four parts. A very long entry costs the matching step nothing
extra beyond finding those signals — no entry **body** (the prose under a heading, a timeline's
narrative lines, evidence text) is ever carried into the extracted structure, into the drafted
entry, or into any store. Matching observes shape; it never retains content.

## Consistency and freshest-wins

Each entry read is extracted into its own `Structure` (after the ambiguity pass below has run).
The structures are then compared on the triple **(`sections`' heading texts in order,
`date_format.pattern`, `field_order`)** — the title is not part of this comparison, per above:

- **All equal** → that structure is the resolved structure.
- **Any difference** → the **most recent** entry's structure is the resolved structure, and
  the drift is surfaced.

Freshest-wins is what makes reading more than one entry meaningful: with freshest-wins as the
tie-break, a single-entry read would always "agree with itself," so the additional entries
exist specifically to detect and report drift, not to average across styles.

## Numeric date ambiguity

A date written as two numeric components where both are ≤ 12 cannot have its day/month order
read from that single entry — `03/04` could be either. Resolving this is a **pass-level**
question, scanned across every entry read in that pass, not a per-entry guess:

- If **any** entry in the pass carries an unambiguous numeric date (a component greater than
  12, which fixes the order), that order is adopted for every entry in the pass.
- If **no** entry in the pass resolves it, the ambiguity is **surfaced for the responder to
  confirm** — it is never picked silently. A silent pick on an ambiguous date is exactly the
  failure mode a responder has no way to catch after the fact, so the flow declines to guess.

This pass-level resolution runs before the consistency comparison above, so a date that gets
resolved and one that does not are never compared against each other as if they disagreed.

## The minimal default

With no template and no entries, the draft uses this skeleton, verbatim:

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

It is offered to the team as a template candidate. The three causal sections carry their
proposal labels in the heading text itself, so the labels survive any transform that preserves
heading text. **The `Evidence` section carries the in-session evidence links as gathered — a
URL plus a short excerpt for each — and never a prose summary**, the same evidentiary standard
every factual claim and hypothesis in this harness is held to.

## Notice kinds

Format resolution surfaces exactly four kinds of notice, never more, never fewer:

| kind | Surfaced when |
|---|---|
| `template_malformed` | rule 2 above fired — a configured template was not usable |
| `entries_inconsistent` | the comparison above found drift and freshest-wins decided it |
| `date_ambiguous` | the pass-level ambiguity resolution above could not fix the order |
| `template_candidate` | rule 4 above fired — the minimal default is offered as a template |

Notices are surfaced, never fatal: emitting one is this document's rule; presenting it to the
responder is the close flow's to execute.

## Ordering consumption

`read_recent` returns entries **most recent first**. This document's consumption rule has two
halves, and both are load-bearing:

- **Consumer-side**: entries arrive most recent first and are used **as-is** — consumers never
  re-sort them. The freshness ordering that drives freshest-wins and the ambiguity pass above
  is the order the read already delivers.
- **Adapter-side**: an adapter sitting over a store that is natively oldest-first **reverses on
  read**, so that its consumers never have to. The ordering commitment is the adapter's to keep,
  not something every consumer re-derives for itself.

## Row fields are not inputs

Session-row fields are not inputs to any part of format resolution — not the decision, not
extraction, not the ambiguity pass, not the consistency comparison. Format resolution takes
entry content and format state only; it never reads a session-row field, and its outcome never
depends on one.
