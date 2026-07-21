# Implementation Plan: Doctor & Setup

**Branch**: `004-doctor-setup` | **Date**: 2026-07-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-doctor-setup/spec.md`

## Summary

Ship the capability-verification and onboarding surface as conventions plus their
executable specification (design §7, Constitution I): the capability manifest
(`manifest/capabilities.json`, `bb.capabilities.v1` — required half projected from
operation contract v1, optional half from design §7.1), `/doctor` command prose (binding
resolution with benign read-shaped probes, config/version/shell checks, the structured
`bb.doctor.report.v1` artifact, the `bb.stamp.v1` green stamp), `/setup` command prose
(mode derivation by inspection — team / responder / already-set-up / repair — the
create-vs-validate store path, workspace scaffold, doctor + smoke test), and the two
templates. Zero shipped storage code: every runtime write goes through doctor-resolved
bindings; the only Python written lives under `tests/` — flow modules
(`doctor_flows.py`, `setup_flows.py`) that execute the documented protocols against
`bb-mock-mcp` and plan-pinned fixture surfaces. Cross-slice pins (report, stamp,
config block, probe table, scaffold set) are normative in
[`contracts/doctor-protocol.md`](contracts/doctor-protocol.md).

## Technical Context

**Language/Version**: Shipped deliverables are markdown command prose + JSON
(manifest, roster template) — plugin bundle documentation surface (design §3.1). Test
code is Python 3 on the slice-1 pytest harness (dev-only; Platform Constraints exempt dev
tooling), importing slice-3's `store_flows` constants at the repo's 3.9 floor.

**Primary Dependencies**: none at runtime (nothing shipped executes); pytest dev-only;
`bb-mock-mcp` (in-tree) as the roster/store/diary/alerting double; slice-3
`store_flows.COLUMN_NAMES` as the header authority (research R5).

**Storage**: none real — all test I/O flows through operation contract v1. Surfaces the
contract lacks (store header, shell adapter, catalog state, live rosters) are fixture
surfaces pinned in research R5/R8/R12 and `data-model.md`. New local artifact:
`.bb-doctor-stamp.json` (gitignored runtime dropping, §2.1 — outside `.bb-session/`,
which close deletes).

**Testing**: contract layer (`tests/contract/`) — resolution against roster fixtures
built from the mock's `describe()` (slice-1 FR-011), setup flows against the mock's write
log, probe outcomes against the `bb.doctor.report.v1` artifact (the oracle reads need —
FR-011), stamp lifecycle on tmp dirs. Runs under `make verify`, no credentials, no
network.

**Target Platform**: repo/CI only this slice (docs + manifest + tests); the documented
commands target the responder runtime (team-brought MCPs) without naming servers —
except the one sanctioned template (FR-010).

**Project Type**: plugin documentation (`commands/`, `manifest/`, `templates/` — first
slice to ship all three) + contract tests.

**Performance Goals**: n/a beyond the verify gate staying fast (in-memory, seconds).

**Constraints**: zero shipped storage/server code (FR-012, Constitution I); command prose
references capabilities/operations only, concrete server names in exactly one template
(FR-010); every FR exercised by ≥1 hermetic contract test (FR-011); binding-entry format
owned by local-state protocol v1, written not redefined; slice-2 config keys keep their
paths (additive `bb.config.v1`).

**Scale/Scope**: 2 command docs + 1 JSON manifest + 2 templates + 1 cross-slice contract
doc; 2 flow-helper modules + 1 fixture-surface module; ~8 contract-test modules; ~1
fixture directory; 1 `.gitignore` line.

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Deliverables are command prose, JSON manifest, templates, tests. No server, no storage code, no per-tool integration; setup/doctor write only through resolved bindings (FR-012). The flows' executable form lives in `tests/` (dev-only), the established slice-3 pattern |
| II — Deterministic Backstops | ✅ The slice *is* a backstop surface: doctor's checks, the read-back-bearing smoke test, and the stamp are deterministic verifications of convention-carried behavior. The probabilistic part (semantic matching, D-7) is explicitly fenced; tests pin the deterministic protocol around it (research R8) |
| III — Layered Guardrails | ✅ No security claims rest on this slice; probes are read-shaped/benign by pinned rule (R6); no guardrail surface touched. Malformed-config repair path is a data-safety behavior, stated as convention + test, not a guarantee |
| IV — Evidence Links+Excerpts | ✅ No evidence-bearing fields written by this slice (smoke-test row is synthetic); report `detail` strings are diagnostics, not incident evidence |
| V — Causal Fields Human-Curated | ✅ No causal fields touched; smoke-test row writes none |
| VI — Validated Memory | ✅ Not in scope — no retrieval behavior changed; smoke-test rows are excluded from retrieval by slice-3 conventions (asserted by this slice's tests) |
| VII — Capability Contracts | ✅ The slice ships Constitution VII's enforcement artifacts (manifest, doctor, binding map). FR-010 naming gate extended to `commands/`, `manifest/`, `templates/session-sheet.md`; `mcp.recommended.json` is the sanctioned sole exception (R13) |
| VIII — Test-First, Agent-Led | ✅ Docs and tests land in the same change; FR-011 maps every FR to ≥1 test; manifest-fidelity test keeps manifest ≡ contract.json mechanically; report artifact exists specifically so tests never assert on prose |
| Platform Constraints | ✅ Nothing shipped executes; test Python dev-only; secrets appear only as `${ENV_VAR}` literals; degraded path (no shell adapter) is skip-not-fail |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/004-doctor-setup/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R1–R14 plan-time pins
├── data-model.md                    # entities, shapes, fixture surfaces
├── quickstart.md                    # validation scenarios → test modules
├── contracts/
│   └── doctor-protocol.md           # cross-slice authority: report, stamp, config block,
│                                    #   probe table, resolution protocol, scaffold set
├── checklists/requirements.md
└── tasks.md                         # Phase 2 (/speckit-tasks)
```

