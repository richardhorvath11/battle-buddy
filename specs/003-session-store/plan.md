# Implementation Plan: Session-Store Conventions

**Branch**: `003-session-store` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-session-store/spec.md`

## Summary

Ship the tier-0 session-store conventions as documentation that behaves like a schema
(design §5, Constitution I): the session-store skill (`skills/session-store/SKILL.md` +
references for schema, fingerprint, retrieval) documenting the Sheet schema and mutation
policy, the normative fingerprint reference, the Drive artifact layout, the checkpoint
representation with the 45,000-char cell guard, the three-stage retrieval flow, the
close-time dual-write with read-back, and optimistic ownership — plus a hermetic
contract-test layer that *executes* every convention against `bb-mock-mcp` through
operation contract v1. Zero shipped storage code: the only Python written in this slice
lives under `tests/` (dev-only), as test-side flow scripts that are the conventions'
executable form.

## Technical Context

**Language/Version**: Shipped deliverables are markdown (skill + references — the plugin
bundle's documentation surface, design §3.1). Test code is Python 3 on the slice-1
pytest harness (dev-only; Constitution Platform Constraints exempt dev tooling); the
tests import the real slice-2 helpers (`bb_fingerprint`, `bb_validate`) at the repo's
3.9 floor.

**Primary Dependencies**: none at runtime (no runtime code ships); pytest dev-only;
`bb-mock-mcp` (in-tree, dev-only) as the store double; slice-2 `bin/` helpers as the
validation/fingerprint gates the conventions cite.

**Storage**: none real — all I/O in tests flows through operation contract v1
(`tools/bb-mock-mcp/contract.json`): storage `append_record`/`read_records`/
`update_record`, artifacts `put_file`/`get_file`, diary `append_entry`. Local session
state per local-state protocol v1 (`specs/002-deterministic-layer/contracts/
local-state-protocol.md`), extended additively with `staging/checkpoints.jsonl`
(research R1).

**Testing**: contract layer (`tests/contract/`) against `bb-mock-mcp` — write ordering
via `write_log.entries`, durability via read-back ops, retrieval via seeded fixtures;
plus the SC-006 mechanical cross-check parsing the schema doc's column table. Runs under
`make verify` with no credentials and no network.

**Target Platform**: repo/CI only this slice (docs + tests); the documented conventions
target the responder runtime described by the design (Google Sheet/Drive via
team-brought MCPs) without naming servers (Constitution VII).

**Project Type**: plugin documentation (`skills/session-store/`) + contract tests —
first slice to ship skill content.

**Performance Goals**: n/a beyond the verify gate staying fast (contract layer is
in-memory, seconds).

**Constraints**: zero shipped storage code (FR-012); skill prose references capabilities/
operations only, store-medium nouns permitted (FR-010); every convention exercised by ≥1
hermetic contract test (FR-011); tier-1-stable field names/formats declared (FR-013).

**Scale/Scope**: 1 SKILL.md + 3 reference docs; ~7 contract-test modules + 1 flow-script
helper module; ~2 fixture directories; 1 additive edit to the local-state protocol doc
(recorded per that doc's versioning duty).

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Deliverables are skill markdown + tests; no server, no storage code, no per-tool integration. The conventions' executable form lives in `tests/` (dev-only, like the mock). FR-012 makes any storage-shaped helper a recorded scope decision |
| II — Deterministic Backstops | ✅ This slice documents the conventions and *consumes* slice-2 backstops (marker read-back points, `bb-validate` gate); no new enforcement code — the spec's "skill enforcement split" assumption made real. Every must-not-lose behavior gets a mechanical contract test |
| III — Layered Guardrails | ✅ No security claims made; no guardrail surface touched. Retrieval/close conventions are behavior, not guarantees |
| IV — Evidence Links+Excerpts | ✅ Schema doc pins `links` and evidence-bearing fields as `{url, excerpt}` pairs; US5 regenerability test asserts it |
| V — Causal Fields Human-Curated | ✅ Schema doc marks `root_cause`/`resolution` human-curated (design §5.1); conventions never auto-promote |
| VI — Validated Memory | ✅ Retrieval conventions present recalled rows as hypotheses (candidates); checkpoint conventions require `bb-validate` before every write with the one-re-prompt-then-flag path (FR-006) |
| VII — Capability Contracts | ✅ FR-010 is a requirement of this slice: skill prose names operations only; a test greps the skill docs for concrete MCP server/tool names |
| VIII — Test-First, Agent-Led | ✅ Docs and their contract tests land in the same change; FR-011 maps every FR to ≥1 test; SC-006's cross-check keeps doc and tests mechanically converged |
| Platform Constraints | ✅ Nothing shipped executes; test Python is dev-only; no credentials anywhere |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/003-session-store/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R1–R10 plan-time pins (locations, versions, mechanisms)
├── data-model.md                    # column set, mutation classes, checkpoint/overflow shapes
├── quickstart.md                    # validation scenarios mapped to test modules
├── checklists/requirements.md
└── tasks.md                         # Phase 2 (/speckit-tasks)
```

