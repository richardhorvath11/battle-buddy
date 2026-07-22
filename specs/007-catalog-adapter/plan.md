# Implementation Plan: Catalog Adapter

**Branch**: `007-catalog-adapter` | **Date**: 2026-07-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-catalog-adapter/spec.md`

## Summary

Ship the service-catalog surface as prose plus hermetic tests (design §6.1, §2's division of
knowledge, §5.2 rung 1): `skills/catalog/SKILL.md` plus two references pinning the six-field
internal `Service` model, the literal annotation mapping, alert→service resolution
(exact-then-substring, explicit choice on ambiguity, ask-once + fix-up on a miss), per-field
and per-file graceful degradation, one-hop `dependsOn` blast-radius widening, and the
fetched-fresh/never-copied freshness rule with pointer-only runbook references.

The CI instrument is a **dev-only, test-side reference encoding**
(`tests/helpers/catalog_reference.py`) of those documented rules, run over a **fixture
catalog repo this slice creates** (`tests/fixtures/catalog/`) — the same doc↔executable
relationship slice 3 pinned between `fingerprint.md` and `bb-fingerprint`, except nothing
here ships (FR-009, Constitution I): at runtime the "parser" is an agent reading files
through the code capability. Four contract-test modules gate the rules' coherence, the
golden models, the resolution matrix, and the prose's capability/storage-op discipline.
Whether a live agent *follows* the prose stays scenario-harness territory (spec's stated
slice-6 boundary), not CI.

Two cross-slice reconciliations land in the same change: slice 4's doctor catalog fixture is
retagged to the canonical annotation vocabulary (research R4), and `bb-technical-design.md`
gains a §6.1 clarification plus decision-log row **D-22** recording this slice's six pins
(research R9).

## Technical Context

**Language/Version**: shipped deliverables are markdown (`skills/catalog/SKILL.md` + two
references — design §3.1's plugin layout). Test code is Python 3 on the slice-1 pytest
harness, **stdlib only** (`json`, `pathlib`, `re`) — dev-only, and deliberately dependency-free
so the contract layer's CI step (`pip install pytest`) needs no edit (research R2).

**Primary Dependencies**: none at runtime — no runtime code ships. pytest dev-only. The
slice consumes, and never restates: `manifest/capabilities.json` (slice 4) as the
`code`-capability authority for research R6's fidelity backstop, slice 3's
`skills/session-store/` conventions as the `runbook_refs` home, and
`tests/contract/test_skill_capability_naming.py`'s public `DENY_PATTERNS` as the SC-005 scan
mechanism.

**Storage**: none. This slice performs **zero** store I/O by design — that is FR-005's
whole point, and SC-006's scan is what instruments it. Catalog data is read fresh from the
team's git repo through the code capability at session start and copied nowhere; only
pointer-shaped runbook references (`{url, commit?}`) ever reach a session row, and slice 5
is what writes them.

**Testing**: contract layer only (`tests/contract/`) — golden-model parsing, the resolution
matrix, degradation and malformed-file isolation, one-hop widening, and four prose gates
(SC-005 naming scan with the annotation-key mask, SC-006 storage-op scan, FR-007 generic
code-capability reference, prose↔encoding annotation-table agreement). Nothing lands in
`tests/unit/`: the unit layer runs at the py3.9 shipped-code floor and `tests/conftest.py`
states the layer rule — the unit layer "proves future shipped code, which must not depend on
dev tooling" — and the reference encoding *is* dev tooling (research R8). The rule is
**stated, not enforced**: conftest puts `tests/` on `sys.path` for every layer, so nothing
mechanically stops a unit test importing the encoding; the binding constraints are the py3.9
floor and this convention. Runs under `make verify`; no credentials, no network, no live git.

**Target Platform**: repo/CI only this slice. The documented flow targets the responder
runtime through the **code capability**, referenced generically — no MCP server or tool
names, and no code-operation names either (FR-007, Constitution VII).

**Project Type**: plugin prose (`skills/catalog/`) + contract tests + fixture catalog repo.

**Performance Goals**: n/a beyond keeping the verify gate fast — every new test is in-memory
document parsing and pure-function matching over 11 fixture files (milliseconds).

**Constraints**: prose and tests only (FR-009); the six-field model is the *only* shape that
crosses the adapter boundary (FR-001); literal annotation keys are normative and must survive
the naming scan via a whole-key mask, never by degrading the doc (SC-005, research R5); every
determinism pin is fixture-backed, so "zero silent picks" is counted, not claimed (SC-003,
research R7); file-mode Backstage is v1's only catalog source, API-mode explicitly deferred.

**Scale/Scope**: 1 `SKILL.md` + 2 reference docs; 1 reference-encoding helper module; a
11-entity fixture catalog repo (8 parsed services) + 2 expectation fixtures + a fixture
README; 4 contract-test
modules; 1 slice-4 fixture retag; 1 design-doc amendment (§6.1 + D-22).

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Deliverables are skill markdown + tests. FR-009 forbids a parsing library outright; the reference encoding is dev-only test tooling under `tests/helpers/` (D-1 exemption, same standing as `bb-mock-mcp`). The declared bundle names no `tests/` path and the packaging ratchet keeps it that way (research R10) — a string lint over the declared globs, not filesystem proof, so T022 adds the direct assertion that the encoding is named by no bundle glob. No storage code, no server, no per-tool integration |
| II — Deterministic Backstops | ✅ Every rule *whose drift the CI layer can observe* gets a mechanical gate: the annotation table is compared to the reference encoding's vocabulary, the determinism pins are fixture-backed cases with discriminating payloads, and the naming/storage-op discipline is a scan. Stated honestly rather than over-claimed: three documented rules are **prose-only** — the catalog-unreachable path (gated as a *statement*, not a behavior), FR-001's no-raw-structure property as it applies to shipped prose rather than the dev encoding, and agent compliance generally. A fourth, "no agent ever writes to the catalog", is **not** prose-only and an earlier draft misclassified it: read-only credentials by default (Platform Constraints, guardrail layer 2) are a deterministic backstop, and the shipped prose now says so rather than leaving the claim resting on instruction. Those are scenario-harness territory, the same boundary `quickstart.md` draws; "a skill instruction alone is not enforcement" is respected by naming them, not by claiming a gate that does not exist |
| III — Layered Guardrails | ✅ No new guardrail surface. The catalog is read-only data through an optional capability; the fix-up is a snippet for a human to commit, never an agent write — no mutating path is introduced, so no probabilistic layer is asked to carry a guarantee |
| IV — Evidence Links+Excerpts | ✅ Not this slice's shape, and deliberately kept distinct: a `RunbookRef` is `{url, commit?}` — a *pointer with a version* — and the prose says so rather than borrowing the `{url, excerpt}` evidence shape for something that is not an evidence claim (research R11) |
| V — Causal Fields Human-Curated | ✅ Untouched. The catalog carries no causal content. The adjacent discipline this slice does honor: the catalog is human-curated data the harness reads and never writes |
| VI — Validated Memory | ✅ Consumed, not restated. Resolution feeds slice 3's fingerprint ladder (rung 1) and `catalog_resolved`; a miss downgrades match confidence exactly as §5.2/D-19 already pin. This slice adds no recall semantics |
| VII — Capability Contracts | ✅ The slice's sharpest constraint. Prose references the `code` capability generically; SC-005's scan runs with a **whole-key** annotation mask so vendor words still fail as product names (research R5); FR-007's zero-code-op rule is gated, with a manifest-fidelity backstop should it ever be relaxed (research R6) |
| VIII — Test-First, Agent-Led | ✅ Prose and its tests land in the same change, per user story (the *phase* is the commit seam, so no encoding lands without the module that asserts on it). Every assertion is on artifacts — parsed models, resolution outcomes, warning/failure records, scan results — never on prose opinion. SC-001 maps every FR to ≥1 test (`quickstart.md`), FR-009 included: its gate is a direct assertion that `skills/catalog/` holds no `*.py` and that the reference encoding is named by no bundle glob, rather than the end-of-slice eyeball an earlier draft relied on |
| Platform Constraints | ✅ Nothing shipped executes, so the stdlib rule is satisfied vacuously — and the test code honors it anyway (stdlib-only, no YAML dependency, research R2), leaving the CI gate surface untouched. Degraded operation is the slice's *subject*: FR-004's per-field degradation and the catalog-unreachable path both keep the session open |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/007-catalog-adapter/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R1–R12 plan-time pins (locations, formats, mechanisms)
├── data-model.md                    # Service/Catalog/Alert/Resolution shapes, match order,
│                                    #   degradation map, fixture roster + resolution matrix
├── quickstart.md                    # validation scenarios mapped to test modules
├── checklists/requirements.md
└── tasks.md                         # Phase 2 (/speckit-tasks)
```

