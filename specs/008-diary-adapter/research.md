# Research: Diary Adapter (slice 8)

Plan-time pins for `specs/008-diary-adapter/spec.md`. Every item the spec's Assumptions
section deferred "to plan time" is resolved here, plus the mechanism choices the tests
need. Format follows slice 7's: **Decision / Rationale / Alternatives rejected**.

---

## R1 — Skill location and file layout

**Decision.** `skills/diary/SKILL.md` plus one reference, `skills/diary/references/format.md`.
`SKILL.md` carries the adapter interface (the two operations, the error posture), the write
flow, the drafting handoff and its input contract, and the non-goals. `references/format.md`
carries the format-resolution decision rule, the structure-extraction rules, the pinned
defaults (minimal default structure, freshest-wins, malformed-template fallback), and the
ordering-consumption rule.

**Rationale.** Design §3.1's bundle tree shows a bare `skills/diary/SKILL.md`; slice 7 hit
exactly this and expanded `catalog/` to `SKILL.md` + `references/` following the
`session-store/` and `investigation/` siblings shown directly above it in that same tree.
The same expansion applies for the same reason: the extraction rules are a normative rule
table that would swamp the skill's actual subject (a two-operation interface). One
reference, not two — the interface is genuinely small, and splitting a two-op contract
across files buys nothing.

**Alternatives rejected.** (a) Single flat `SKILL.md` — the extraction rules alone are
longer than the rest of the skill, and burying them makes the interface unreadable.
(b) Two references (`interface.md` + `format.md`) — the interface is four lines of contract
plus an error sentence; a reference file for it is ceremony.

---

## R2 — Read depth `n`

**Decision.** `n` defaults to **5**, overridable by an additive workspace-config key
`battleBuddy.diary.recentEntries` (integer ≥ 1). The skill documents the default and the
knob; nothing in this slice reads config (no code ships) — the key is the documented name
the close flow passes through.

**Rationale.** Spec Assumptions: "the ~5 read depth follows §6.2's 'last ~5 entries'; the
exact n is a configuration default pinned at plan time (the design's tilde invites a config
knob, not a hard constant)." The `battleBuddy.diary.*` block already exists (`/setup` writes
`diary` as `{url}` — `commands/setup.md`) and slice 5 already added `template` to it as an
additive key (`commands/close.md`), so `recentEntries` is a sibling in an established block,
not a new config surface. Operation contract v1 pins `n ≥ 1`, which the default satisfies.

**Alternatives rejected.** (a) Hard constant 5 — contradicts the spec's own reading of the
tilde. (b) A knob with no default — every team would have to configure a value that has an
obvious right answer.

---

## R3 — Template location, shape, and what "malformed" means

**Decision.** The template lives at **`battleBuddy.diary.template`** — the key slice 5
already pinned in `commands/close.md` ("an additive workspace-config key"). This slice
**consumes** that pin and does not restate it as its own invention. The value is the entry
**skeleton text** (a single string).

A template is **malformed** in exactly two cases: the key is present but the value is not a
string, or the value is empty/whitespace-only. Everything else is a usable template.

**Rationale.** Consuming the sibling pin is what keeps one source of truth for a config key
two slices touch. Keeping "malformed" to two mechanical cases makes the fallback rule
testable without a template grammar this slice has no mandate to invent — and it deliberately
does **not** treat "a template with no headings" as malformed, because a flat entry is a
legitimate team style, not a defect. The fallback itself (match-recent, with the problem
surfaced) is the spec's informed default from the repo's fail-soft posture.

**Alternatives rejected.** (a) Template as a pointer to a diary-adjacent document — adds a
read the format-resolution path would have to make before it can decide, and there is no
operation in the diary capability's closed op-set to fetch it. (b) A structured template
(JSON with named slots) — a schema for team prose is exactly the imposition FR-4c exists to
avoid. (c) Treating "no headings" as malformed — punishes a legitimate style.

---

## R4 — Structure extraction: what is extracted and how

