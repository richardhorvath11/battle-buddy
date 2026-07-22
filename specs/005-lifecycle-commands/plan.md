# Implementation Plan: Lifecycle Commands

**Branch**: `005-lifecycle-commands` | **Date**: 2026-07-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/005-lifecycle-commands/spec.md`

## Summary

Ship the session lifecycle surface as command prose plus its executable specification
(design §3.2, §4, §9; Constitution I): `/page` (preflight → marker → open flow →
checkpoint zero riding the open append → briefing), `/incident` (incident defaults +
in-place promotion), and `/close` (draft with proposal-labeled causal fields → approved
dual-write → read-back-gated marker deletion, plus merge-at-close and close-time
ownership). These commands *execute* the slice-3 session-store conventions and are the
designated writer of the slice-2 local-state protocol's marker. Zero shipped storage or
agent code: the only Python written lives under `tests/` — `lifecycle_flows.py` (the
three commands' executable form, built on slice-3 `store_flows` and slice-4
`setup_flows`/`doctor_flows`) and `lifecycle_fixtures.py` (fixture stand-ins for the
consumed slice-6–9 surfaces). Cross-slice pins (preflight decision table, marker join
extension, draft/briefing artifact shapes, timeline derivation, close ordering scope,
transcript capture) are normative in
[`contracts/lifecycle-protocol.md`](contracts/lifecycle-protocol.md).

## Technical Context

**Language/Version**: Shipped deliverables are three markdown command documents
(`commands/page.md`, `commands/incident.md`, `commands/close.md`) — plugin bundle
documentation surface (design §3.1). Test code is Python 3 on the slice-1 pytest harness
(dev-only; Platform Constraints exempt dev tooling), at the repo's 3.9 floor.

**Primary Dependencies**: none at runtime (nothing shipped executes); pytest dev-only;
`bb-mock-mcp` (in-tree) as the storage/artifacts/diary/alerting double; slice-2 `bin/`
helpers imported real (`bb_validate` for verdict validation, `bb_fingerprint` for
fingerprints — research R3/R4); slice-3 `store_flows` (columns, parse rule, retrieval,
checkpoint, ownership primitives, and `close_session` extended with additive
default-off params — R1/R13; `open_session` itself is *not* reused, per R1's reuse
boundary); slice-4 `doctor_flows.evaluate_stamp` +
`setup_flows.responder_mode` (preflight, research R11).

**Storage**: none real — all test I/O flows through operation contract v1. Local state
is the slice-2 protocol's `.bb-session/` on tmp dirs (marker, staging). Surfaces the
contract lacks (triage agent, catalog parsing, diary format matching, shell adapter) are
fixture surfaces pinned in research R3–R6 and `data-model.md`.

**Testing**: contract layer (`tests/contract/`) — the documented command steps driven as
deterministic scripts against `bb-mock-mcp` with temporary local-state directories:
marker lifecycle, write-log ordering, join/promotion/merge/ownership paths, draft and
briefing structural assertions, one full open→close simulation (SC-007). Runs under
`make verify`, no credentials, no network.

**Target Platform**: repo/CI only this slice (docs + tests); the documented commands
target the responder runtime without naming servers (FR-011 — the existing naming gate
auto-covers new `commands/*.md` by glob).

**Project Type**: plugin documentation (`commands/` — completing the five-command set)
+ contract tests.

**Performance Goals**: n/a beyond the verify gate staying fast (in-memory, seconds).
NFR-1 is expressed as the no-probe preflight property (SC-002), asserted on artifacts.

**Constraints**: zero shipped storage/agent code (FR-013, Constitution I); command prose
references capabilities/operations only (FR-011); every FR exercised by ≥1 hermetic
contract test (FR-012); marker shapes owned by local-state protocol v1, written not
redefined (FR-002); slice-3 conventions executed, never restated normatively; causal
fields proposal-labeled structurally (SC-006, Constitution V); evidence `{url, excerpt}`
throughout (Constitution IV).

**Scale/Scope**: 3 command docs + 1 cross-slice contract doc; 2 test-helper modules;
~7 contract-test modules; 1 fixture directory (`tests/fixtures/lifecycle/`).

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Deliverables are command prose and tests. No storage code, no agent definitions, no server; triage/catalog/diary-format/shell are consumed surfaces stood in by fixtures (FR-013). Executable form lives in `tests/` (dev-only), the established slice-3/4 pattern |
| II — Deterministic Backstops | ✅ This slice writes exactly the protocol shapes slice 2's deterministic layer reads (marker lifecycle, staging). Read-back gates both confirmation points; deletion-is-cleared stays exclusive to confirmed close; the crash-residue path is a marker *rewrite*, preserving the guard's semantics (research R8) |
| III — Layered Guardrails | ✅ No security claims added; no guardrail surface touched. Fail-soft behaviors (alert fetch, shell, diary) are availability postures, not security claims |
| IV — Evidence Links+Excerpts | ✅ Briefing claims and folded merge links are `{url, excerpt}` pairs structurally asserted (R16); timeline derives from trace + checkpoints, never prose (R10) |
| V — Causal Fields Human-Curated | ✅ The draft artifact separates factual autofill from proposal-labeled causal fields structurally (`bb.draft.v1`, R5); SC-006 asserts causal values appear only under proposal-labeled fields; no flow promotes a proposal without the approval step |
| VI — Validated Memory | ✅ Checkpoint zero passes `bb-validate` before persisting (real validator, R2); recalled candidates reach the briefing only through the verdict's validation-marked fields; retrieval exclusions ride slice-3 `retrieve_candidates` unchanged |
| VII — Capability Contracts | ✅ Command prose cites operations in `capability.operation` form only; the existing FR-010 naming gate (`test_command_capability_naming.py`) covers the three new docs automatically via its `commands/*.md` glob |
| VIII — Test-First, Agent-Led | ✅ Docs and tests land in the same change; FR-012 maps every FR to ≥1 contract test asserting on artifacts (write log, marker file, draft/briefing/timeline structures), never prose |
| Platform Constraints | ✅ Nothing shipped executes; test Python dev-only; degraded shell mode is a first-class tested path (R6); no credentials anywhere |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/005-lifecycle-commands/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R1–R17 plan-time pins
├── data-model.md                    # entities, artifact shapes, fixture surfaces
├── quickstart.md                    # validation scenarios → test modules
├── contracts/
│   └── lifecycle-protocol.md        # cross-slice authority: preflight table, marker
│                                    #   join/crash extensions, bb.draft.v1, briefing
│                                    #   properties, timeline derivation, close ordering
│                                    #   scope, transcript capture, additive config keys
├── checklists/requirements.md
└── tasks.md                         # Phase 2 (/speckit-tasks)
```

The contracts/ doc exists because slice 6 (triage/deep launch commitments, briefing
consumption), slice 8 (diary draft rendering), and slice 9 (shell call points) consume
rules no shipped file states normatively, and because this slice pins two documented
local-state-protocol *extensions* (join-path marker confirmation, close-time ownership
scope) flagged in the spec's Assumptions for later protocol reconciliation.

### Source Code (repository root)

```text
commands/
├── page.md                          # FR-001/002/004/005/006: preflight, marker
│                                    #   handling, open flow order, join-vs-separate,
│                                    #   checkpoint zero, briefing; §3.2
├── incident.md                      # FR-003: incident defaults, deep proposal,
│                                    #   in-place promotion; §3.2/§3.4
└── close.md                         # FR-007–FR-010: draft + curation, merge-at-close,
                                     #   dual-write order, ownership, artifacts,
                                     #   timeline, marker deletion; §4

tests/helpers/lifecycle_fixtures.py  # fixture stand-ins (R3–R6): verdict fixtures +
│                                    #   re-prompt sequences, catalog resolver,
│                                    #   RecordingShellAdapter (+ degraded recorder),
│                                    #   staged-file builders, transcript source
tests/helpers/lifecycle_flows.py     # the commands' executable form (R1): preflight,
│                                    #   open_command (page/incident), promote_session,
│                                    #   join_session / open_separate, draft_close,
│                                    #   close_command (merge → dual-write → read-back)
tests/contract/
├── test_page_preflight.py           # FR-001 preflight: happy path no probes (SC-002),
│                                    #   missing config stop, stale stamp → responder
│                                    #   mode, existing-marker + crash-residue paths
├── test_open_flow.py                # US1: marker lifecycle, row fields, checkpoint
│                                    #   zero rides append (R2), validation re-prompt/
│                                    #   flagged, alert-fetch failure, catalog ladder
├── test_briefing_properties.py      # FR-006: every claim {url, excerpt}, top-cited
│                                    #   dashboard navigate vs degraded printed links
├── test_incident_flows.py           # US2/SC-003: incident defaults, deep proposal/
│                                    #   auto-launch flag, promotion update-not-append
├── test_join_separate.py            # US3/SC-004: join offer, no writes pre-choice,
│                                    #   rehydrate + take-over + marker rewrite (R7),
│                                    #   separate appends exactly one row
├── test_close_command.py            # US4/SC-005/SC-006: draft structure, ordering,
│                                    #   diary_pending, read-back-then-delete,
│                                    #   transcript capture (R9), timeline (R10)
├── test_close_merge_ownership.py    # FR-010: merge-at-close canonical/superseded,
│                                    #   displacement → read-only, no-session close
└── test_lifecycle_full_sim.py       # SC-007: full open→close simulation, zero ops
                                     #   outside the operation contract
tests/fixtures/lifecycle/
├── verdicts/*.json                  # fixture triage outputs incl. invalid + re-prompt
├── catalog.json                     # fixture catalog data (alert → service mapping)
└── seeds/*.json                     # seeded rows for join/merge/promotion scenarios
```

**Structure Decision**: `commands/` completes design §3.1's five-command layout. Flow
and fixture modules live in `tests/helpers/` beside `store_flows.py` and
`setup_flows.py` (same executable-specification relationship; the packaging test
already fences `tests/`). The cross-slice contract lives under
`specs/005-lifecycle-commands/contracts/` mirroring the slice-2/slice-4 precedent.

## Complexity Tracking

Not required — Constitution Check passed without violations.