No `specs/…/contracts/` directory (slice-3 and slice-6 precedent): this slice's contract
artifact **is** the deliverable prose — `skills/catalog/references/annotations.md` is the
normative annotation mapping and `resolution.md` the normative match order. Duplicating them
under `specs/` would create a second source of truth for exactly the content FR-001–FR-007
pin. Cross-slice contracts this slice consumes (capability manifest, session-store
conventions, fingerprint ladder) are cited in place, never copied.

### Source Code (repository root)

```text
skills/catalog/
├── SKILL.md                         # FR-001/004/005/009: the six-field model as the only
│                                    #   consumer shape; freshness + never-copied rule;
│                                    #   per-field and per-file degradation; what this
│                                    #   surface does NOT do (no writes, no caching,
│                                    #   file-mode only, API-mode deferred)
└── references/
    ├── annotations.md               # FR-002: the literal annotation mapping table,
    │                                #   multi-valued parsing, entity classification,
    │                                #   linkage metadata as adapter-internal (D-22),
    │                                #   duplicate-name tie-break, runbook-ref format
    └── resolution.md                # FR-003/006: exact-then-substring order + pinned
                                     #   substring direction, ambiguity → explicit choice,
                                     #   miss → ask-once → fingerprint rung 2 → fix-up
                                     #   snippet, one-hop blast radius with the depth bound

tests/helpers/
└── catalog_reference.py             # research R3: dev-only reference encoding —
                                     #   parse_entity / load_catalog / resolve /
                                     #   disabled_features / blast_radius / fixup_offer.
                                     #   Stdlib only; plain dicts; the CI instrument

tests/fixtures/catalog/
├── README.md                        # research R2: YAML-flow-style format decision + the
│                                    #   honestly-stated residual gap
├── repo/services/<11 entities>/catalog-info.yaml
├── golden-models.json               # US2/SC-002 expectations, per service
└── resolution-matrix.json           # US1/SC-003 expectations, per alert case

tests/contract/
├── test_catalog_model.py            # US2: golden models field-for-field incl. empty-list
│                                    #   defaults; minimal subset sufficiency; non-service
│                                    #   entities ignored; linkage kept out of the model
├── test_catalog_resolution.py       # US1/SC-003: the full resolution matrix; exact-beats-
│                                    #   substring globally; ambiguity surfaces candidates;
│                                    #   sparse alerts miss without crashing; substring
│                                    #   direction; duplicate-name tie-break + warning
├── test_catalog_degradation.py      # US3/SC-004: per-field disabled features; malformed-
│                                    #   file isolation (other services unaffected);
│                                    #   one-hop dependsOn widening + two-hop bound
└── test_catalog_prose.py            # US4 + SC-005/SC-006: naming scan with the whole-key
                                     #   annotation mask + positive control; storage-op
                                     #   scan; FR-007 generic code-capability reference +
                                     #   manifest fidelity backstop; prose↔encoding
                                     #   annotation-table agreement; freshness/never-copied
                                     #   and runbook-pointer prose gates; doctor-fixture
                                     #   vocabulary ratchet

tests/fixtures/doctor/catalog-valid.json   # research R4: retagged to canonical annotations

bb-technical-design.md               # research R9: §6.1 clarification + decision-log D-22
```

**Structure Decision**: `skills/catalog/` matches design §6.1's own reference to
`skills/catalog/SKILL.md` and **extends** §3.1's plugin layout, which shows a bare
`catalog/SKILL.md` with no `references/` subdirectory — the expansion follows the
`session-store/` and `investigation/` sibling precedent directly above it in that same tree,
and T021 folds the layout change into the §6.1 amendment. Tests extend `tests/contract/` in place
and reuse slice-1 conftest helpers plus slice-3's scan mechanism; the fixture catalog follows
the scaffold's real `tests/fixtures/<domain>/` convention rather than design §10's superseded
`tests/scenarios/` sketch (research R1). All new Python is dev-only test code — this slice
ships no executable anything.

## Complexity Tracking

Not required — Constitution Check passed without violations.