The contracts/ doc exists (unlike slice 3) because slice 5's preflight and slice 9's
shell check consume rules no shipped file states normatively: shipped command prose is
runtime-facing restatement; `doctor-protocol.md` is the dev-side authority both cite.

### Source Code (repository root)

```text
commands/
├── doctor.md                        # FR-002–FR-005: resolution protocol, probe table,
│                                    #   checks, report artifact, stamp write; §7.2
└── setup.md                         # FR-006–FR-009: mode table, team/responder flows,
│                                    #   create-vs-validate, scaffold, smoke test; §7.3
manifest/
└── capabilities.json                # FR-001: bb.capabilities.v1 (required ≡ contract v1;
                                     #   optional from §7.1 + enables lists)
templates/
├── mcp.recommended.json             # FR-010's sole server-name location; default roster
└── session-sheet.md                 # reference doc, explicitly not the setup path

.gitignore                           # + .bb-doctor-stamp.json (R2)

tests/helpers/doctor_fixtures.py     # roster-fixture builder (from describe(), R8),
│                                    #   FixtureHeaderStore (R5), fixture shell adapter (R12)
tests/helpers/doctor_flows.py        # doctor's executable form (R9): resolve_bindings,
│                                    #   run_probes, check_config, check_versions,
│                                    #   check_shell, assemble_report, write/evaluate_stamp
tests/helpers/setup_flows.py         # setup's executable form (R9): derive_mode,
│                                    #   team_mode, responder_mode, validate_existing,
│                                    #   scaffold_workspace, smoke_test
tests/contract/
├── test_capability_manifest.py      # FR-001: schema, required-half fidelity vs
│                                    #   contract.json, optional ops + enables, get_file excluded
├── test_binding_resolution.py       # US2/SC-002: full/missing/ambiguous/drift rosters,
│                                    #   entry format parses under protocol v1 keys
├── test_doctor_checks.py            # FR-003: probe outcomes via report, header validation,
│                                    #   diary/catalog checks, version seam, shell ok/fail/skip
├── test_doctor_report.py            # FR-004: report schema, outcome rules, reduced
│                                    #   features exact lists, migrations mirror
├── test_stamp_lifecycle.py          # FR-005/SC-006: green writes 3 fields, staleness on
│                                    #   version/hash change only, missing/corrupt ⇒ stale
├── test_setup_team_mode.py          # US1/SC-003/SC-004/SC-007: sequence order, header
│                                    #   through binding, validate/mismatch zero-write,
│                                    #   scaffold file set, smoke test + retrieval exclusion
├── test_setup_responder_mode.py     # US3: probes under responder credentials, stamp,
│                                    #   team write log unchanged
├── test_setup_idempotence.py        # US4/SC-005: second run zero mutating ops, partial
│                                    #   states, malformed-config repair path
└── test_command_capability_naming.py# FR-010: naming gate over commands/, manifest/,
                                     #   templates/session-sheet.md; roster template exempt+valid
tests/fixtures/doctor/
├── config-**.json                   # valid / malformed / future-versioned blocks
└── (rosters come from doctor_fixtures.py builders — R8; catalog fixture reuses the
                                     #   existing scenario fixture surface)
```

**Structure Decision**: `commands/`, `manifest/`, `templates/` follow design §3.1's
plugin bundle layout exactly — this slice is the first to populate them. Flow modules and
fixture surfaces live in `tests/helpers/` beside slice-3's `store_flows.py` (same
executable-specification relationship; packaging test already fences `tests/`). The
cross-slice contract lives under `specs/004-doctor-setup/contracts/` mirroring slice 2's
`local-state-protocol.md` precedent, because later slices consume its rules.

## Complexity Tracking

Not required — Constitution Check passed without violations.
