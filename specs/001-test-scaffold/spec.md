# Feature Specification: Test Scaffold & Mock MCP

**Feature Branch**: `001-test-scaffold`

**Created**: 2026-07-19

**Status**: Draft

**Input**: Slice 1 of the battle-buddy MVP (design `bb-technical-design.md` §10, §7.1; Constitution VIII): the hermetic test harness that precedes all component code — the two required test layers behind one verify command, and `bb-mock-mcp`, the in-memory executable specification of the operation contract.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One trustworthy verify command (Priority: P1)

A contributor (human or coding agent) working on any battle-buddy change runs a single command and gets a reliable red/green verdict in seconds — with no credentials, no network, and no external services. Green means the change respects every tested invariant; red points at the specific violation. This is the standing guardrail that keeps agent-written changes honest (Constitution VIII), so it must exist before any component code does.

**Why this priority**: Every subsequent slice is developed against this gate. Without it, agent-led development has no mechanical honesty check and convention violations ship silently.

**Independent Test**: On a fresh clone with only dev tooling installed, run the verify command; it completes green, quickly, offline. Introduce a deliberate defect in a tested unit; the command goes red and names the failing case.

**Acceptance Scenarios**:

1. **Given** a fresh clone with dev dependencies installed and no network access, **When** the contributor runs the verify command, **Then** both test layers execute and the command exits green.
2. **Given** a change that breaks a tested invariant, **When** the contributor runs the verify command, **Then** it exits non-zero and the failure output identifies the specific test and expectation that failed.
3. **Given** a repository state where a test layer's directory does not yet contain tests for a future component, **When** verify runs, **Then** it reports the absence visibly and treats the empty layer as passing (green-but-loud — the gate's strictness grows as layers gain tests), while still evaluating all tests that do exist.

---

### User Story 2 - Mock MCP as the contract's executable specification (Priority: P1)

A contributor implementing or integrating against the operation contract (design §7.1) tests against `bb-mock-mcp`: an in-memory stand-in for the entire external service layer (record store, artifact store, diary, alerting). The mock behaves exactly as the contract prescribes — every required operation is supported, contract-violating calls are rejected — so a test passing against the mock means the caller honors the contract. The mock additionally records the sequence of write operations, making ordering rules (e.g. diary-before-record) assertable.

**Why this priority**: Co-equal with Story 1 — the contract layer is what makes integration behavior testable hermetically, and later slices (session store, lifecycle, doctor) cannot be built test-first without it. The mock encodes the same contract expectations that `/doctor`'s probes later check against real rosters (Constitution VII — `/doctor`, not the mock, is the judge of real integrations).

**Independent Test**: Run the contract conformance suite against the mock alone: every required operation has at least one passing conformance case, invalid calls are rejected with descriptive errors, and a scripted multi-write sequence is reproduced in exact order from the mock's write log.

**Acceptance Scenarios**:

