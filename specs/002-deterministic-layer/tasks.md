# Tasks: Deterministic Layer

**Input**: Design documents from `/specs/002-deterministic-layer/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/local-state-protocol.md, quickstart.md — and slice 1's implementation (merged, PR #6: pytest harness, CI matrix, `tests/helpers/`, packaging fixtures; this branch is synced onto it)

**Tests**: Constitution VIII — every component lands with its table-driven tests in the same task.

**Organization**: By user story. US1 (deny), US2 (validator), US3 (fingerprint) are P1 and mutually independent once the foundational tasks land; US4 (trace hook) and US5 (session guard) are P2. US4's tripwire and US1's credential-scan context rule both touch the trace protocol, so the protocol contract is foundational.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [X] T001 Create shipped-tree skeleton per plan.md: `hooks/` (empty `hooks.json`), `bin/`, fixture directories `tests/fixtures/{misbehaviors,benign,faults,outcomes,tripwire,markers,sessions,validate,fingerprint}/`
- [X] T002 [P] Add `tests/unit/test_stdlib_boundary.py`: walks `hooks/` + `bin/`, asserts stdlib-only imports (SC-006; extends slice-1 packaging boundary); passes trivially on the empty skeleton and gates everything after

## Phase 2: Foundational (blocking all stories)

- [ ] T003 Implement `hooks/_config.py` ConfigView per research R6 (turn cap default 15, bindings, config-presence; malformed ⇒ absent) + table-driven tests in `tests/unit/test_config_view.py` — every hook consumes this
- [ ] T004 Implement `hooks/_state.py` — the local-state protocol helpers consumed by all three hooks: flock-guarded `counters.json` (atomic seq assignment; per-actor turn counts checked-at-Pre / incremented-at-Post per protocol finding-A resolution), trace append (append-only, appender never reads), 10-line tail read for consumers, marker read, actor-key derivation from transcript_path (R10), `agents.json` role lookup — matching `contracts/local-state-protocol.md` exactly. **First, a cheap runtime probe (fixture-recorded): confirm the hook payload's `transcript_path` is distinct per agent instance (subagent vs main); if not, R10's actor key needs a different signal — record the finding before building on it.** Write `tests/unit/test_local_state_protocol.py` with one test per protocol-doc assertion (FR-013 acceptance), including the parallel-append concurrency case (multiprocessing writers → unique, gap-free-absent-crash, monotonic seq per R11)
- [ ] T005 [P] Author the fault corpus `tests/fixtures/faults/*.json` (malformed stdin, truncated JSON, unreadable state dir, seeded exception trigger) + shared fail-open runner `tests/helpers/failopen.py` asserting allow/proceed + visible diagnostics (SC-007) — reused by every hook's test file

**Checkpoint**: protocol pinned and tested; config + state helpers green

## Phase 3: User Story 1 — Deny hook (P1)

**Goal**: Four deny classes, corpus-gated, fail-open
**Independent Test**: two-corpus run + fault corpus, no agent involved (spec US1)

- [ ] T006 [US1] Implement `hooks/guardrail_deny.py`: DENY_CLASSES table (destructive_filesystem, destructive_infra, verify_skip pattern classes), stdin→verdict flow, fail-open wrapper, block messages naming the class, and on every block append the `denied:guardrail:<class>` trace line via `_state.py` (protocol: one line per tool call incl. blocked ones); register in `hooks/hooks.json` (PreToolUse)
- [ ] T007 [US1] Add the credential_scan class with its context rule: `error:auth` within the protocol's 10-line trace window (reads via `_state.py` tail; degrades to pattern-only when no trace exists per spec Assumption)
- [ ] T008 [P] [US1] Author the misbehavior corpus `tests/fixtures/misbehaviors/*.json` — ≥3 source-annotated fixtures per deny class (documented real-world agentic misbehaviors) — and the benign corpus `tests/fixtures/benign/*.json` per the US1 AS-2 membership rule (incl. quoted `rm -rf` in commit message, URL containing dangerous string)
- [ ] T009 [US1] Write `tests/unit/test_guardrail_deny.py`: iterate both corpora (SC-001), context-rule cases (auth window present/absent/stale), fault corpus (fail-open), block-message content

**Checkpoint**: US1 deliverable — the misbehavior gate is live in CI

## Phase 4: User Story 2 — bb-validate (P1)

**Goal**: Schema + semantic invariants, one-pass machine-readable errors
**Independent Test**: violation corpus classified 100% correctly (spec US2)

- [ ] T010 [US2] Implement `bin/bb_validate.py` + `bin/bb-validate` CLI shim: version-tag dispatch (`bb.verdict.v1`, `bb.ledger.v1`), schema shape checks, semantic invariants (validation status on non-fresh; ≥3 live + ≥1 fresh when `phase` ∈ {evidence-gathering, deep-dive} per R9; `{url, excerpt}` evidence), one-pass JSON-lines violation output, exit codes 0/1/2, input never modified
- [ ] T011 [P] [US2] Author `tests/fixtures/validate/*.json`: ≥1 violating document per schema rule and per semantic invariant, multi-violation document, valid verdict + ledger documents, non-JSON input, `schema_valid: false` pre-flagged document (validates like any other)
- [ ] T012 [US2] Write `tests/unit/test_validate.py`: corpus classification (SC-004), one-pass completeness on the multi-violation document, byte-identity of valid inputs, decisive termination on garbage

**Checkpoint**: Constitution VI has its enforcement mechanism

## Phase 5: User Story 3 — bb-fingerprint (P1)

**Goal**: One implementation, versioned rules, golden corpus
**Independent Test**: corpus on both matrix ends + rule-change tripwire (spec US3)

- [ ] T013 [US3] Implement `bin/bb_fingerprint.py` + `bin/bb-fingerprint` CLI shim: §5.2 normalization (lowercase/trim/collapse; alert-type volatile-token placeholders: UUID, hex≥8, int≥3, ISO timestamp, hostname/IP), sha256 16-hex truncation, `bb.fp.v1` version in output metadata, deterministic flagged outputs for empty/all-volatile inputs
- [ ] T014 [P] [US3] Author `tests/fixtures/fingerprint/golden.json`: unicode, messy whitespace, each volatile-token type, near-collisions, empty/all-volatile edge cases — the executable form of the rules
- [ ] T015 [US3] Write `tests/unit/test_fingerprint.py`: golden corpus 100% (runs on both CI matrix versions by virtue of the slice-1 workflow), determinism across repeated calls, seeded rule-change failure demo (SC-003)

**Checkpoint**: all three P1 stories deliverable

## Phase 6: User Story 4 — Trace hook (P2)

**Goal**: Complete capture with outcomes, turn cap, tripwire
**Independent Test**: scripted 100-call session + cap + tripwire fixtures (spec US4)

- [ ] T016 [US4] Implement `hooks/tool_trace.py` PostToolUse path: trace-line append per protocol (seq, agent, tool, capability from bindings, at, summary, outcome via R4 classifier); register in `hooks.json`
- [ ] T017 [US4] Implement PreToolUse path: per-actor turn count from `counters.json` (never trace scans), actor role from `agents.json` (R10 — unregistered ⇒ uncapped, fail open), cap from ConfigView, past-cap denial with emit-your-verdict message + `denied:turn_cap` line; no separate marker (verdict fields carry FR-5f(a) semantics per spec FR-009)
- [ ] T018 [US4] Implement the tripwire: R5 regex families over untrusted-capability results (bindings-classified; set v1 = alerting, observability), one advisory + one tripwire trace event per trip; no-binding-map ⇒ disabled with one notice per session
- [ ] T019 [P] [US4] Author fixtures: `tests/fixtures/outcomes/*.json` (R4 classifier pairs), `tests/fixtures/tripwire/*.json` (trip/no-trip per family + no-binding-map case), and `tests/fixtures/sessions/hundred-call.json` (the scripted multi-agent session, SC-005)
- [ ] T020 [US4] Write `tests/unit/test_tool_trace.py`: SC-005 (100 lines, ordered, no dupes; N+1 denied), outcome classification, tripwire incl. degraded mode, fault corpus (fail-open)

## Phase 7: User Story 5 — Session guard (P2)

**Goal**: Unpersisted-record detection, transcript staging, config warning
**Independent Test**: four marker states + transcript + config fixtures (spec US5)

- [ ] T021 [US5] Implement `hooks/session_guard.py`: **SessionEnd** marker check (present ⇒ warn with remedial instruction; deletion = cleared per protocol — SessionEnd not Stop, so a legitimately-open session isn't nagged every turn, per protocol doc's event-binding note), transcript copy to `staging/` with degrade-to-notice, SessionStart config-presence warning (FR-015, non-blocking); register both events in `hooks.json`
- [ ] T022 [P] [US5] Author `tests/fixtures/markers/*.json`: absent / open-unconfirmed / open-confirmed-never-closed / cleared, plus transcript-present/missing/unreadable and config-present/absent payloads
- [ ] T023 [US5] Write `tests/unit/test_session_guard.py`: warnings on exactly the two present states (US5 Independent Test), staging behavior, FR-015 warning, fault corpus (fail-open)

## Phase 8: Polish & Cross-Cutting

- [ ] T024 [P] Write `tests/unit/test_hook_latency.py`: R8 timing tripwire — p95 < 100ms over 100 invocations per hook entry (SC-002)
- [ ] T025 [P] Confirm `tests/fixtures/packaging/intended-bundle.json` (merged in slice 1) already lists `hooks/**` + `bin/**` (it does); the real work is a shipped-side exclusion case proving `tests/`, `tools/`, and `.bb-session/` never appear in the bundle — extend `tests/unit/test_packaging.py` accordingly (SC-006 from the shipped side)
- [ ] T026 Full quickstart walkthrough (all 10 scenarios); append validation run to `specs/002-deterministic-layer/checklists/requirements.md`

## Dependencies

```text
T001 → T002 ∥ (T003, T004, T005) → ┬→ US1: T006 → T007 → T009; T008 ∥ (after T001)
                                   ├→ US2: T010 → T012; T011 ∥
                                   ├→ US3: T013 → T015; T014 ∥
                                   ├→ US4: T016 → T017 → T018 → T020; T019 ∥
                                   └→ US5: T021 → T023; T022 ∥
T007 needs T004 (trace tail) · T016–T018 need T003+T004 · T021 needs T003+T004
Fixture→test edges (each test consumes its corpus): T008→T009 · T011→T012 · T014→T015 · T019→T020 · T022→T023
Polish: T024 after all hooks; T025 after T001; T026 last
```

## Parallel Execution Examples

- After T004: five story tracks parallel — US1–US5 touch disjoint *implementation* files, with one shared exception: `hooks/hooks.json` registration (T006, T016, T021 each add their event bindings). Treat `hooks.json` edits as append-only registration blocks to avoid a merge point, or serialize just those three touches; everything else is genuinely disjoint. Fixture-authoring tasks (T008, T011, T014, T019, T022) run parallel to their implementations.
- Max useful width: ~5 workers (one per story) + fixture authors

## Implementation Strategy

MVP = Phases 1–5 (the three P1 stories): the misbehavior gate, the validator, and the fingerprint — the components other slices consume first. US4/US5 complete the runtime hook suite; T026 closes the slice with all 10 quickstart scenarios demonstrated. Every phase checkpoint keeps `make verify` green (Constitution VIII).