No `specs/…/contracts/` directory: this slice's contract artifacts ARE the deliverable
skill docs (`skills/session-store/`), shipped in the plugin bundle — duplicating them
under `specs/` would create a second source of truth for the exact content FR-001–FR-009
pin. The one existing cross-slice contract this slice touches is slice 2's
`local-state-protocol.md`, edited additively in place per its own versioning duty
(research R1).

### Source Code (repository root)

```text
skills/session-store/
├── SKILL.md                         # conventions core: open/close dual-write + read-back
│                                    #   confirmation points, checkpoint representation +
│                                    #   validation gate, optimistic ownership, artifact
│                                    #   layout, failure paths (diary/artifact/not-found)
└── references/
    ├── schema.md                    # FR-001/FR-002: column table (SC-006's parse target),
    │                                #   mutation policy, bb.schema.v1 + Sheet representation,
    │                                #   tier-1 stability commitment (FR-013)
    ├── fingerprint.md               # FR-003: normative bb.fp.v1 rules, construction,
    │                                #   resolution ladder, catalog_resolved semantics
    └── retrieval.md                 # FR-007: three stages, exclusions, cap 20 + surfaced
                                     #   truncation, catalog_resolved downgrade (normative
                                     #   here; slice 6 references it — research R3)

specs/002-deterministic-layer/contracts/local-state-protocol.md
                                     # additive edit: staging/checkpoints.jsonl recorded
                                     #   (research R1; no version bump — no consumer-parse change)

tests/helpers/store_flows.py         # the conventions' executable form (research R4):
                                     #   open_session, write_checkpoint, take_over,
                                     #   retrieve_candidates, close_session — each step
                                     #   cites the skill section it executes; dev-only
tests/contract/
├── test_store_schema_doc.py         # SC-006 cross-check; FR-002 mutation policy;
│                                    #   FR-010 no-tool-names grep; FR-013 stability text
├── test_fingerprint_reference.py    # FR-003 consistency: doc version == helper VERSION ==
│                                    #   golden-corpus version; doc examples recompute
├── test_retrieval_flow.py           # US1: stage 1/2/3, exclusions, cap+surfacing, downgrade
├── test_close_flow.py               # US2: ordering via write_log, read-back → marker clear,
│                                    #   diary-failure → diary_pending, artifact-failure path
├── test_checkpoint_conventions.py   # US3: cell guard boundary, overflow round-trip,
│                                    #   history accumulation, validate-fail re-prompt path
├── test_ownership.py                # US4: take-over write, displaced-writer denial,
│                                    #   join-at-open (source ID + non-terminal status),
│                                    #   merge-at-close → superseded
└── test_artifact_layout.py          # US5: folder path, four names, trace.jsonl mapping,
                                     #   row-links resolve via get_file, regenerability

tests/fixtures/store/
├── seed-retrieval.json              # exact-match, keyword-overlap, test/superseded,
│                                    #   unresolved-catalog rows (mock load_seed format)
├── seed-ownership.json              # open/handoff rows for join + merge scenarios
└── checkpoints/*.json               # valid, invalid(+re-prompt pair), at-guard, over-guard
```

**Structure Decision**: `skills/session-store/` matches design §3.1's plugin layout, with
`retrieval.md` added to its references per the spec's placement assumption (research R3).
The flow scripts live in `tests/helpers/` beside the existing slice-1 helpers — they are
the executable specification of the documented conventions, the same relationship
`bb-mock-mcp` has to the operation contract, and they never ship (FR-012, packaging test
already fences `tests/`). Contract tests extend `tests/contract/` in place.

## Complexity Tracking

Not required — Constitution Check passed without violations.
