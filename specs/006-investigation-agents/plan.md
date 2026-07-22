# Implementation Plan: Investigation Agents & Skill

**Branch**: `006-investigation-agents` | **Date**: 2026-07-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-investigation-agents/spec.md`

## Summary

Ship the two-speed investigation core as prose plus hermetic tests (design §3.3, §3.4,
§3.5 layer 4, §5.4): the investigation skill (`skills/investigation/SKILL.md` +
references for schemas, briefing, and a retrieval pointer) leading with the validation
discipline, and five agent definitions (`agents/` — triage, deep investigator, three
specialists) pinning model class, budget, capability-named toolsets, and contracts.
The schemas reference becomes the normative statement of `bb.verdict.v1` and
`bb.ledger.v1` in the same doc-to-tool relationship slice 3 pinned for the fingerprint:
the merged slice-2 validator (`bb-validate`) is the implementation, and a contract-test
consistency layer classifies every documented worked example through the real validator.
No code ships beyond tests (Constitution I): the validator, hooks, protocol, and store
conventions this slice cites are slices 2 and 3; the orchestration that spawns these
agents is slice 5.

## Technical Context

**Language/Version**: Shipped deliverables are markdown (five agent definitions + one
skill with three references — design §3.1's plugin layout). Test code is Python 3 on the
slice-1 pytest harness (dev-only; Platform Constraints exempt dev tooling), importing
the real slice-2 `bb_validate` at the repo's 3.9 floor.

**Primary Dependencies**: none at runtime (no runtime code ships); pytest dev-only;
slice-2 `bin/bb_validate.py` as the enforcement authority the schemas reference
documents; `manifest/capabilities.json` (slice 4, merged) as SC-006's cross-check
authority; local-state protocol v1 (`specs/002-deterministic-layer/contracts/
local-state-protocol.md`) as the role-registration and turn-cap-key authority.

**Storage**: none — this slice performs no store I/O. Documented flows cite slice-3
conventions (`skills/session-store/`) as normative retrieval/checkpoint homes; the
role-registration write targets the protocol's `agents.json` (simulated in tests
against a temp dir, never a live session).

**Testing**: contract layer (`tests/contract/`) — doc↔validator agreement (worked
examples parsed from `schemas.md` fences and classified by `bb_validate.validate()`),
role-registration shape conformance, toolset↔manifest cross-check, and the
capability-naming scan extended over the new prose surfaces. Unit layer — the
anchoring-guard state matrix (pure validator behavior, py3.9 floor, beside
`test_validate.py` — research R5). Runs under `make verify`, no credentials, no
network.

**Target Platform**: repo/CI only this slice (prose + tests); the documented agents
target the responder runtime via capabilities only (Constitution VII).

**Project Type**: plugin prose (`agents/`, `skills/investigation/`) + contract tests —
first slice to ship the `agents/` surface.

**Performance Goals**: n/a beyond the verify gate staying fast (all new tests are
in-memory document parsing + pure-function validation; milliseconds).

**Constraints**: prose and tests only (FR-014); capability/operation names only, zero
concrete MCP server/tool names (FR-013, SC-005); every documented example classified by
the real validator exactly as documented (SC-002); the skill instructs, the
deterministic layer enforces — no prose may claim self-enforcement (FR-006, FR-010).

**Scale/Scope**: 5 agent definitions + 1 SKILL.md + 3 reference docs; 4 contract-test
modules + 1 unit-test module; 1 reconciling edit to design §5.4's example ledger
(research R8); packaging coverage verified (existing globs already cover the new dirs
— research R11).

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Deliverables are agent/skill markdown + tests; no code beyond tests (FR-014). The validator/hooks/store the prose cites are prior slices' |
| II — Deterministic Backstops | ✅ The slice's core move: every skill-stated invariant names its deterministic enforcer (validator at checkpoint-write, turn-cap hook, fail-open registration rule) and never re-claims enforcement in prose (FR-002, FR-006, FR-010) |
| III — Layered Guardrails | ✅ Injection hardening stated explicitly as probabilistic mitigation (FR-004, D-20); guarantees attributed only to deterministic layers; mutations documented approval-gated (FR-007) |
| IV — Evidence Links+Excerpts | ✅ `{url, excerpt}` is the evidence rule across skill, schemas, findings, briefing (FR-003, FR-005, FR-008); prose-only evidence appears only in documented-invalid examples, and the validator agreement test proves the doc means it |
| V — Causal Fields Human-Curated | ✅ Briefing reference carries the causal-field proposal discipline (FR-005); ledger syntheses labeled proposals |
| VI — Validated Memory | ✅ The headline: validation discipline leads the skill (FR-001); provenance vocabulary, VALIDATED/INVALIDATED, and the phase-scoped anchoring guard documented exactly as the merged validator enforces them (FR-002, SC-004) |
| VII — Capability Contracts | ✅ FR-013 + SC-005: the slice-3/4 scan mechanism extends over `agents/` and `skills/investigation/`; SC-006 cross-checks every toolset capability against the merged manifest |
| VIII — Test-First, Agent-Led | ✅ Prose and its tests land in the same change; FR-012 maps the test surface; SC-001 maps every FR to ≥1 test; all assertions on artifacts (parsed docs, validator output, protocol shapes), never prose opinions |
| Platform Constraints | ✅ Nothing shipped executes; test Python is dev-only; degraded/behavioral concerns bounded out to the §10 scenario harness |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/006-investigation-agents/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R1–R12 plan-time pins (locations, formats, mechanisms)
├── data-model.md                    # schema field tables, vocabularies, phase model, registration shape
├── quickstart.md                    # validation scenarios mapped to test modules
├── checklists/requirements.md
└── tasks.md                         # Phase 2 (/speckit-tasks)
```

