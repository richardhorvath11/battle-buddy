# Fixture diary entry sets

Shared entry sets for slice 8 (diary adapter — `specs/008-diary-adapter/`). They exist so
the diary skill's documented format-resolution rules can be exercised by hermetic tests via
a dev-only reference encoding (`tests/helpers/diary_reference.py`), instead of asserted on
prose alone (Constitution VIII).

## Format decision (data-model.md §10)

Each file is plain JSON — no YAML, no new dependency — parsed with stdlib `json`:

```
{"description": str, "entries": [{"link", "content", "at"}, ...]}
```

`entries` is **newest-first** — the shape `read_recent(n)` returns, so a fixture is consumed
exactly as the contract delivers it and no test ever has to reorder one. `at` is ISO-8601 and
**strictly decreasing** down the list; it exists only to make the newest-first claim checkable
and is **never read by extraction** (FR-002) — `extract_structure` does not take `at` as a
parameter at all. `content` is the sole extraction surface: each entry carries its own H1 (or
bold-title) line with that entry's own date and incident name, followed by its section
headings and body prose.

`entries-labeled-causal.json` additionally carries a top-level `"sections"` key: an ordered
list of `[label, block]` **pairs** (a JSON list of two-element lists, not an object — order is
carried by the data, never by dict-insertion luck), matching what `apply_format` consumes
(data-model.md §8).

## Layout

```
tests/fixtures/diary/
  README.md                        # this file
  entries-consistent.json
  entries-bold.json
  entries-inconsistent.json
  entries-ambiguous-date.json
  entries-disambiguating.json
  entries-short.json
  entries-empty.json
  entries-labeled-causal.json
```

Two further fixtures — `golden-structures.json` and `resolution-matrix.json` — are added by a
later task (T010) and are not described here; they carry expected *outputs* for the entry sets
above rather than diary state, so "what would this discriminate if swapped for
`entries-consistent.json`" does not apply to them the way it does below.

## Fixture roster — what each one discriminates

The test for a fixture pulling its weight: which assertion would still pass if that fixture
were replaced by `entries-consistent.json`? If the answer is "all of them", it isn't pulling
its weight. `entries-consistent.json` is the baseline every other fixture is diffed against.

| Fixture | Discriminates |
|---|---|
| `entries-consistent.json` | The baseline matched-structure path: 5 entries with differing per-entry titles (date + incident name, excluded from the compared triple per data-model §3) but the **same four `##` section headings in the same order** and ISO dates throughout. Every other fixture below is a controlled deviation from this one. |
| `entries-bold.json` | The `bold` heading marker (`marker="bold"`, `level=None`). Its title and section labels are whole-line `**text**` form with no ATX heading markers anywhere in any entry's content. Swapping it for `entries-consistent.json` would make the `bold`-marker recognition assertion vacuous — `entries-consistent.json` has no bold headings. |
| `entries-inconsistent.json` | Freshest-wins plus the `entries_inconsistent` notice. The four older entries share one `##` section order; the **newest** entry uses a different order and different labels (`Impact`/`Timeline`/`Mitigation`/`Next steps` vs. `What happened`/`Timeline`/`Resolution`/`Follow-ups`). Swapping it for `entries-consistent.json` would make the drift-detection assertion pass on an already-consistent set, proving nothing. |
| `entries-ambiguous-date.json` | The `date_ambiguous` notice and "no silent pick". Every title date is `MM/DD/YYYY`-shaped with **both** numeric components ≤ 12 in **every** entry, so §3.1's pass-level scan cannot fix the day/month order. `entries-consistent.json` uses unambiguous `YYYY-MM-DD` dates, so swapping would leave the ambiguity path untested. |
| `entries-disambiguating.json` | §3.1's pass-level ambiguity **resolution**. Same ambiguous-date style as `entries-ambiguous-date.json`, except the **third-newest** entry is dated `17/06/2026` (component > 12, placed **first** so the adopted order differs from the provisional first-seen labelling — see "Notes on specific fixtures" below), which fixes the component order for the whole read and clears every `ambiguous` flag. Section headings match the rest of the set, so the *only* cross-entry difference is the one the ambiguity pass resolves. Swapping it for either `entries-consistent.json` or `entries-ambiguous-date.json` would lose the "one unambiguous entry rescues the whole pass" property. |
| `entries-short.json` | Consuming fewer than `n` entries. Exactly 2 entries, otherwise shaped like `entries-consistent.json` (same section order, ISO dates). Swapping it for `entries-consistent.json` (5 entries) would make a "fewer entries than requested" read indistinguishable from the ordinary case. |
| `entries-empty.json` | The empty-diary default path: `"entries": []` drives `source="default"`, `structure=MINIMAL_DEFAULT`, and the `template_candidate` notice. No other fixture here is empty. |
| `entries-labeled-causal.json` | `apply_format`'s label pass-through and no-content-dropped properties (FR-005). Its two entries' headings carry the close flow's causal proposal labels verbatim (`Root cause (proposal)`, `Contributing factors (proposals)`, `Action items (proposals)`); its top-level `sections` list is the `[label, block]` input `apply_format` arranges. `Contributing factors (proposals)` carries punctuation in its label *and* a block whose text ends in trailing spaces (byte-preservation is a real assertion, not a trivially-satisfied one); `Timeline` is a block whose label matches **no** heading in either entry, exercising the "no content is ever dropped" append rule. None of this exists in `entries-consistent.json`, which carries no `sections` key and no causal labels. |

