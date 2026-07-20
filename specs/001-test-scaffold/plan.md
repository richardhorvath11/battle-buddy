# Implementation Plan: Test Scaffold & Mock MCP

**Branch**: `001-test-scaffold` | **Date**: 2026-07-19 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-test-scaffold/spec.md`

## Summary

Build the hermetic test harness that precedes all component code: pytest scaffold with two
layers (unit, contract) behind the existing `make verify` gate, and `bb-mock-mcp` — an
in-process, stdlib-only Python package that executes the operation contract from a
committed machine-readable contract file, exposes a schema registry for binding-resolution
tests (FR-011), records an ordered write log, and loads declarative seed fixtures. CI
mirrors the same make targets on every PR.

## Technical Context

**Language/Version**: Python — dev tooling 3.11+; unit layer additionally proven on 3.9
(shipped-code floor, design D-1; research R2)

**Primary Dependencies**: pytest (sole dev dependency); `bb-mock-mcp` itself is
stdlib-only (research R1)

**Storage**: in-memory only (per-test mock instances); no external services ever

**Testing**: pytest, table-driven via parametrize over JSON fixtures (research R3)

**Target Platform**: macOS/Linux developer machines + GitHub Actions ubuntu runners

**Project Type**: dev tooling inside the plugin repo (single project; `tests/` + `tools/`)

**Performance Goals**: full `make verify` < 30s offline (SC-002); fresh clone → green
< 5 min including dependency install (SC-001)

**Constraints**: hermetic — zero network/credentials in both layers (FR-002); mock and
tooling excluded from any shipped bundle (FR-010/SC-007)

**Scale/Scope**: slice 1 of 9 (AGENTS.md slice map); ~4 mock stores + schema registry +
seed loader; ≥1 conformance test per contract operation (SC-003)

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Everything in this slice is dev-only (`tests/`, `tools/`); nothing ships to responders; no server/DB/integration code |
| II — Deterministic Backstops | ✅ This slice *builds* the backstop layer's proving ground; nothing convention-enforced is introduced |
| III — Layered Guardrails | ✅ N/A surface (no agent tooling, no credentials); hermeticity keeps it that way |
| IV — Evidence Links+Excerpts | ✅ N/A (no evidence-producing features in scope) |
| V — Causal Fields Human-Curated | ✅ N/A |
| VI — Validated Memory | ✅ N/A (enforcement arrives with `bb-validate`, slice 2) |
| VII — Capability Contracts | ✅ Strengthened: the contract becomes a machine-readable committed artifact (research R5); mock/tests reference operations, never tool names |
| VIII — Test-First, Agent-Led | ✅ This slice *is* the mandate; mock code lands with its own conformance tests in the same PR |
| Platform Constraints | ✅ Shipped-code stdlib rule untouched (nothing shipped); dev-only exemption exercised as intended |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-test-scaffold/
├── spec.md
├── plan.md              # this file
├── research.md          # Phase 0 — decisions R1–R7
├── data-model.md        # Phase 1 — mock entities, write log, seed schema
├── quickstart.md        # Phase 1 — validation guide
├── contracts/
│   └── operations.md    # Phase 1 — operation contract v1, concrete shapes
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
tools/
└── bb-mock-mcp/
    ├── contract.json            # machine-readable operation contract (from contracts/operations.md)
    ├── bb_mock_mcp/
    │   ├── __init__.py          # MockMcp facade: capabilities, describe(), seed loading, write log
    │   ├── stores.py            # MockRecordStore, MockArtifactStore, MockDiary, MockAlerting
    │   ├── schema.py            # SchemaRegistry: contract.json loader + describe() (FR-011)
    │   └── errors.py            # uniform error shape: {error: {op, code, message}}
    └── README.md                # dev-only notice + pointer to contracts/operations.md

tests/
├── conftest.py                  # fresh-mock factory fixture; fixture-loading helpers
├── unit/
│   ├── test_harness_selftest.py # table-driven pattern demo: (payload, state) -> (exit, output)
│   └── test_packaging.py        # FR-010/SC-007 bundle-boundary check (fixture-driven, R7)
├── contract/
│   ├── test_storage.py          # conformance per storage op incl. D-3 limit + errors
│   ├── test_artifacts.py
│   ├── test_diary.py            # incl. most-recent-first ordering (§6.2)
│   ├── test_alerting.py
│   ├── test_schema_registry.py  # FR-011 / Story 2 AS-5
│   ├── test_write_ordering.py   # cross-capability ordering demo (SC-004)
│   ├── test_rejections.py       # seeded-defect corpus: ≥1 violation per op (SC-006)
│   └── test_seeds.py            # Story 3: seed load, corrupted-seed failure
├── helpers/
│   └── assertions.py            # FR-008 artifact-assertion entry point (T022)
└── fixtures/
    ├── seeds/synthetic-incident.json
    ├── seeds/corrupted.json
    ├── packaging/intended-bundle.json
    ├── packaging/mis-packaged.json
    └── unit/…                   # table-driven payload fixtures

.github/workflows/verify.yml     # unit (3.9 + 3.12 matrix) + contract (3.12); mirrors make targets (R4)
Makefile                         # existing targets gain real content; green-but-loud empty-layer rule preserved
```

**Structure Decision**: single project; dev tooling under `tools/`, all tests under
`tests/` split by layer, fixtures shared. Matches AGENTS.md path tiers (everything in the
Allowed tier) and the design §10 repo-layout sketch.

## Complexity Tracking

Not required — Constitution Check passed without violations.
