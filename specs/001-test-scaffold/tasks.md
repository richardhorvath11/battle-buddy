# Tasks: Test Scaffold & Mock MCP

**Input**: Design documents from `/specs/001-test-scaffold/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/operations.md, quickstart.md

**Tests**: This slice's deliverable *is* the test harness — test tasks are the implementation, not an option (Constitution VIII).

**Organization**: By user story. US1 (verify gate) and US2 (mock) are both P1 and mutually independent: US1 completes with the unit layer alone (contract layer reports green-but-loud while empty), US2 builds the mock + conformance suite. US3 (fixtures) depends on US2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 per spec.md

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Repo skeleton and the contract artifact everything derives from

- [X] T001 Create directory skeleton per plan.md: `tools/bb-mock-mcp/bb_mock_mcp/` (empty `__init__.py`), `tests/unit/`, `tests/contract/`, `tests/fixtures/{seeds,packaging,unit}/`
- [ ] T002 Add pytest configuration (`pyproject.toml` with `[tool.pytest.ini_options]`: testpaths, `-q` defaults) and a root `tests/conftest.py` stub; document `pip install pytest` as the only dev dependency in `tools/bb-mock-mcp/README.md` placeholder
- [ ] T003 [P] Encode `specs/001-test-scaffold/contracts/operations.md` as machine-readable `tools/bb-mock-mcp/contract.json` (every capability, op, input/output field with type+required, error codes, the 45000 D-3 limit as a named constant field) — research R5: this file is the single source the mock, registry, and tests load

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The gate plumbing every story's tests run through

- [ ] T004 Implement real `test-unit` / `test-contract` Makefile targets in `Makefile`: run pytest on the layer dir; treat pytest exit 5 (no tests collected) as pass-with-visible-notice (green-but-loud rule, spec Story 1 AS-3); `verify` remains the aggregate
- [ ] T005 [P] Implement `tests/conftest.py`: `mock_mcp` factory fixture (fresh instance per test, lazy import so the unit layer never imports the mock), JSON-fixture loading helper for table-driven tests

**Checkpoint**: `make verify` runs both layers (both green-but-loud empty) — foundation ready

## Phase 3: User Story 1 — One trustworthy verify command (P1)

**Goal**: Green/red/loud verdicts, hermetic, CI-mirrored

**Independent Test**: fresh clone → `make verify` green offline in <30s; seeded defect → red naming the test; empty layer → visible notice, still green (quickstart scenarios 1, 2, 7)

- [ ] T006 [P] [US1] Table-driven unit-layer selftest demonstrating the (payload, state) → (exit code, output) pattern: `tests/unit/test_harness_selftest.py` + `tests/fixtures/unit/selftest.json` (FR-007)
- [ ] T007 [P] [US1] Gate-behavior test `tests/unit/test_verify_gate.py`: run `make test-unit` / `make test-contract` via subprocess in a temp sandbox (copied Makefile, empty/populated/failing test dirs) asserting exit codes and the green-but-loud notice text (FR-001, Story 1 AS-1..3, edge cases)
- [ ] T008 [US1] CI workflow `.github/workflows/verify.yml`: `pull_request` + push-to-`main` triggers; unit job on {3.9, 3.12} matrix, contract job on 3.12; both invoke the make targets verbatim (FR-009, research R2/R4); note in workflow comments that branch-protection required-checks must be enabled in repo settings (manual, one-time)

**Checkpoint**: US1 fully deliverable with contract layer still empty

## Phase 4: User Story 2 — Mock MCP as executable contract spec (P1)

**Goal**: The mock, behavior-identical to contract.json, with schema registry, write log, and full conformance suite

**Independent Test**: conformance suite green against the mock alone; every op covered; rejection corpus caught 100%; ordering reproducible from write log (quickstart scenarios 3, 4)

- [ ] T009 [P] [US2] Uniform error envelope `tools/bb-mock-mcp/bb_mock_mcp/errors.py`: `{error: {op, code, message}}`, codes `invalid_input|not_found|limit_exceeded|unknown_op` (contracts/operations.md)
- [ ] T010 [P] [US2] `tools/bb-mock-mcp/bb_mock_mcp/schema.py`: SchemaRegistry loading contract.json at init; `describe()` returns per-capability op schemas without invocation (FR-011)
- [ ] T011 [US2] `tools/bb-mock-mcp/bb_mock_mcp/stores.py`: MockRecordStore (insertion order, merge-update, D-3 single-field limit from contract.json), MockArtifactStore (`art://N` links), MockDiary (logical clock, most-recent-first `read_recent`), MockAlerting (seed-only, newest-first history) — per data-model.md
- [ ] T012 [US2] `tools/bb-mock-mcp/bb_mock_mcp/__init__.py` facade: `invoke(capability, op, payload)` routing with contract-shape validation before dispatch, `unknown_op` handling, ordered WriteLog on every mutating op, direct state-access properties for tests (FR-003..006)
- [ ] T013 [P] [US2] Conformance tests `tests/contract/test_storage.py`: every storage op — happy path, each documented error, D-3 limit boundary (44999/45000/45001), insertion-order reads (SC-003)
- [ ] T014 [P] [US2] Conformance tests `tests/contract/test_artifacts.py`: put/get, stable deterministic links, not_found
- [ ] T015 [P] [US2] Conformance tests `tests/contract/test_diary.py`: append→link, `read_recent` most-recent-first (§6.2), n≥1 validation
- [ ] T016 [P] [US2] Conformance tests `tests/contract/test_alerting.py`: seeded `get_alert`, `list_alert_history` filters newest-first, not_found
- [ ] T017 [P] [US2] `tests/contract/test_schema_registry.py`: `describe()` enumerates every contract op with shapes, zero invocations beforehand; a binding-resolution-style matcher exercise (Story 2 AS-5, FR-011)
- [ ] T018 [P] [US2] `tests/contract/test_write_ordering.py`: scripted diary→artifact→record sequence reproduced exactly from write log; interleaved two-actor writes deterministic (Story 2 AS-3/AS-4, SC-004)
- [ ] T019 [US2] Rejection corpus `tests/contract/test_rejections.py`: ≥1 deliberately violating call per required operation (parametrized table), each caught with the violated expectation named (FR-004, SC-006)