## Notes on specific fixtures

**`entries-labeled-causal.json`'s `sections` list** exercises `apply_format`'s
"a section with no matching label is **appended** after the structured ones"
rule — its `Timeline` block matches no heading in either seed entry. It does
**not**, on its own, exercise the mirror rule that "a `field_order` label
with no matching section is **omitted**." T011 covers that omit half by
pairing this fixture's `sections` list against `entries-consistent.json`'s
**resolved** structure instead: that structure's `field_order` has no
`Root cause (proposal)` / `Contributing factors (proposals)` / `Action items
(proposals)` labels, so matching against it drops those three sections from
`apply_format`'s output while `What happened`, `Timeline`, `Resolution` and
`Follow-ups` still emit — the omit rule's positive case.

**Date sequences chosen for the ambiguous-date fixtures (Fix 1 of the Phase
1 review round).** `entries-ambiguous-date.json` and
`entries-disambiguating.json` both use the title-date sequence `09/08`,
`08/07`, `07/06` (`17/06` in the disambiguating file only), `06/05`, `05/04`
(all `/2026`), chosen specifically because it is **strictly decreasing under
both the MM/DD and the DD/MM reading** — a set whose titles contradict
`at`'s newest-first order under either interpretation would not be diary
data any reviewer could cross-check. In `entries-disambiguating.json`, the
third-newest entry's `17/06/2026` puts the `>12` component **first**:
data-model §3.1 step 1's provisional per-entry labelling is already
first→`MM`, second→`DD`, so a disambiguator in the *second* slot would adopt
an order byte-identical to that provisional guess, and a broken
implementation that never inspects the unambiguous entry — and merely
clears every `ambiguous` flag — would produce the same result as a correct
one. Putting the `>12` component first instead forces the adopted order to
differ from the provisional one, so order **adoption** (not just flag
clearing) is what the fixture makes observable.

## Mock-seeding rule

A mock-seeded test converts a fixture to diary state by iterating `reversed(entries)` and
calling `diary.append_entry(entry["content"])` for each — oldest first, so the mock's own
newest-first read returns them in the fixture's original order. The mock mints its own
`link` and `at` on each append; the fixture is never written into the mock verbatim. This
keeps the fixture the single source of truth and means no test hand-writes seed data.

**State the consequence explicitly, because it is the trap**: entries read back from the mock
therefore never `==` the fixture's entries (their `link`/`at` differ from whatever the fixture
file happens to carry). An ordering or content assertion must compare on content alone —
`[e["content"] for e in returned]` against the fixture's `content` order — never on the full
entry dict.
