# Tasks: Session-Store Conventions

**Input**: Design documents from `/specs/003-session-store/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R10), data-model.md, quickstart.md

**Tests**: REQUIRED — Constitution VIII (code without its tests in the same change is
incomplete) and FR-011 (every convention exercised by ≥1 hermetic contract test). Doc
and test tasks are paired inside each story; a story's checkpoint is `make verify`
green.

**Organization**: By user story, in spec priority order. US1/US2 are P1 (the MVP seam),
US3/US4 P2, US5 P3.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 per spec.md

## Phase 1: Setup

**Purpose**: The skill bundle scaffold every story writes into.

- [ ] T001 Create `skills/session-store/SKILL.md` skeleton (frontmatter with name +
      when-to-use description, overview of the tier-0 store model, routing table to
      `references/schema.md` / `fingerprint.md` / `retrieval.md`, empty convention
      section stubs for close flow / checkpoints / ownership / artifacts) and the
      `skills/session-store/references/` directory

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The schema documentation and its mechanical cross-check — every story's
rows, flows, and fixtures build from these columns; SC-006 is the drift gate that must
exist before doc and tests can co-evolve safely.

**⚠️ CRITICAL**: No user story work until this phase is complete.

- [ ] T002 Write `skills/session-store/references/schema.md`: the full §5.1 column
      table (Column / Type / Mutation class / Notes per data-model.md — the SC-006
      parse target), `session_id` key format, `bb.schema.v1` declaration + header-row
      sentinel-cell representation (research R2/R8), the FR-002 append-mostly mutation
      policy (full enumerated mutable set, close-time group, write-once re-assertion
      rule), and the FR-013 tier-1 stability commitment
- [ ] T003 Create `tests/helpers/store_flows.py` base: canonical column constants
      (name + mutation class, mirroring schema.md), enum constants (`status`,
      `session_type`, non-terminal set), row-builder helper producing
      contract-shaped records; module docstring stating it is the conventions'
      executable form (research R4, FR-012 dev-only)
- [ ] T004 Write `tests/contract/test_store_schema_doc.py`: parse schema.md's column
      table and assert name/order/mutation-class equality both ways against
      `store_flows` constants (SC-006); assert the documented mutable set is exactly
      FR-002's enumeration; assert the stability commitment and `bb.schema.v1` are
      present

**Checkpoint**: `make verify` green — schema doc and test constants mechanically
converged.

---

## Phase 3: User Story 1 — Repeat incident recognized before investigation starts (P1) 🎯

**Goal**: The documented three-stage retrieval flow + the normative fingerprint
reference, executed as deterministic reads against seeded fixtures (FR-003, FR-007).

**Independent Test**: Seed the mock, run the documented retrieval stages via
`store_flows.retrieve_candidates`, assert candidate sets per stage — no agent, no
credentials, no network.

- [ ] T005 [P] [US1] Write `skills/session-store/references/fingerprint.md`: normative
      `bb.fp.v1` statement — construction formula, normalization rules matching
      `bin/bb_fingerprint.py` (same rule order), the four-rung service-resolution
      ladder with `catalog_resolved` semantics, never-a-shared-sentinel rule,
      version-bump + re-fingerprint discipline, helper/golden-corpus roles, and ≥2
      worked examples in a fenced block (one catalog-resolved, one rung-4) for the R6
      recomputation check
- [ ] T006 [P] [US1] Write `skills/session-store/references/retrieval.md`: stage-0
      exclusions (`session_type: test`, `status: superseded`) applied at every stage;
      stage 1 fingerprint exact-match with `catalog_resolved` downgrade (either row);
      stage 2 keyword overlap on `services`/`alert_signature`/`severity`; stage 3
      cap 20 with truncation stated, never silent; empty result = normal fresh-
      investigation outcome
- [ ] T007 [P] [US1] Create `tests/fixtures/store/seed-retrieval.json` (mock
      `load_seed` format): exact-fingerprint match row, keyword-overlap-only rows,
      `session_type: test` and `status: superseded` rows that would otherwise match,
      a `catalog_resolved: false` exact-match pair, and >20 keyword-matching rows for
      the cap case
- [ ] T008 [US1] Implement `retrieve_candidates` in `tests/helpers/store_flows.py`
      executing retrieval.md's stages step-by-step over `read_records` (each step
      cites its skill section)
- [ ] T009 [US1] Write `tests/contract/test_retrieval_flow.py`: US1 AS-1–AS-5 plus the
      empty/all-excluded-store edge case (spec Edge Cases), asserting candidate sets,
      downgrade classification, cap truncation surfaced, and exclusions at every stage
      (SC-003)
- [ ] T010 [US1] Write `tests/contract/test_fingerprint_reference.py`: doc version tag
      == `bb_fingerprint.VERSION` == golden-corpus version; every worked example in
      fingerprint.md recomputes exactly through the real helper (research R6, FR-003)

**Checkpoint**: `make verify` green — retrieval conventions proven against fixtures.

---

## Phase 4: User Story 2 — Closing session's record lands durably, in order (P1) 🎯

**Goal**: The close-time dual-write conventions — diary → artifacts → row → read-back →
marker clearance — plus the open-time append/read-back twin and the diary/artifact
failure paths (FR-008, research R10).

**Independent Test**: Run `store_flows.close_session` against the mock; assert ordering
from `write_log.entries`, marker clearance only on read-back success, and failure paths
landing the row.

- [ ] T011 [US2] Fill SKILL.md's close-flow + open-flow section: pinned write order
      with the ordering claim scoped to close-flow writes; both read-back confirmation
      points (open-time `open_write_confirmed`, close-time deletion-is-cleared per
      local-state protocol v1); diary failure → row lands `diary_pending: true` with
      the flag-as-retry-queue recovery convention (research R10); artifact-upload
      failure → row proceeds, links omitted, gap surfaced (spec edge case); `not_found`
      on row update → re-locate by source ID + non-terminal status, never retry-blind;
      timeline derived from trace + checkpoint history, never prose recall
- [ ] T012 [US2] Implement `open_session` (append → read-back → marker
      `open_write_confirmed`) and `close_session` (diary → staged artifacts → row
      update with re-asserted write-once values → read-back → marker delete; failure
      paths per SKILL.md) in `tests/helpers/store_flows.py`, operating on a
      caller-supplied local state dir per protocol v1
- [ ] T013 [US2] Write `tests/contract/test_close_flow.py`: US2 AS-1–AS-4 (ordering via
      write log, read-back gates marker clearance, diary-failure → `diary_pending` +
      row never skipped, failed read-back leaves marker), artifact-failure edge (row
      lands, link omitted), `not_found` reconciliation edge, and the R10
      pending-recovery read (`read_records` filter `{diary_pending: true}`) (SC-002)

**Checkpoint**: `make verify` green — US1+US2 = both P1 stories complete (MVP seam).

---

## Phase 5: User Story 3 — Interrupted investigation resumes from checkpoint (P2)

**Goal**: Checkpoint representation — row cell + local history accumulation, 45,000-char
guard with overflow pointers, `bb-validate` gate with re-prompt-then-flag (FR-005,
FR-006, research R1/R9).

**Independent Test**: Write fixture checkpoints (small / at-guard / over-guard / valid /
invalid) through `store_flows.write_checkpoint`; assert cell contents, history lines,
overflow round-trip via `get_file`, and the flagged-persist path.

- [ ] T014 [US3] Fill SKILL.md's checkpoint section: `triage_verdict` (seq 0) vs
      `latest_checkpoint`; serialized-length guard at 45,000 chars — at the guard fits
      the cell, strictly above stores full document via artifacts `put_file` at write
      time with cell holding `{"overflow": "<link>", "seq": n}` (readers MUST follow);
      history accumulates one line per checkpoint at
      `.bb-session/staging/checkpoints.jsonl`, uploaded at close as
      `checkpoints.jsonl` (research R1); mandatory `bb-validate` before every write,
      one re-prompt with the error list, second failure persists flagged
      `"schema_valid": false` and surfaces the degradation; one-row-read resume rule
- [ ] T015 [US3] Record the additive `staging/checkpoints.jsonl` entry in
      `specs/002-deterministic-layer/contracts/local-state-protocol.md` (staging/
      section): accumulation lifecycle, upload name, and the no-version-bump rationale
      (no existing format or consumer-parse change — research R1)
- [ ] T016 [P] [US3] Create `tests/fixtures/store/checkpoints/` fixtures: valid
      `bb.ledger.v1` document, invalid+fixed pair, invalid+still-invalid pair
      (research R9), and an oversize template the test inflates past 45,000 chars
- [ ] T017 [US3] Implement `write_checkpoint` in `tests/helpers/store_flows.py`:
      ownership pre-read (cites the US4 section; passes trivially for the owner) →
      `bb_validate` on the ordered candidate list (one re-prompt, then flag) → guard
      check → in-cell `update_record` or `put_file`+pointer → history line append to
      the local staging file
- [ ] T018 [US3] Write `tests/contract/test_checkpoint_conventions.py`: US3 AS-1–AS-4
      plus the exactly-at-guard edge (45,000 chars lands in-cell, zero store
      rejections — SC-005), overflow round-trip recovering the full document,
      history-line accumulation matching every write, and the twice-invalid path
      persisting flagged with data intact

**Checkpoint**: `make verify` green.

---

## Phase 6: User Story 4 — Handoff and duplicates resolve without locking (P2)

**Goal**: Optimistic ownership — take-over write, mandatory pre-write re-read,
join-at-open by source ID + non-terminal status, merge-at-close (FR-009).

**Independent Test**: Two simulated writers against one mock store: take-over,
displaced-writer denial, join detection on a seeded yesterday-dated open row,
merge-at-close producing one canonical + one `superseded` row.

- [ ] T019 [US4] Fill SKILL.md's ownership section: `responder` as ownership token with
      `<responder> @ <ISO timestamp>` format; take-over as a single recorded
      `update_record` write; mandatory ownership re-read immediately before every
      checkpoint write — failed check ⇒ no write, session informed, read-only;
      join-at-open detection by source ID + non-terminal status (`open`|`handoff`),
      never a recomputed session ID (cross-day rationale); merge-at-close — earliest
      `started_at` canonical, artifact links folded in, duplicate `status: superseded`;
      race bound: at most one stale checkpoint, store edit history as audit trail
- [ ] T020 [P] [US4] Create `tests/fixtures/store/seed-ownership.json`: same-source-ID
      rows with yesterday-dated `session_id` in `open` and `handoff` status, a
      terminal-status row that must NOT trigger join, and a duplicate-open pair for
      the merge scenario
- [ ] T021 [US4] Implement `take_over`, `detect_open_session` (join-at-open read), and
      `merge_duplicates` in `tests/helpers/store_flows.py`; wire the ownership
      pre-read denial path in `write_checkpoint` to return the read-only outcome
- [ ] T022 [US4] Write `tests/contract/test_ownership.py`: US4 AS-1–AS-4 plus the
      cross-day-handoff edge (join found despite differing session ID) and the
      terminal-status non-match; assert the displaced writer performs zero mutating
      ops after take-over (write log) and exactly one non-`superseded` row per source
      ID after merge (SC-004)

**Checkpoint**: `make verify` green.

---

## Phase 7: User Story 5 — Audit trail findable and regenerable (P3)

**Goal**: The artifact-layout conventions — folder per session, four documented names,
the local→uploaded name mapping, row-discoverable links, regenerability (FR-004).

**Independent Test**: Run the documented upload conventions against the mock artifact
store; assert folder-qualified names, the mapping, and links resolving via `get_file`.

- [ ] T023 [US5] Fill SKILL.md's artifact-layout section: `battle-buddy/<session_id>/`
      folder path expressed as the folder-qualified `put_file` name; the four artifact
      names (`transcript.md`, `tool-trace.jsonl`, `checkpoints.jsonl`, `report.md`);
      the local `trace.jsonl` → uploaded `tool-trace.jsonl` mapping restated as owned
      by local-state protocol v1; row discoverability (`artifacts_folder_url` +
      per-artifact links); report = pure rendering of row + artifacts, regenerable
      because evidence is `{url, excerpt}` (execution of report generation + timeline
      derivation deferred to slice 5, documented as such)
- [ ] T024 [US5] Write `tests/contract/test_artifact_layout.py`: US5 AS-1–AS-3 —
      uploads land under the session's folder path with the four names (driven through
      `close_session`), the `trace.jsonl` → `tool-trace.jsonl` mapping holds, every
      row artifact link resolves to the uploaded content via `get_file`, and the
      regenerability property (row + artifacts carry `{url, excerpt}` evidence with no
      information needed beyond them)

**Checkpoint**: `make verify` green — all five stories independently proven.

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: The cross-cutting requirements that span all docs, and the design-doc
reconciliation the spec flags.

- [ ] T025 [P] Write `tests/contract/test_skill_capability_naming.py`: FR-010 — scan
      every `skills/session-store/` file for concrete MCP server/tool-name patterns
      (e.g. `mcp__`, known server names) and assert none; operation names
      (`append_record`, `put_file`, `append_entry`, …) and store-medium nouns (Sheet,
      Drive, cell) are the permitted vocabulary; assert each documented operation name
      exists in `tools/bb-mock-mcp/contract.json` (operation-contract fidelity)
- [ ] T026 [P] Update `specs/003-session-store/quickstart.md` scenario table if any
      module names/paths drifted during implementation; confirm the FR-001–FR-013 →
      test mapping is complete (SC-001) and record it in the table
- [ ] T027 Reconcile `bb-technical-design.md` per the spec's flagged assumptions (spec
      Assumptions: mutable-field set, checkpoint-history representation, §9 rehydrate
      row): §5.1's append-mostly sentence names the full FR-002 mutable set; §5.4's
      "appends to `checkpoints.jsonl` in Drive" reworded to local accumulation +
      close-time upload; §9's mid-investigation rehydrate row drops the remote
      `checkpoints.jsonl` fallback; version bump 1.2.1 → 1.2.2 with change note
- [ ] T028 Run full `make verify` + walk quickstart.md's scenario table end-to-end;
      confirm zero storage code outside `tests/` (packaging test) and hermeticity (no
      credentials/network anywhere in new tests)

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: T001 before T002 (SKILL.md routes to schema.md).
- **Phase 2 blocks all stories**: T002 → T003 → T004 (doc → constants → cross-check).
- **US1 (Phase 3)**: T005/T006/T007 parallel after Phase 2; T008 needs T003+T006;
  T009 needs T007+T008; T010 needs T005.
- **US2 (Phase 4)**: T011 after T001; T012 needs T003+T011; T013 needs T012. US2 is
  independent of US1 (different files throughout).
- **US3 (Phase 5)**: T014 after T011 (same file, sequential); T015/T016 parallel;
  T017 needs T012 (state-dir plumbing) + T014 + T016; T018 needs T017.
- **US4 (Phase 6)**: T019 after T014 (same file); T021 needs T017 (extends
  `write_checkpoint` denial path) + T020; T022 needs T021.
- **US5 (Phase 7)**: T023 after T019 (same file); T024 needs T012 + T023.
- **Polish**: T025/T026 parallel after all docs exist; T027 anytime after Phase 5
  (needs the R1 pin landed); T028 last.

**SKILL.md serialization note**: T011 → T014 → T019 → T023 all edit SKILL.md — always
sequential, never parallel-dispatched.

## Parallel Example: User Story 1

```text
After Phase 2 checkpoint:
  T005 fingerprint.md  |  T006 retrieval.md  |  T007 seed-retrieval.json   (3 files, no deps)
then T008 → T009, and T010 (needs only T005) alongside T008/T009.
```

## Implementation Strategy

**MVP = US1 + US2** (both P1): Phases 1–4, verify green, then each later phase is an
independent increment with its own green seam. Commit at every checkpoint; tasks.md
ticks are the orchestrator's acceptance record (verify gate + adjudicated review), not
the implementer's self-report.