**Checkpoint**: both P1 stories deliverable — this is the MVP of the slice

## Phase 5: User Story 3 — Fixtures & artifact assertions (P2)

**Goal**: Seed-fixture convention + assertion entry point for future scenario tests

**Independent Test**: synthetic-incident seed loads exactly; corrupted seed fails naming the entry (quickstart scenario 5)

- [ ] T020 [US3] Seed loader on the facade: `load_seed(path)` — all-or-nothing, offending entry named on failure, seeds bypass the write log (data-model.md SeedFixture)
- [ ] T021 [P] [US3] Fixtures `tests/fixtures/seeds/synthetic-incident.json` (alert + flap history + two prior session records, one fingerprint-matching) and `tests/fixtures/seeds/corrupted.json`
- [ ] T022 [US3] Assertion entry point `tests/helpers/assertions.py` (`assert_seeded_state`, `assert_write_sequence` — structural checks only, never prose) + `tests/contract/test_seeds.py` exercising both fixtures (Story 3 AS-1/AS-2)

## Phase 6: Polish & Cross-Cutting

- [ ] T023 [P] Packaging boundary check `tests/unit/test_packaging.py` + `tests/fixtures/packaging/{intended-bundle,mis-packaged}.json`: intended passes, mis-packaged fails (FR-010, SC-007, research R7)
- [ ] T024 [P] `tools/bb-mock-mcp/README.md`: dev-only notice, pointer to contracts/operations.md, one-paragraph usage
- [ ] T025 Full quickstart walkthrough (all 7 scenarios) including offline run and <30s timing (SC-001/SC-002); append validation run to `specs/001-test-scaffold/checklists/requirements.md`

## Dependencies

```text
Phase 1 (T001–T003) → Phase 2 (T004–T005) → ┬→ US1 (T006–T008) ──────────┐
                                            └→ US2 (T009–T019) → US3 (T020–T022) → Polish (T023–T025)
US1 ∥ US2 (fully independent); T011 needs T009+T010; T012 needs T011; T013–T019 need T012; T022 needs T020+T021
```

## Parallel Execution Examples

- After T005: T006, T007 (US1) alongside T009, T010 (US2) — four workers, no shared files
- After T012: T013–T018 all parallel (one conformance file each); T019 after any one of them establishes the pattern
- Polish: T023, T024 parallel; T025 last (it validates everything)

## Implementation Strategy

MVP = Phases 1–4 (both P1 stories): the gate is real and the mock is proven — slice 2 can start against it. US3 + Polish complete the slice's definition of done (SC-001..007 all demonstrated by T025). Each phase checkpoint leaves `make verify` green — no task may be marked done with a red gate (Constitution VIII).