**Decision.** Extraction runs over an entry's `content` (never `at` — the contract's `at` is
machine ordering metadata, FR-002) and yields four parts: `title`, `sections`, `date_format`,
`field_order`. The full shapes and recognition rules are in data-model.md §3; the three
decisions worth recording here are the ones that were otherwise undecidable.

**(a) The title is split out of the compared shape.** A diary entry's title carries that
entry's own date and incident name, so it differs across every entry by construction. Had the
comparison included it, *every* real diary would classify as inconsistent, the freshest-wins
fixture would be undiscriminating, and the "consistent" fixture's expected empty notice set
would be unsatisfiable. The title's shape is still captured, through `date_format` and the
title heading's marker/level; it is simply not compared by literal text and is not a member of
`field_order`.

**(b) Padding is a property of how a component is written, not of its value.** A numeric
component written with two digits takes `MM`/`DD`; one digit takes `M`/`D`. Without this rule
padding is unobservable for any component >= 10, and two implementers produce different
patterns for the same fixture (`21 Jul 2026` is `DD Mon YYYY`, not `D Mon YYYY`).

**(c) Ambiguity is a pass-level property, resolved in two explicit steps.** A single-entry
function cannot answer a cross-entry question, so `extract_structure` sets `ambiguous` with a
provisional first-is-month labelling per entry, and `resolve_date_ambiguity` scans the whole
pass: any entry with a component > 12 fixes the order for all of them and clears the flags; if
none does, the flags stand and `date_ambiguous` surfaces. The pass-level step runs **before**
the consistency comparison, so a resolved and an unresolved entry never disagree on `pattern`
and trip a spurious `entries_inconsistent`.

