# Implementation Plan: Diary Adapter

**Branch**: `008-diary-adapter` | **Date**: 2026-07-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-diary-adapter/spec.md`

## Summary

Ship the team-diary surface as prose plus hermetic tests (design §6.2 including the v1.2.1
ordering commitment, §4 close steps 1–2, §2's division of knowledge): `skills/diary/SKILL.md`
plus `references/format.md`, pinning the two-operation adapter interface
(`read_recent(n) → entries[]` newest-first, `write_entry(content) → url`) and its realization
onto operation contract v1 (`write_entry ≡ append_entry`, `url ≡ link`, uniform error
envelope surfaced to the close flow); the format-resolution decision (configured template
wins, else match the last ~5 entries) with the structure-extraction rules for headings, date
format, and field order; and the five plan-time pins the spec deferred — read depth 5 behind
`battleBuddy.diary.recentEntries`, the template at slice-5's `battleBuddy.diary.template` with
a two-case malformed definition, the concrete minimal-default skeleton, ambiguity surfaced
rather than silently picked, and consistency detection as what makes freshest-wins observable.

The CI instrument is a **dev-only, test-side reference encoding**
(`tests/helpers/diary_reference.py`) of those documented rules run over fixture entry sets
(`tests/fixtures/diary/`) — the same doc↔executable relationship slice 7 pinned between
`skills/catalog/` and `tests/helpers/catalog_reference.py`, and slice 3 before it between
`fingerprint.md` and `bb-fingerprint`, except that nothing here ships (FR-008,
Constitution I): at runtime the "formatter" is an agent reading entries through the diary
capability. Four contract-test modules gate the resolution matrix and extraction goldens, the
entry→link→row linkage against `bb-mock-mcp`, the ordering consumption with its no-re-sort
scans, and the prose's capability-naming/packaging/boundary discipline.

Three cross-slice touches land in the same change (research R13): `bb-technical-design.md`
gains a §6.2 clarification plus decision-log row **D-23** recording this slice's pins;
`"diary"` is registered in slice 7's `SCANNED_SKILL_DIRS` guard, which creating `skills/diary/`
makes fire **by design** ("a skill added without one is silently exempt") — in the same task
that lands the naming scan, so the listing is truthful rather than a rubber stamp; and slice 5's
`_render_draft_entry` slice-8 IOU comment is repointed at the now-landed rules (a citation
change only). Three consequences of this slice's pins have no landed consumer and are recorded
as explicit deferrals rather than implied to be wired up (research R14).

## Technical Context

**Language/Version**: shipped deliverables are markdown (`skills/diary/SKILL.md` + one
reference — design §3.1's plugin layout). Test code is Python 3 on the slice-1 pytest
harness, **stdlib only** (`json`, `re`, `inspect`, `pathlib`) — dev-only, and deliberately
dependency-free so the contract layer's CI step (`pip install pytest`) needs no edit.

**Primary Dependencies**: none at runtime — no runtime code ships. pytest dev-only. The
slice consumes, and never restates: `tools/bb-mock-mcp/contract.json` (slice 1) and its
shipped projection `manifest/capabilities.json` (slice 4) as the diary-operation authority;
`skills/session-store/` (slice 3) as the normative home of `diary_url` / `diary_pending`,
the dual-write ordering, and the row schema the FR-003 property parses; `commands/close.md`
(slice 5) as the owner of the drafting interaction, causal labeling, retry policy, and the
already-pinned `battleBuddy.diary.template` key; and
`tests/contract/test_skill_capability_naming.py`'s public `DENY_PATTERNS` as the SC-006 scan
mechanism.

**Storage**: none. This slice performs **zero** store I/O by design — that is FR-003's
whole point, and the input-signature property is what instruments it. The diary itself is
the team's readable artifact, reached only through the diary capability's two operations;
the link the write returns is the only value that crosses toward the session row, and
slice 5 is what writes it there.

**Testing**: contract layer only (`tests/contract/`) — the resolution matrix, structure-
extraction goldens, freshest-wins, pass-level ambiguity resolution and its surfacing, the
minimal default, bounded extraction, label pass-through as a byte-preservation property, the
FR-003 input-signature property, the write flow / closed-op-set equality / write-log count
against `bb-mock-mcp`, ordering consumption with short and empty reads, and the prose gates
(naming scan with its local singular-product pattern, operation fidelity with its skill-level
mask, the ordering statement and its masked negative scan, prose↔encoding agreement, packaging
ratchet, FR-004/FR-005 prose, non-goals). Slice 1's `tests/contract/test_diary.py` already
gates the two diary operations' **raw contract** behavior — append→link, newest-first, short
and empty reads, `n` validation, the error envelope — so this slice cites it and adds only the
consumption layer on top rather than re-asserting it. Nothing lands in `tests/unit/`: that layer runs at the py3.9 shipped-code floor
and `tests/conftest.py` states the rule — the unit layer "proves future shipped code, which
must not depend on dev tooling" — and the reference encoding *is* dev tooling. The rule is
**stated, not enforced**: conftest puts `tests/` on `sys.path` for every layer, so nothing
mechanically stops a unit test importing the encoding; the binding constraints are the py3.9
floor and this convention. Runs under `make verify`; no credentials, no network, no live
diary.

**Target Platform**: repo/CI only this slice. The documented flow targets the responder
runtime through the **diary capability**, referenced generically — no MCP server or product
names (FR-006, Constitution VII), which for this slice specifically means the design's
concrete §6.2 MVP binding is abstracted in shipped prose (spec Assumptions; research R11).

**Project Type**: plugin prose (`skills/diary/`) + contract tests + fixture entry sets.

**Performance Goals**: n/a beyond keeping the verify gate fast — every new test is in-memory
string extraction and pure-function matching over small fixture entry sets (milliseconds).

**Constraints**: prose and tests only (FR-008); the two operations are the diary's *entire*
surface and the op-set is closed — asserted as an **equality** against the contract file, since
a subset assertion would go quiet on exactly the case that matters, a future `create_diary` op
— which is what makes "never creates diaries" a derived pin rather than an aspiration (FR-004); `content` is the sole extraction surface and `at` is
never read as a date format (FR-002); every determinism pin is fixture-backed, so "no silent
pick" is counted, not claimed (SC-002/SC-003); ambiguity and malformed templates **surface**
and never block a draft; the close flow owns retry, approval, and labeling (FR-008).

**Scale/Scope**: 1 `SKILL.md` + 1 reference doc; 1 reference-encoding helper module; 8 entry-set
fixtures + 2 expectation fixtures + a fixture README; 4 contract-test modules; 1 design-doc
amendment (§6.2 + D-23); 1 `AGENTS.md` surface-list line; 2 one-line sibling touches
(`SCANNED_SKILL_DIRS` registration, the `lifecycle_flows.py` IOU citation).

**Dependency status** (updating the spec's Assumptions, which were written while they were
open PRs): slices 5, 6 and 7 have all since merged to `main`. This slice's consumed boundaries
— the close flow's drafting and dual-write, the investigation skill's delimiting rule, and the
reference-encoding testing model — are landed files, not pending ones, and are cited as such
throughout.

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Deliverables are skill markdown + tests. FR-008 forbids shipped adapter code outright; the reference encoding is dev-only test tooling under `tests/helpers/` (D-1 exemption, same standing as `bb-mock-mcp` and slice 7's `catalog_reference.py`). The packaging ratchet keeps it that way — a direct assertion that `skills/diary/` holds no `*.py` and that the encoding is named by no glob in `tests/fixtures/packaging/intended-bundle.json`. No storage code, no server, no per-tool integration |
| II — Deterministic Backstops | ✅ Every rule *whose drift the CI layer can observe* gets a mechanical gate: the resolution matrix and extraction goldens are fixture-backed with discriminating payloads, the notice vocabulary and `STRUCTURE_PARTS` are asserted both ways against the prose, the no-re-sort commitment is gated three ways (contract ordering, encoding source scan, masked prose scan), and the naming discipline is a scan. Stated honestly rather than over-claimed: three documented behaviors are **prose-only** — the *surfacing* of notices to the responder (this slice emits them; slice 5 executes the interaction), the destination pin as it binds a live runtime rather than the dev encoding, and agent compliance generally. One further gate is **accepted-weak and labelled as such** rather than presented as instrumentation: FR-003's input-signature property (data-model §9) holds by vocabulary rather than by construction, and its load-bearing half is the non-vacuity check. Those are scenario-harness territory, the same boundary `quickstart.md` draws; "a skill instruction alone is not enforcement" is respected by naming them, not by claiming gates that do not exist. The must-not-lose write is **not** this slice's — the row write's backstop is slice 3/5's session marker and read-back, and the diary write is explicitly the *losable* one (`diary_pending` is its retry queue) |
| III — Layered Guardrails | ✅ No new guardrail surface. The diary write is a mutating action, and this slice does not weaken its gate: the approval gate on the draft lives in `commands/close.md` ("no write of any kind happens before the draft is approved"), which this slice consumes and restates only as a non-goal. No security guarantee is asked of a probabilistic layer. Slice 6's untrusted-telemetry delimiting inside drafts is a consumed boundary, not scope |
| IV — Evidence Links+Excerpts | ✅ Not this slice's shape and deliberately not borrowed: a diary link is the *address of the team's own artifact*, not an evidence citation, so it carries no excerpt and the prose does not dress it as `{url, excerpt}`. The in-session evidence links that enter drafting arrive already shaped by the slices that gathered them; this slice arranges blocks and never re-shapes their contents |
| V — Causal Fields Human-Curated | ✅ The principle's sharpest test here, and the reason `apply_format` is defined as opaque-block arrangement: causal proposal labels applied by slice 5's labeling rule pass through **byte-preserved**, gated as a property that holds for every block rather than for a fixture's known label strings. The minimal default carries "(proposal)"/"(proposals)" in the heading text itself, so labels survive even a transform that preserves only heading text. Nothing here promotes a proposal to fact; promotion is the responder's decision in the close flow |
| VI — Validated Memory | ✅ Untouched. Recent entries are read for *format*, never as recalled knowledge — no entry's content becomes a hypothesis, so no VALIDATED/INVALIDATED discipline attaches. Worth stating rather than skipping: reading five past entries is exactly the shape that could be mistaken for recall, and it is not |
| VII — Capability Contracts | ✅ The slice's most load-bearing constraint. Prose references the diary capability's operations only; the shared `DENY_PATTERNS` scan (which already carries the concrete product and MCP names §6.2 uses) runs over `skills/diary/**/*.md` with a `mcp__` hard fail and a positive control, and every backticked operation token is checked against the contract file. The abstraction of §6.2's concrete MVP binding is deliberate and recorded (spec Assumptions; D-23) |
| VIII — Test-First, Agent-Led | ✅ Prose and its tests land in the same change, per user story (the *phase* is the commit seam, so no encoding lands without the module that asserts on it). Every assertion is on artifacts — extracted structures, resolution outcomes, notice records, write logs, scan results — never on prose opinion. SC-001 maps every FR to ≥1 test (`quickstart.md`), FR-008 included: its gate is the packaging assertion above, not an end-of-slice eyeball |
| Platform Constraints | ✅ Nothing shipped executes, so the stdlib rule is satisfied vacuously — and the test code honors it anyway (stdlib only), leaving the CI gate surface untouched. Degraded operation is respected in both directions this slice touches: a malformed template and an ambiguous date each degrade to a surfaced notice and a usable draft, and a diary-write failure is explicitly *not* this slice's path to handle (`diary_pending`, slice 3/5) |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/008-diary-adapter/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R1–R13 plan-time pins (layout, depth, template,
│                                    #   extraction, defaults, gate mechanisms)
├── data-model.md                    # interface, Entry consumption rules, Structure,
│                                    #   FormatResolution + notice vocabulary, MINIMAL_DEFAULT,
│                                    #   DraftInputs, fixture roster
├── quickstart.md                    # validation scenarios + the FR/SC → test map
├── checklists/requirements.md
└── tasks.md                         # Phase 2 (/speckit-tasks)
```