1. **Given** the mock in a clean state, **When** a test exercises each required operation of every required capability, **Then** each operation behaves per the contract (records persist and are readable; artifact writes return stable link identifiers; diary entries append and are retrievable most recent first per the contract's `read_recent` ordering, design §6.2; seeded alerts are readable by id and their history listable).
2. **Given** a call that violates the contract (unknown operation, missing required field, malformed record), **When** it reaches the mock, **Then** the mock rejects it with an error naming the violated expectation, rather than silently accepting or coercing it.
3. **Given** a test scenario performing writes across capabilities in a prescribed order, **When** the scenario completes, **Then** the mock's write log reproduces the exact operation sequence so ordering invariants can be asserted.
4. **Given** two simulated actors writing to the same record, **When** their operations interleave, **Then** the mock preserves both actors' operations in the log and final state deterministically, so ownership-conflict behavior can be tested.
5. **Given** the mock with no operations yet invoked, **When** a test enumerates its per-capability tool-schema surface, **Then** every required operation's name and input/output shape is discoverable without invoking it, sufficient for a binding-resolution test to match operations to tools (FR-011).

---

### User Story 3 - Fixtures and artifact assertions for future scenario tests (Priority: P2)

A contributor preparing agent-behavior tests (later slices) finds a fixture layout and an artifact-assertion entry point already established: synthetic incident fixtures (alert, catalog data, pre-seeded session records) and a deterministic assertion script that inspects mock state after a run and passes/fails on structural invariants — never on prose. Slice 1 ships the foundation (layout, seed-loading, the assertion tool's skeleton with initial checks); full scenario coverage arrives with the slices that produce the artifacts.

**Why this priority**: Valuable but not blocking — slices 2–4 need only Stories 1–2. Establishing the layout now prevents each later slice from inventing its own fixture conventions.

**Independent Test**: Load a seed fixture into the mock, run the assertion tool, and confirm it verifies the seeded state (present records, expected fields) and fails informatively when the fixture is corrupted.

**Acceptance Scenarios**:

1. **Given** a seed fixture describing pre-existing session records, **When** it is loaded into the mock, **Then** the mock contains exactly the seeded state and the assertion tool confirms it.
2. **Given** a deliberately malformed fixture, **When** loading is attempted, **Then** the failure names the offending entry rather than partially loading silently.

---

### Edge Cases

- Verify is run on a machine with no network: everything must still pass (hermeticity is a hard property, not a convenience).
- A test layer directory exists but contains zero tests: verify surfaces this visibly and passes (same green-but-loud rule as Story 1 AS-3) — never a silent green, never a hard failure for emptiness alone.
- The mock is asked for state it never stored (unknown record, unknown artifact link): it returns a not-found outcome distinguishable from an error in the mock itself.
- Write-log queries during an in-progress scenario: the log reflects all operations completed so far, in order.
- Very large record payloads: the design's cell-size guard (design §5.4, D-3: ~45k chars, with overflow diverted by the *caller* to an artifact pointer) is caller-side convention, not store behavior — so the mock emulates a store-side limit by rejecting any single field above the D-3 guard threshold (45,000 characters), making the caller's overflow handling testable in later slices. (This rejection is deliberate extra-contractual emulation of the real store, not a §7.1 contract rule.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A single verify command MUST run both required test layers (unit and contract) and exit zero only when all present tests pass. *(Design §10; Constitution VIII)*
- **FR-002**: Both layers MUST be hermetic: no network access, no credentials, no external services required or contacted. *(Design §10)*
- **FR-003**: `bb-mock-mcp` MUST implement every required operation of every required capability in the operation contract — storage (`append_record`, `read_records(filter)`, `update_record(fields)`), artifacts (`put_file → link`), diary (`append_entry → link`, `read_recent(n)`), and alerting (`get_alert(id)`, `list_alert_history(filter)`) — with behavior matching the contract's documented semantics. *(Design §7.1; the enumeration here mirrors the contract and the contract wins if they ever diverge)*
- **FR-004**: The mock MUST reject contract-violating calls with errors that name the violated expectation. *(Story 2; the mock is the contract's executable specification)*
- **FR-005**: The mock MUST record every write operation in an inspectable, ordered write log scoped per test. *(Design §10 — ordering assertions)*
- **FR-006**: The mock's full state MUST be inspectable by test code after (and during) a run without going through the contract operations themselves. *(Artifact-assertion requirement)*
- **FR-007**: The unit layer MUST support table-driven fixture tests for pure functions of the form (input payload, local state) → (exit code, output), matching how the deterministic-layer components are specified. *(Design §10 layer 1)*
- **FR-008**: The scaffold MUST establish the fixture layout and seed-loading path for scenario tests, including at least one synthetic incident seed and an assertion entry point that validates seeded mock state. *(Story 3)*
- **FR-009**: Continuous integration MUST run both layers on every proposed change and block merge on failure. *(Design §10: "CI: layers 1–2 on every PR"; §1 build order)*
- **FR-010**: The mock and all test tooling MUST be dev-only artifacts, excluded from anything shipped to responders — verified mechanically by a packaging check that the shipped plugin bundle enumerates no test, mock, or tooling paths. *(Constitution I, Platform Constraints; see SC-007)*
- **FR-011**: The mock MUST expose an inspectable per-capability tool-schema surface (operation names and input/output shapes discoverable without invoking them), so that binding resolution and doctor-style conformance probing (design §7.2, §10) are hermetically testable against it. *(Design §10 layer 2 explicitly lists binding resolution and the `/setup` create-vs-validate paths as hermetic targets; Story 2 AS-5)*

### Key Entities

- **Operation contract**: The published set of capability operations with input/output shapes (design §7.1). Slice 1 treats it as the authority the mock executes; the contract document itself is maintained with the design.
- **Mock record store**: In-memory table of session-record-shaped rows; supports append, filtered read, field update; preserves insertion order and deterministic final state — which, with the write log, is sufficient for conflict tests.
- **Mock artifact store**: In-memory file store keyed by stable generated links; supports put and read-back.
- **Mock diary**: Ordered entry list; supports append (returning a link) and recent-N read, most recent first (design §6.2).
- **Mock alerting**: Seeded alert set; supports alert read by id and alert-history listing with filters (the triage "is it real?" data path).
- **Write log**: Ordered record of every mutating operation across all mock stores: operation name, capability, payload summary, sequence number.
- **Seed fixture**: A declarative description of pre-existing state (records, artifacts, diary entries, alerts and their history) loadable into a clean mock.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fresh clone, a contributor reaches a green verify run in under 5 minutes including dev-dependency installation, with zero credentials or service accounts provisioned.
- **SC-002**: A full verify run completes in under 30 seconds on a typical developer laptop, offline.
- **SC-003**: Every required operation in the operation contract has at least one conformance test that fails if the mock's behavior diverges from the contract's documented semantics — coverage is 100% of required operations at slice completion.
- **SC-004**: Write-ordering rules are assertable: a test can verify an exact cross-capability write sequence, demonstrated by at least one passing ordering test.
- **SC-005**: Every proposed change to the repository is automatically gated: CI runs both layers and a failing layer blocks merge.
- **SC-006**: The suite is validated against a defined seeded-defect corpus — at minimum one deliberately introduced contract violation per required operation, authored alongside the suite — and the contract layer catches 100% of that corpus without human code-reading.
- **SC-007**: The dev-only boundary is mechanically verified: the packaging check (FR-010) fails if any test, mock, or tooling path appears in the shipped plugin bundle, demonstrated by a deliberately mis-packaged fixture case.

## Assumptions

- The operation contract's required capabilities and operations are as defined in design §7.1 at time of writing (storage, artifacts, diary, alerting required; code and observability optional). Contract changes flow through the design doc first; the mock then tracks them.
- Dev-only dependencies (test runner, tooling) are permitted without limit by the Constitution's Platform Constraints; only shipped code is bound to the no-install rule.
- Scenario *drivers* (interactive or headless execution of real agent sessions) are out of scope for this slice — only the fixture layout and artifact assertions land here (design §10 defines drivers as swappable and later).
- Optional-capability operations (code, observability) may be added to the mock opportunistically but are not required for slice completion.
- CI runs on the project's hosted git platform (GitHub, per the newly configured remote); workflow specifics are a plan-level choice.