No `specs/…/contracts/` directory (slice-3 precedent): this slice's contract artifacts
ARE the deliverable prose (`skills/investigation/references/schemas.md` is the normative
schema statement; the agent definitions are the role contracts) — duplicating them under
`specs/` would create a second source of truth for exactly the content FR-001–FR-011
pin. The cross-slice contracts this slice consumes (local-state protocol, capability
manifest, session-store conventions) are cited in place, never copied.

### Source Code (repository root)

```text
agents/
├── triage.md                        # FR-006: model class, ≤2-min target + turn cap
│                                    #   (default 15, key budgets.triageTurnCap, hook-
│                                    #   enforced), 4 questions, read-only capability
│                                    #   toolset, input contract, bb.verdict.v1 output,
│                                    #   truncation ⇒ FR-5f(a), re-invocation charter
├── deep-investigator.md             # FR-007: frontier class, open budget, approval-gated
│                                    #   mutations, ledger ownership + checkpoint gate,
│                                    #   seed-from-verdict, ≥1 fresh before deep-dive,
│                                    #   ledger-updates-only reporting
├── log-diver.md                     # FR-008: single purpose, read-only, parallel,
├── deploy-analyst.md                #   findings to deep investigator only,
└── dependency-checker.md            #   {url, excerpt} per finding

skills/investigation/
├── SKILL.md                         # FR-001/002/004/009/010: validation discipline first,
│                                    #   anchoring guard (validator phase scoping),
│                                    #   untrusted-data rule, launch conditions,
│                                    #   spawn/role registration + mechanism/policy split
└── references/
    ├── schemas.md                   # FR-011: normative bb.verdict.v1 + bb.ledger.v1,
    │                                #   marker-tagged worked examples (valid + invalid,
    │                                #   rule-named) — the consistency test's parse target
    ├── briefing.md                  # FR-005: briefing format, deep-linked evidence per
    │                                #   claim, causal-field proposal discipline
    └── retrieval.md                 # FR-005: pointer to slice-3's normative retrieval
                                     #   conventions — consumes, never restates

bb-technical-design.md               # research R8: §5.4 example ledger reconciled to
                                     #   pass the merged validator (flagged by spec)

tests/contract/
├── test_schemas_reference.py        # SC-002: every marker-tagged example classified by
│                                    #   bb_validate exactly as documented; vocabulary/
│                                    #   constant agreement (phases, invariant phases,
│                                    #   provenance, validation, min-live, version tags)
├── test_role_registration.py        # SC-003: simulated spawn write conforms to the
│                                    #   protocol agents.json shape; role vocabulary
│                                    #   derived from shipped agent docs; bad role
│                                    #   rejected
├── test_agent_toolsets.py           # SC-006 + FR-006/007/008 pinned-property
│                                    #   inspection: toolset tables parse, capabilities ⊆
│                                    #   manifest, triage set exact, read-only markings
└── test_investigation_prose.py      # SC-005 + FR-001/002/004/009 doc-structure gates:
                                     #   naming scan over agents/ + skills/investigation/
                                     #   (slice-3/4 mechanism extended), discipline-first
                                     #   ordering, launch conditions, enforcement
                                     #   attribution phrases

tests/unit/test_anchoring_matrix.py  # SC-004 (unit layer — pure validator behavior,
                                     #   py3.9 floor, beside test_validate.py): both
                                     #   invariant phases × {2 live, 3 live none fresh,
                                     #   3 live with fresh, dead fresh} + early-phase
                                     #   sparse-ledger legality
```

**Structure Decision**: `agents/` and `skills/investigation/` match design §3.1's plugin
layout exactly. `references/retrieval.md` ships as a pointer (spec assumption: slice 3
made session-store the normative home). Contract tests extend `tests/contract/` in
place, reusing the slice-3 scan mechanism (`test_skill_capability_naming.py`'s public
constants) and the slice-1 conftest helpers; all new Python is dev-only test code.

## Complexity Tracking

Not required — Constitution Check passed without violations.