No `specs/…/contracts/` directory (slice-3, slice-6, slice-7 precedent): this slice's
contract artifact **is** the deliverable prose — `skills/diary/SKILL.md` is the normative
adapter interface and `references/format.md` the normative resolution/extraction rules.
Duplicating them under `specs/` would create a second source of truth for exactly the content
FR-001–FR-006 pin. Cross-slice contracts this slice consumes (operation contract v1, the
session-row schema, the close flow's draft/approval rules) are cited in place, never copied.

### Source Code (repository root)

```text
skills/diary/
├── SKILL.md                         # FR-001/004/005/008: the two-operation interface and
│                                    #   its contract realization; the error posture (attempt
│                                    #   + honest report, retry belongs to the close flow);
│                                    #   the write flow — configured diary via the diary
│                                    #   capability, append-only, no creation, no alternate
│                                    #   destination; the entry→link→row linkage; the drafting
│                                    #   handoff and its input contract (and what is NOT an
│                                    #   input: the row, the timeline); non-goals + deferrals
└── references/
    └── format.md                    # FR-002/003: template-wins-else-match-recent; absent vs
                                     #   malformed; the extraction rules (heading shapes, the
                                     #   title split out of the compared shape, date-format
                                     #   tokens + the padding rule, field-order normalization,
                                     #   bounded extraction); read depth 5 and its config key;
                                     #   consistency detection + freshest-wins; pass-level date
                                     #   ambiguity, else surfaced; the minimal default (incl.
                                     #   its Evidence link+excerpt rule) + template-candidate
                                     #   offer; the ordering-consumption rule — consumers never
                                     #   re-sort, and the adapter-side half; the notice
                                     #   vocabulary; STRUCTURE_PARTS; row independence

tests/helpers/
└── diary_reference.py               # research R12: dev-only reference encoding —
                                     #   extract_structure / resolve_format / apply_format /
                                     #   consume_recent + MINIMAL_DEFAULT, NOTICE_KINDS,
                                     #   FORMAT_INPUT_KEYS. Stdlib only; plain functions over
                                     #   plain dicts; the CI instrument

tests/fixtures/diary/
├── README.md                        # fixture format decision + what each set discriminates
├── entries-consistent.json          # 5 uniform ATX entries, ISO dates
├── entries-bold.json                # bold-only section labels
├── entries-inconsistent.json        # newest differs → freshest-wins
├── entries-ambiguous-date.json      # both components ≤ 12 throughout
├── entries-disambiguating.json      # one component > 12 resolves the order
├── entries-short.json               # 2 entries — fewer than n
├── entries-empty.json               # [] — minimal-default path
├── entries-labeled-causal.json      # labeled causal sections + the `sections` key
│                                    #   apply_format consumes, for byte-preservation
├── golden-structures.json           # SC-003 expectations, per entry set
└── resolution-matrix.json           # SC-002 expectations, per (template state, entry set)

tests/contract/
├── test_diary_format.py             # US1 + SC-002/SC-003: the resolution matrix; extraction
│                                    #   goldens field-for-field; freshest-wins + drift notice;
│                                    #   date ambiguity surfaced and resolved; malformed-
│                                    #   template fallback; minimal default + template
│                                    #   candidate; label pass-through byte-preserved (FR-005);
│                                    #   the FR-003 input-signature property
├── test_diary_write.py              # US2 + SC-004: append returns the link; the link is the
│                                    #   value handed onward for the row; exactly one diary
│                                    #   append per close; op-set confined to the two
│                                    #   operations; the uniform error envelope surfaced
├── test_diary_ordering.py           # US3 + SC-005: newest-first end-to-end against the mock;
│                                    #   entries[0] is the freshest consumed; short and empty
│                                    #   reads; the encoding's no-reorder source scan
└── test_diary_prose.py              # SC-006 + FR-006/008: naming scan (shared DENY_PATTERNS,
                                     #   mcp__ hard fail, positive control); operation fidelity
                                     #   against contract.json; ordering statement + masked
                                     #   re-sort scan; prose↔encoding notice-vocabulary
                                     #   agreement; packaging ratchet (no *.py under
                                     #   skills/diary/, encoding named by no bundle glob);
                                     #   non-goals/boundary gates

tests/contract/test_catalog_prose.py # research R13: "diary" registered in SCANNED_SKILL_DIRS,
                                     #   in the same change as its naming scan
tests/helpers/lifecycle_flows.py     # research R14: the slice-8 IOU comment repointed at the
                                     #   landed rules — a citation change, no behavior change
bb-technical-design.md               # research R11: §6.2 clarification + decision-log D-23
AGENTS.md                            # shipped-surface list gains skills/diary
```

**Structure Decision**: `skills/diary/` matches design §3.1's own `skills/diary/SKILL.md`
and **extends** it with a `references/` subdirectory — the same expansion slice 7 made for
`catalog/`, following the `session-store/` and `investigation/` siblings shown directly above
it in that same tree; the §6.2 amendment folds in the layout note. Tests extend
`tests/contract/` in place and reuse slice-1 conftest helpers plus slice-3's scan mechanism;
fixtures follow the scaffold's real `tests/fixtures/<domain>/` convention. All new Python is
dev-only test code — this slice ships no executable anything.

## Complexity Tracking

Not required — Constitution Check passed without violations.
