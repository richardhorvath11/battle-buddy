# Tasks: Doctor & Setup

**Input**: Design documents from `/specs/004-doctor-setup/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R14), data-model.md,
contracts/doctor-protocol.md, quickstart.md

**Tests**: REQUIRED — Constitution VIII (code without its tests in the same change is
incomplete) and FR-011 (every requirement exercised by ≥1 hermetic contract test). Doc
and test tasks are paired inside each story; a story's checkpoint is `make verify` green.

**Organization**: By user story in dependency order: US2 (doctor — P1) precedes US1
(setup — P1) because team-mode setup *ends by invoking* doctor + smoke test; then US3
(responder/stamp — P2), US4 (idempotence — P2).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 per spec.md

## Phase 1: Setup

**Purpose**: The bundle directories this slice is first to populate, and the new runtime
dropping's ignore line.

- [ ] T001 Create `commands/`, `manifest/`, `templates/`, `tests/fixtures/doctor/`
      directories; add `.bb-doctor-stamp.json` to `.gitignore` under the runtime-droppings
      section (research R2)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The capability manifest (every resolution path's input) and the fixture
surfaces every story's tests drive — plus the fidelity gate that keeps the manifest
mechanically equal to operation contract v1.

**⚠️ CRITICAL**: No user story work until this phase is complete.

- [ ] T002 Write `manifest/capabilities.json` (`bb.capabilities.v1`): required half
      projected from `tools/bb-mock-mcp/contract.json` (storage/artifacts/diary/alerting
      ops with input/output shapes; `artifacts.get_file` excluded as test-only —
      contracts/doctor-protocol.md), optional half from design §7.1 (`code`:
      `read_file`/`list_commits`/`search`; `observability`: `query_metrics`/`search_logs`)
      with shapes and `enables` lists (R7)
- [ ] T003 [P] Write `tests/contract/test_capability_manifest.py`: schema field, required
      half ≡ contract.json capability/op/shape fidelity (both directions), `get_file`
      absent, optional ops + exact `enables` lists present (FR-001)
- [ ] T004 [P] Create `tests/helpers/doctor_fixtures.py`: roster-fixture builder pulling
      op shapes from `mock.describe()` and assigning fixture tool names (R8);
      `FixtureHeaderStore` (ordered `header` cells or `None`, write log; header
      representation = `store_flows.COLUMN_NAMES` + `bb.schema.v1` sentinel — R5);
      fixture shell adapter (answering / raising / absent — R12); config-block fixture
      loaders. Scenario rosters as data or builders: full, missing-one-required,
      multi-match, with-optional, drifted
- [ ] T005 [P] Create `tests/fixtures/doctor/` config-block fixtures: `config-valid.json`
      (full `bb.config.v1` per contracts/doctor-protocol.md incl. protocol-v1 key paths),
      `config-malformed.json` (unparseable), `config-future-version.json`
      (`configVersion`/`store.schemaVersion` bumped for seam tests)

**Checkpoint**: `make verify` green — manifest and contract v1 mechanically converged;
fixture surfaces importable.

---

## Phase 3: US2 — `/doctor` links capabilities to whatever tools the team brought (P1)

**Goal**: Resolution protocol, benign probes, verification checks, and the structured
report — the binding map lands in protocol-v1 format; failures are loud and specific.

**Independent test**: resolution against the mock's `describe()`-derived rosters; every
required op resolves; written entries parse under `capability.operation`; missing op fails
naming it; optional-missing yields the reduced-features list (spec US2).

- [ ] T006 [US2] Create `tests/helpers/doctor_flows.py` — resolution core:
      `resolve_bindings(manifest, roster, choices=None)` implementing the per-op protocol
      (match → zero⇒fail / multi⇒ambiguous-with-candidates / one-or-chosen⇒probe-or-
      schema-match → write entry `capability.op → tool_name`), `run_probes(mock)` per the
      R6 probe table, and drift re-validation
      `revalidate_bindings(bindings, roster)` flagging stale entries by name — each step
      citing contracts/doctor-protocol.md sections
- [ ] T007 [US2] Write `tests/contract/test_binding_resolution.py`: full roster ⇒ one
      entry per required op, all parsing under the protocol-v1 key format (SC-002);
      missing-op roster ⇒ loud fail naming exactly that op; multi-match ⇒ `ambiguous` +
      candidate names, no silent pick, entry written only after explicit choice; drifted
      roster ⇒ stale entries named (US2 scenarios 1/2/5)
- [ ] T008 [US2] Extend `tests/helpers/doctor_flows.py` — checks + report:
      `check_config(mock, config, header_store, catalog_path)` (store header + sentinel
      validation with exact-mismatch detail, diary readable + append schema-matched,
      catalog parseable, malformed-config repair case), `check_versions(config,
      plugin_version)` (exact-match seam, migration-string detail — R11),
      `check_shell(config, adapter)` (ok/fail/skip — R12), and
      `assemble_report(...)` → `bb.doctor.report.v1` (outcome rule, `reduced_features`
      from manifest `enables`, `migrations` mirror)
- [ ] T009 [P] [US2] Write `tests/contract/test_doctor_checks.py`: probe outcomes
      asserted via the report artifact (storage/diary/alerting probes pass on an empty
      mock — empty result is a pass; artifacts schema-match-only recorded); header
      validate pass / exact-mismatch fail with zero writes; diary + catalog checks;
      version-seam mismatch ⇒ exact migration string (US2 scenario 4); shell
      configured-answering ⇒ ok, raising ⇒ fail, absent ⇒ skip-not-failed (FR-003)
- [ ] T010 [P] [US2] Write `tests/contract/test_doctor_report.py`: report schema shape;
      one check per op and per verification; `red` iff required fail/unresolved
      ambiguous; optional-missing ⇒ `green` + exact disabled-features lists (US2
      scenario 3); `candidates` only on ambiguous; migrations mirror (FR-004)
- [ ] T011 [US2] Write `commands/doctor.md`: run-outside-incidents framing, resolution
      protocol + explicit-choice rule, R6 probe table, verification checks, report
      semantics (loud required failure / reduced features), stamp write on green
      (content + location per contracts/doctor-protocol.md), drift re-validation —
      capabilities/operations language only (FR-010), each section matching the
      doctor_flows step that executes it

**Checkpoint**: `make verify` green — US2 independently delivered.

---

## Phase 4: US1 — Empty directory to green in one command (P1)

**Goal**: Team-mode setup: full sequence, header through the just-resolved storage
binding, create-vs-validate, scaffold, doctor + smoke test.

**Independent test**: documented team-mode steps as a deterministic script against the
mock from empty fixture state; header lands through the storage binding matching the
documented columns; config written with version field; smoke test exercises all four
paths; run reported green (spec US1).

- [ ] T012 [US1] Create `tests/helpers/setup_flows.py` — team mode:
      `derive_mode(workspace)` (inspection only — no done-flag; malformed ⇒ repair),
      `team_mode(mock, workspace, roster, inputs)` running resolve → store
      create-or-validate (`create_header` writes `COLUMN_NAMES` + sentinel **through the
      resolved storage binding entry**; existing mismatched header ⇒ exact mismatch
      report, zero writes) → artifact-root establishment (config record + writability via
      smoke, R5/spec assumption) → diary/catalog prompts (inputs) → config-block write
      (`bb.config.v1`, version field) → `scaffold_workspace(tmpdir)` (four files, R10) →
      doctor + `smoke_test(mock, bindings)` (`test-bb-setup-<date>` row, append →
      put_file under `<artifactRoot><session_id>/` → append_entry → read-backs)
- [ ] T013 [P] [US1] Write `templates/mcp.recommended.json` (the FR-010 sanctioned
      server-name location: default roster covering the four required capabilities,
      tokens as `${ENV_VAR}` refs) and `templates/session-sheet.md` (manual store
      reference doc, explicitly not the setup path)
- [ ] T014 [US1] Write `tests/contract/test_setup_team_mode.py`: full-sequence order via
      write log + report; header row through storage binding matching documented columns
      exactly (SC-003 create path); existing-correct store ⇒ zero-write validation;
      mismatched store ⇒ exact mismatch, zero writes, nothing re-created (US1 scenario
      4); config block carries version field; scaffold = exactly four files, env-var-ref
      discipline, zero upstream content; smoke-test row `session_type: test` exercised
      all four paths and appears in no retrieval candidate set (SC-004 — drive slice-3
      `store_flows.retrieve_candidates` over the post-smoke store); single-invocation
      green (SC-007)
- [ ] T015 [US1] Write `commands/setup.md`: mode-derivation table (team / responder /
      already-set-up / repair — inspection only), team-mode sequence (§7.3 order),
      create-vs-validate rules, scaffold contents + git-init/push-to-private-org
      instructions, diary/catalog prompts, doctor + smoke-test finish, "green: run
      /page" / specific-failure endings — capabilities/operations language only,
      sections matching setup_flows steps

**Checkpoint**: `make verify` green — US1 independently delivered (MVP seam complete
with US2).

---

## Phase 5: US3 — A new responder self-heals on their first page (P2)

**Goal**: Responder mode (verify-under-my-credentials, no team writes) and the stamp
artifact slice 5's preflight trusts.

**Independent test**: from valid-team-scope fixture state, responder-mode run writes the
three-field stamp, team write log unchanged, report records per-op probe outcomes; stamp
invalidated by plugin-version or roster-hash change (spec US3).

- [ ] T016 [US3] Extend `tests/helpers/doctor_flows.py` — stamp:
      `roster_hash(roster_file_contents)` (16-hex SHA-256 over canonical JSON of
      `mcpServers`, env-var refs literal — R3), `write_stamp(path, plugin_version,
      roster_hash)` (`bb.stamp.v1`, written only on green outcome),
      `evaluate_stamp(path, plugin_version, roster_hash)` (stale iff either field
      differs or file missing/unparseable; `at` never expiry-checked)
- [ ] T017 [US3] Extend `tests/helpers/setup_flows.py` — responder mode:
      `responder_mode(mock, workspace, plugin_version)` verifying probes under current
      credentials, writing the stamp, creating no team resources; wire into
      `derive_mode` (config present + probes-fail-or-stamp-stale ⇒ responder)
- [ ] T018 [P] [US3] Write `tests/contract/test_stamp_lifecycle.py`: green run writes
      all three fields (SC-006); changed plugin version ⇒ stale; changed roster file ⇒
      hash differs ⇒ stale; unchanged roster ⇒ hash stable across recomputation;
      timestamp difference alone never stale; missing/corrupt file ⇒ stale; stamp path
      is workspace-root `.bb-doctor-stamp.json` and never lands in the scaffold's
      committed file set (FR-005)
- [ ] T019 [P] [US3] Write `tests/contract/test_setup_responder_mode.py`: mode selected
      by inspection from valid-team/absent-responder state; probe outcomes recorded per
      required op in the report; team write log unchanged (zero mutating ops); stamp
      written; responder-scope failure (probe fails under this responder) reported
      distinct from team-scope binding failure (edge case) (US3 scenarios 1–3, FR-008)

**Checkpoint**: `make verify` green — US3 independently delivered.

---

## Phase 6: US4 — Running setup again is always safe (P2)

**Goal**: Idempotence by inspection: already-green ⇒ validate + report with zero writes;
partial states do only what's missing; malformed config is repair, never re-create.

**Independent test**: documented flow twice from the same fixture: second run performs
zero mutating operations (write log unchanged) and reports already-green (spec US4).

- [ ] T020 [US4] Extend `tests/helpers/setup_flows.py` — validation paths:
      `validate_existing(mock, workspace)` (store header, config, bindings, stamp —
      no writes), already-set-up reporting (doctor summary), partial-state resumption
      (each missing team artifact created, present ones validated never re-created),
      malformed-config repair surfacing (never treated as absent — R4)
- [ ] T021 [US4] Write `tests/contract/test_setup_idempotence.py`: run team mode then
      re-run ⇒ second run zero mutating ops in write log + already-green report
      (SC-005); partial state (config present, header missing) ⇒ only the header
      created, config untouched (US4 scenario 2); malformed config ⇒ repair case
      surfaced, no team-mode re-creation, no writes (FR-009 + edge case)

**Checkpoint**: `make verify` green — all four stories delivered.

---

## Phase 7: Polish & Cross-Cutting

**Purpose**: The Constitution VII gate over the new shipped prose, the FR→test mapping
record, and design-doc reconciliation.

- [ ] T022 [P] Write `tests/contract/test_command_capability_naming.py`: extend the
      slice-3 naming-scan mechanism over `commands/*.md`, `manifest/capabilities.json`,
      `templates/session-sheet.md` — no concrete MCP server/tool names;
      `templates/mcp.recommended.json` exempt but asserted valid JSON naming servers for
      all four required capabilities; op names in command prose parse under the
      `capability.operation` format (FR-010, R13)
- [ ] T023 [P] Append the FR → test-module mapping record to this file (FR-001–FR-012,
      each naming its exercising module(s)) — the FR-011 traceability artifact
- [ ] T024 Reconcile design doc: verify §7.2's "diary writable" and "Sheet" phrasing
      against the spec's schema-matched/store-neutral pins — if the design needs an
      amendment note (per its §11 decision-log duty), make it in
      `bb-technical-design.md` in this change; otherwise record "no amendment needed"
      in the PR body
- [ ] T025 Final `make verify` + quickstart walkthrough (every quickstart command runs
      as documented); confirm every FR-011 surface listed in the spec has its test

**Checkpoint**: `make verify` green; slice complete.

---

## Dependencies

- Phase 1 → Phase 2 → Phase 3 (US2) → Phase 4 (US1) → Phases 5–6 (US3, US4 — order
  between them free; both extend `setup_flows.py`, so serialize edits) → Phase 7
- US1 depends on US2 (team mode ends with doctor + smoke); US3/US4 depend on US1's
  setup_flows base; T016 (stamp) has no US1 dependency beyond doctor_flows and may start
  after Phase 3
- Within phases, [P] tasks touch disjoint files

## Parallel opportunities

- Phase 2: T003, T004, T005 after T002
- Phase 3: T009, T010 after T008; T011 alongside tests once T006/T008 fix the protocol
- Phase 4: T013 alongside T012
- Phase 5: T018, T019 after T016/T017
- Phase 7: T022, T023 parallel

## Implementation strategy

MVP = Phases 1–4 (US2 + US1: doctor resolving/verifying and a team reaching green in one
command — the SM-2 seam). US3/US4 complete the responder and idempotence promises; Phase
7 gates naming and traceability. Verify + commit at every checkpoint; each story stands
alone green.