**Rationale.** These parts are precisely what §6.2 and FR-002 name ("headings, date format,
field order"), and each is rule-shaped — the reference encoding's home turf per the spec's
testing-model assumption. `bold` headings are recognized because a document-backed diary
rendered to text routinely loses `#` markers while keeping bold section labels; refusing to
see them would make extraction fail on the most common real diary. The provisional labelling
plus the flag is what keeps goldens writable *without* a silent pick — the D-22 posture
("a silent pick is the failure mode a responder cannot detect") applied to a second surface.

**Alternatives rejected.** (a) Falling back to `at` for the date format — FR-002 forbids it in
as many words. (b) Defaulting ambiguous numeric dates to month-first unflagged — a silent,
locale-biased pick. (c) Comparing whole heading lists including titles — makes every fixture
inconsistent; this was a real defect in the first draft of this plan, caught in artifact
converge. (d) Extracting prose style (tone, length, person) — not rule-shaped; scenario-harness
territory, which the spec's testing model puts out of CI scope.

---

## R5 — Consistency detection and freshest-wins

**Decision.** Structure is extracted from **each** of the entries read; the pass-level
ambiguity resolution of R4(c) runs; then the structures are compared on the triple
(**sections'** heading text sequence, `date_format` pattern, `field_order`) — the title is not
in it, per R4(a). All equal → that is the observed structure. Any difference → the **most
recent entry's** structure is the result
(`freshest_wins`), and `inconsistent: true` is recorded and surfaced.

**Rationale.** This is what makes reading ~5 entries meaningful rather than decorative: with
freshest-wins as the pinned tie-break, a depth-1 read would give the same answer, so the
extra four entries exist to *detect and report* drift. The spec pins freshest-wins
(Assumptions) but the detection half is what makes it observable.

**Alternatives rejected.** (a) Majority vote across entries — undermines the spec's pinned
freshest-wins. (b) Extract from entry[0] only — cheaper, but then "inconsistent recent
entries" is an edge case the flow can never notice, and the spec asks for it explicitly.

---

## R6 — The empty-diary minimal default structure

**Decision.** With no template and no entries, the draft uses this skeleton, and it is
offered to the team as a template candidate (the offering interaction is the close flow's to
execute — FR-002):

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

Date format `YYYY-MM-DD`; ATX headings; the three causal sections carry their proposal
labels in the section names themselves. The `Evidence` section carries the in-session evidence
links **as gathered** — `{url, excerpt}` pairs per Constitution IV, never a prose summary. That
sentence belongs in the shipped prose because this skeleton is the one artifact shape this
slice authors, and a bare "Evidence" heading otherwise invites prose-only evidence.

**Rationale.** "A date-titled entry with the standard close-report sections" is the spec's
pin; this makes it concrete and therefore testable as a golden. The section list is *informed
by* `commands/close.md`'s draft anatomy — its factual fields, its timeline, its resolution and
its three explicitly-labeled causal sections — so the default does not invent a report shape
that disagrees with the flow that fills it. It is not a transcription of that list: `What
happened` and `Evidence` are this slice's additions, since an entry needs a narrative opening
and a home for the in-session evidence links. Carrying "(proposal)" in the heading text
means the label survives even a format transform that only preserves heading text
(Constitution V; FR-005).

**Alternatives rejected.** (a) An empty/one-heading default — nothing for the team to adopt
as a template. (b) Reusing the FR-4d report template — that is a different artifact with a
different audience.

---

## R7 — "Format matching" as a mechanical arrangement, and the label pass-through property

**Decision.** The reference encoding exposes `apply_format(structure, sections)` — it
**arranges already-authored section blocks** into the resolved structure (heading markers,
date rendering, section order). It never authors, rewords, summarizes, or re-labels a block;
blocks are opaque strings in and byte-identical strings out. FR-005's label pass-through is
tested as exactly that property: a fixture block carrying causal proposal labels is
byte-preserved through `apply_format`.

**Rationale.** This draws the CI/scenario-harness boundary the spec's testing model demands
in a way a test can enforce. Arrangement is rule-shaped and gateable; authoring is not.
Stating it as an opacity property is also the strongest possible form of "format resolution
never strips or rewords labeled fields" (FR-005, Constitution V) — it holds for *every*
block, not just the ones a fixture happens to test.

**Alternatives rejected.** (a) An encoding that drafts entry prose — that is agent behavior;
CI asserting on it would be asserting on prose quality, which FR-007 explicitly excludes.
(b) Testing label survival by string-searching the output for known labels — weaker: it
passes a transform that mangles everything except the searched labels.

---

## R8 — FR-003 instrumented as an input-signature property

**Decision.** The encoding declares `FORMAT_INPUT_KEYS` — the complete set of inputs
format resolution consumes (`template`, `entries`, and per-entry `content`). The test parses
the session-row field names **dynamically** out of
`skills/session-store/references/schema.md`'s column table and asserts that set is disjoint
from `FORMAT_INPUT_KEYS` **and** from `resolve_format`'s signature parameters.

**Rationale.** The spec words FR-003's in-slice instrument precisely: "row fields appear
nowhere in the format-resolution decision inputs (the reference encoding takes entry content
and format state only)". Sourcing the row's field names from slice 3's normative schema doc
rather than a test-local copy means the property tightens automatically if slice 3 adds a
column — the same "never a hand-maintained list" discipline slice 7 used for the annotation
vocabulary. End-to-end row independence remains a consumed slice-5 property, not this
slice's to prove.

**Alternatives rejected.** (a) Scanning the encoding's whole source for row field names —
noisy to the point of uselessness (`links`, `timeline`, `resolution` are ordinary English).
(b) Hardcoding the row field list in the test — a second source of truth for slice 3's schema.

---

## R9 — Ordering: how "no re-sort" is gated

**Decision.** Three mechanisms, because no single one is honest on its own:

1. **Contract** — against `bb-mock-mcp`, `read_recent(n)` returns newest-first (the mock
   reverses on read, `tools/bb-mock-mcp/bb_mock_mcp/stores.py`), and the encoding's
   consumption treats `entries[0]` as freshest.
2. **Encoding source scan** — the consumption functions contain no `sorted(`, `.sort(`, or
   `reversed(`. If the encoding never reorders, the documented flow it encodes doesn't either.
3. **Prose** — a positive gate that `references/format.md` states the consumer-side
   commitment ("consumers never re-sort"), and a negative scan for consumer-side re-sort
   directives. The negative scan is masked to permit the one legitimate mention: the sentence
   stating that *adapters over oldest-first stores* reverse on read — an adapter-side
   statement of the commitment, not a consumer-side instruction.

**Rationale.** SC-005 asks for "zero re-sort steps" in a *documented flow* plus fixture-
confirmed newest-first arrival. A prose scan alone is gameable by rewording; a contract test
alone says nothing about what the prose tells an agent to do. The encoding scan is the bridge.

**Alternatives rejected.** (a) Prose scan only — the weakest of the three and the easiest to
satisfy vacuously. (b) An unmasked "no reverse/sort words anywhere" scan — would fail the doc
for stating the very commitment it must state.

---

## R10 — SC-006 naming scan mechanism

**Decision.** `tests/contract/test_diary_prose.py` imports `DENY_PATTERNS` from
`tests/contract/test_skill_capability_naming.py` (slice-7 precedent — a public, reused
mechanism, never a copy), scans every `skills/diary/**/*.md` via `rglob`, and adds:
the `mcp__` literal hard fail (raw text, fenced or not); an operation-fidelity check that
every backtick-quoted op-shaped token is a real operation in
`tools/bb-mock-mcp/contract.json`; and a positive control proving the scan can fail.

The existing deny-list already carries `docs mcp` and `google docs`, which is exactly what
this slice's prose must never say — see R11.

**Rationale.** One scan mechanism for the whole repo means a pattern added for any slice
protects every slice. The positive control is what distinguishes "the scan passes" from
"the scan is broken".

**Alternatives rejected.** A slice-local deny-list copy — guarantees divergence.

---

## R11 — The concrete-store abstraction, and the design-doc amendment

**Decision.** The skill says "the team's configured diary, through the diary capability" and
never names the document product or its MCP. `bb-technical-design.md` gains a §6.2
clarification (the abstracted destination framing, the `skills/diary/` layout expansion, and
the two config keys) plus decision-log row **D-23** recording this slice's pins.

**Rationale.** §6.2's MVP heading names a concrete product; Constitution VII supersedes it
for *shipped prose*, and the spec's Assumptions already declare this deliberate. The design
doc is the architectural record and may keep naming the MVP binding — it is not scanned and
not shipped — but it should say plainly that the skill abstracts it, so a later reader does
not "fix" the skill back toward the concrete name. Recording hard-to-reverse pins in §11 is
the repo's Development Workflow rule; slice 7 set the precedent with D-22.

**Alternatives rejected.** (a) Amending §6.2 to delete the concrete MVP binding — loses the
recommended-roster information that has real value and zero architectural privilege.
(b) No amendment — leaves five pins (read depth, template key, malformed definition,
ambiguity surfacing, freshest-wins detection) recorded only in a slice spec.

---

## R12 — Test module layout

**Decision.**

| Path | Covers |
|---|---|
| `tests/helpers/diary_reference.py` | dev-only reference encoding: `extract_structure`, `resolve_format`, `apply_format`, `consume_recent`, `MINIMAL_DEFAULT`, `FORMAT_INPUT_KEYS` |
| `tests/fixtures/diary/` | entry-set fixtures + `golden-structures.json` + `resolution-matrix.json` |
| `tests/contract/test_diary_format.py` | US1: resolution matrix, extraction goldens, freshest-wins, minimal default, label pass-through (R7), FR-003 input signature (R8) |
| `tests/contract/test_diary_write.py` | US2: write flow against the mock — link returned, link is what the row receives, write log shows exactly one diary append |
| `tests/contract/test_diary_ordering.py` | US3: newest-first end-to-end, short/empty reads, the encoding's no-reorder scan |
| `tests/contract/test_diary_prose.py` | naming scan, op fidelity, ordering-prose gates, packaging ratchet, FR-008 boundary gates |

Contract layer only; nothing in `tests/unit/`. Stdlib only (`json`, `re`, `inspect`,
`pathlib`).

**Rationale.** Mirrors slice 7's module-per-user-story shape with a prose module for the
cross-cutting gates. `tests/unit/` runs at the py3.9 shipped-code floor and `tests/conftest.py`
states the layer rule — the unit layer "proves future shipped code, which must not depend on
dev tooling" — and the reference encoding *is* dev tooling.

**Alternatives rejected.** One big `test_diary.py` — loses the story-to-module traceability
`quickstart.md` depends on, and makes a scope cut messy.

---

## R13 — Cross-slice surfaces this slice touches but does not own

| Surface | Owner | This slice's relationship |
|---|---|---|
| `commands/close.md` drafting + dual-write | slice 5 | **Consumed.** The template key, the read-recent fallback, and the causal-label rule are already stated there; the diary skill must agree with it and must not restate the close flow |
| `skills/session-store/` diary step, `diary_url`, `diary_pending` | slice 3 | **Consumed.** Write ordering and diary-failure handling live there; this slice's non-goals say so |
| `manifest/capabilities.json` + `tools/bb-mock-mcp/contract.json` diary ops | slices 4 / 1 | **Consumed** as the operation authority; the op-fidelity and closed-op-set checks read the contract file |
| `tests/contract/test_diary.py` | slice 1 | **Consumed, not duplicated.** It already gates append→link, newest-first, short/empty reads, `n` validation, and the error envelope; this slice's modules add the *consumption* layer and cite it rather than re-asserting it |
| `tests/contract/test_catalog_prose.py`'s `SCANNED_SKILL_DIRS` | slice 7 | **Updated** — creating `skills/diary/` makes that guard fire by design ("a skill added without one is silently exempt"); `"diary"` is added in the same task that lands the naming scan, so the listing is truthful rather than a rubber stamp |
| `AGENTS.md` shipped-surface list | repo doc | **Updated** — `skills/diary` added to the landed-surfaces line |

An earlier draft of this research claimed "no sibling-slice file needs retagging". That was
wrong on two counts — the `SCANNED_SKILL_DIRS` guard above, and the deferrals in R14 — and is
corrected here rather than left as an optimistic summary.

---

## R14 — Recorded deferrals (things this slice pins but does not wire up)

Three consequences of this slice's pins have **no landed consumer**, and saying so is the
honest alternative to implying they take effect (Constitution II; the repo's
"scope-vs-correctness tradeoffs are surfaced explicitly, never silently shipped" rule).

**1. `battleBuddy.diary.recentEntries` has no reader.** Slice 5's close-flow encoding
hardcodes the depth (`tests/helpers/lifecycle_flows.py`, `draft_close` →
`read_recent` with `n` fixed at 5). This slice documents the default and the override key —
the diary skill's prose *is* the spec the close flow will implement against — but wiring the
key into the close flow's call is a slice-5 change and is deliberately not made here. Recorded
in D-23 and the PR body. The default is 5, so behavior today is identical either way; only a
team that sets the key would notice, and no team can set it yet.

**2. The notice vocabulary has no consumer.** FR-002 assigns the *surfacing* interaction to the
close flow, and `commands/close.md` currently has no notion of receiving notices. This slice
defines and emits the four kinds; where they land in the close-flow UI is slice 5's to add.

**3. Slice 5's `_render_draft_entry` placeholder.** `tests/helpers/lifecycle_flows.py` carries
an explicit slice-8 IOU — "slice 8 owns the real format-matching logic; no established shipped
format exists yet to imitate" — and renders a stand-in line. Now that this slice has landed the
rules, that placeholder could cite them. Replacing slice 5's rendering with a real format-match
is a behavior change to a landed, gated helper and is out of this slice's scope; the citation
update is folded into T024 so the IOU points at something real instead of at nothing.

None of the three blocks any FR or SC of this slice. All three are the kind of thing a reader
of the plan would otherwise assume had been handled.
