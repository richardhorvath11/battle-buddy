# Tasks: Lifecycle Commands

**Input**: Design documents from `/specs/005-lifecycle-commands/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R17), data-model.md,
contracts/lifecycle-protocol.md, quickstart.md

**Tests**: REQUIRED — Constitution VIII (code without its tests in the same change is
incomplete) and FR-012 (every requirement exercised by ≥1 hermetic contract test). Doc
and test tasks are paired inside each story; a story's checkpoint is `make verify` green.

**Organization**: By user story in dependency order: US1 (`/page` open flow — P1) first
(everything else rides an opened session), then US2 (incident/promotion — P1), US4
(close — P1), US3 (join — P2; rides US1's machinery and US4's take-over/marker-rewrite
primitives). Full open→close simulation (SC-007) lands in Polish once all stories exist.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 per spec.md

## Phase 1: Setup

**Purpose**: The fixture directory this slice introduces.

- [x] T001 Create `tests/fixtures/lifecycle/` with subdirs `verdicts/` and `seeds/`;
      add a fixture transcript source file `tests/fixtures/lifecycle/transcript.md`
      (a few markdown turns — the R9 copy source)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The fixture stand-ins for every consumed slice-6–9 surface (research
R3–R6) — every story's tests drive them.

**⚠️ CRITICAL**: No user story work until this phase is complete.

- [x] T002 [P] Create `tests/fixtures/lifecycle/verdicts/` fixture verdicts (R3):
      `valid-known-issue.json` (VALIDATED known_issue + candidates with `{url, excerpt}`
      evidence incl. ≥2 distinct dashboard URLs with one cited most — feeds R16
      top-cited), `valid-no-signal.json` (`no_strong_signal: true`), `invalid-then-
      valid/` pair (re-prompt path), `invalid-twice/` pair (flagged-persist path) —
      invalid docs violating `bb.verdict.v1` in ways `tests/fixtures/validate/` doesn't
      already cover, else reuse that corpus; all valid docs pass the real `bb_validate`
- [x] T003 [P] Create `tests/fixtures/lifecycle/catalog.json` (R4): ≥2 fixture services
      (`name`, `owner`, `runbooks`, `dashboards`, `alert_matchers`, `depends_on`), one
      matching the mock's seeded alert `service_hint`, one unmatched (ladder path)
- [x] T004 [P] Create `tests/fixtures/lifecycle/seeds/` seed-row fixtures:
      `join-open-yesterday.json` (open row, same source ID, yesterday-dated
      `session_id`, `latest_checkpoint` set + an overflow variant), `merge-duplicates.json`
      (two open rows sharing a source ID, distinct `started_at`/links/folders),
      `promotion-open-page.json` (open page row), `ownership-displaced.json`
      (row whose `responder` names someone else)
- [x] T005 Create `tests/helpers/lifecycle_fixtures.py` (R3–R6): fixture-verdict
      loaders (single + ordered re-prompt lists); `resolve_service(alert, catalog,
      rung_answers=None)` walking the §5.2 ladder with `catalog_resolved` semantics,
      fingerprinting via the real `bb_fingerprint`; `RecordingShellAdapter`
      (`open_pane`/`navigate_pane`/`notify`/`close_workspace`, call log) +
      `FailingShellAdapter` (raises mid-flow) + degraded-mode printed-message recorder;
      seed loader writing seed rows through `storage.append_record`; local-state
      builders (staged `trace.jsonl` call/tripwire lines + `staging/checkpoints.jsonl`
      entries for R10 timeline inputs); a transient-fault injector wrapping the mock
      (slice-4 `FailingProbeInjector` pattern) that fails a designated op N times then
      passes through — the FR-008 transient-row-write stand-in the contract's closed
      error set cannot express

**Checkpoint**: `make verify` green — fixture surfaces importable, fixture verdicts
validated by the real validator.

---

## Phase 3: US1 — One command from alert to briefing (P1)

**Goal**: `/page` end to end: preflight (no probes, stop/repair/crash-residue/auto-
responder paths), the FR-001 open-flow order, checkpoint zero riding the append,
marker lifecycle, briefing with deep-linked evidence and shell/degraded branches.

**Independent test**: drive the documented `/page` steps against `bb-mock-mcp` with a
temp local-state dir; assert marker lifecycle, row landing, verdict validation before
persist, mock write ordering (spec US1).

- [x] T006 [US1] Write `commands/page.md`: preflight decision table (contracts doc
      order — config stop / repair / confirmed-marker stop / crash-residue rewrite /
      stamp auto-responder / zero-probe proceed), open-flow order (§3.2 + FR-001 incl.
      checkpoint-zero-rides-append and overflow-first), join-vs-separate section
      (FR-004, choice before any write), briefing properties (`bb.briefing.v1`
      invariants, top-cited navigate, degraded printed links), fail-soft postures
      (alert fetch, shell, catalog ladder), session-ID UTC date pin — capability/
      operation names only (the existing naming gate covers this file by glob)
- [x] T007 [US1] Create `tests/helpers/lifecycle_flows.py` — preflight + open:
      `preflight(config, state_dir, stamp_path, ...)` per the contracts-doc table,
      reusing `doctor_flows.evaluate_stamp` + `setup_flows.responder_mode` (R11);
      `open_command(mock, state_dir, session_type, source_id, opened_date, verdict_candidates,
      catalog, shell, transcript_path=None, ...)` executing the FR-001 order via
      `store_flows`/`retrieve_candidates`, verdict gate through the real `bb_validate`
      (one re-prompt, flagged persist), verdict riding the append with cell-guard
      overflow-first (R2), history line, read-back → marker confirm, `bb.briefing.v1`
      assembly + navigate/degraded branch (R16), `deep_proposed`/`deep_launched` flags
      (R14); outcome dicts per data-model.md
- [x] T008 [P] [US1] Write `tests/contract/test_page_preflight.py`: happy path — zero
      probe calls, write log untouched, no doctor report produced, stamp byte-unchanged
      (SC-002); missing config stops with "run /setup" and zero session artifacts
      (AS-2); malformed config → repair stop; missing/stale stamp → `responder_mode`
      ran then flow proceeds; confirmed marker → stop offering close; unconfirmed
      marker → surfaced, rewritten only on confirmation, untouched on decline (FR-001,
      R8)
- [x] T009 [P] [US1] Write `tests/contract/test_open_flow.py`: session-ID format +
      row fields + `status: open` (AS-3); marker created `false` → `true` only after
      read-back, write-log ordering (marker precedes append is local, append precedes
      read-back); checkpoint zero rides the append — exactly one `append_record`, no
      post-append verdict `update_record`, history line written (R2); over-guard
      verdict → `put_file` `checkpoint-0.json` **before** the append, cell holds
      overflow pointer; validation paths — valid / invalid-then-valid re-prompt /
      invalid-twice persists flagged `schema_valid: false` and surfaces (AS-4);
      alert-fetch `not_found` → session still opens degraded (edge, R15); catalog miss
      → ladder rung answer used, `catalog_resolved: false` on the row, briefing notes
      downgrade (edge)
- [x] T010 [P] [US1] Write `tests/contract/test_briefing_properties.py`: every claim
      carries ≥1 `{url, excerpt}` with both non-empty (Constitution IV); top-cited
      dashboard computed per R16 tie rule; shell configured → exactly one
      `navigate_pane` to it; degraded → same links in `printed_links`, zero adapter
      calls; `FailingShellAdapter` mid-flow → flow completes, printed fallback
      recorded; open-time `open_pane` recorded with the session-named workspace when a
      shell adapter is configured, printed message in degraded mode (FR-001 step,
      FR-006, FR-011)

**Checkpoint**: `make verify` green — `/page` independently testable end to end.

---

## Phase 4: US2 — Incidents get incident weight; pages promote (P1)

**Goal**: `/incident` fresh (incident defaults, deep proposal) and in-place promotion
(update-not-append).

**Independent test**: fresh `/incident` lands `session_type: incident`; `/incident`
inside an open page fixture re-tags the same row — write log shows an update, no second
row (spec US2).

- [x] T011 [US2] Write `commands/incident.md`: same open flow by reference to
      `commands/page.md` with incident deltas — `session_type: incident`, deep
      investigation proposed immediately after triage, responder confirmation vs
      `autoLaunchDeep` (additive key, contracts doc), and the promotion path: detect
      open page session via the marker, one `update_record` re-tag, same `session_id`,
      no new marker, deep launch on promotion (FR-003, §3.2/§3.4)
- [x] T012 [US2] Extend `tests/helpers/lifecycle_flows.py`: `open_command` incident
      defaults (`deep_proposed` after triage; `deep_launched` per confirmation/
      `autoLaunchDeep` — R14) and `promote_session(mock, state_dir, ...)` (marker names
      the open session; single re-tag `update_record`; `deep_launched: true`)
- [x] T013 [US2] Write `tests/contract/test_incident_flows.py`: fresh incident row
      lands `session_type: incident` with `deep_proposed` (AS-1); confirmation gate —
      `deep_launched` false without confirmation, true with it, true unconfirmed when
      `autoLaunchDeep` (R14); promotion — same `session_id`, write log shows exactly
      one `update_record` re-tag and no second `append_record` for the source ID
      (AS-2, SC-003); promotion leaves marker and other row fields untouched

**Checkpoint**: `make verify` green — both entry points + promotion independently
testable.

---

## Phase 5: US4 — Close writes everything down, in order, and proves it (P1)

**Goal**: `/close` end to end: draft artifact with proposal-labeled causal fields,
approval gate, merge-at-close, ownership at close, the pinned dual-write, transcript
capture, timeline derivation, read-back-gated deletion, shell close.

**Independent test**: run documented close steps against the mock with a fixture
session; assert write ordering, read-back-then-delete, `diary_pending`, proposal
labeling, merge leaving one non-superseded row (spec US4).

- [x] T014 [US4] Write `commands/close.md`: no-session guard (report, zero writes);
      merge-at-close first + canonical-row rule (R12); draft step — `bb.draft.v1`
      structure, factual autofill vs proposal-labeled causal fields, template-else-
      `read_recent(5)` rendering (R5), approval gate (no writes before `approved`);
      dual-write pinned order + ordering-claim scope (contracts doc), diary-failure
      (`diary_pending` is the retry queue), per-file artifact failure, transcript
      capture from the runtime transcript path + post-close-turns limitation (R9),
      timeline derivation rule (R10), close-time ownership re-read + read-only
      displacement (R13), transient row-write retry (bounded, injector-driven; close
      blocks on row-write success) vs displacement distinction (FR-008), read-back → `.bb-session/` deletion, shell `close_workspace` last,
      state restorable, degraded printed message (FR-007–FR-010)
- [x] T015 [US4] Extend `tests/helpers/store_flows.py` and
      `tests/helpers/lifecycle_flows.py` — close. In `store_flows.close_session`: two
      additive, keyword-only, default-off parameters (R13 mechanism) — `owned_by=None`
      (when set, re-read the row's `responder` immediately before the step-3
      `update_record`; mismatch ⇒ return read-only outcome with `taken_over_by`,
      skipping row update/read-back/marker clearance; earlier diary/artifact writes
      stand) and `row_write_retries=0` (bounded re-issue of the step-3 `update_record`
      on a non-`not_found` error; steps 1–2 never re-run — no double diary write);
      defaults preserve slice-3 behavior, existing slice-3 tests unmodified. In
      `lifecycle_flows.py`:
      `derive_timeline(state_dir)` (R10: call lines + history entries → ordered events,
      1:1); `draft_close(mock, config, row, timeline, proposals)` → `bb.draft.v1`
      (template-else-`read_recent(5)` rendering input recorded); `close_command(mock,
      state_dir, transcript_path, draft, ...)`: no-marker guard, merge via
      `merge_duplicates` + canonical retarget (R12), ownership pre-reads before merge
      writes and close-time update (R13), approval gate, transcript copy → staging
      (R9), dual-write by calling the extended `store_flows.close_session` on the
      canonical row (`owned_by` + `row_write_retries` set; close blocks on row-write
      success, FR-008), timeline into the update, shell close; outcome dict per
      data-model.md
- [x] T016 [P] [US4] Write `tests/contract/test_close_command.py`: draft structure —
      causal values only under `proposals.*` with `"proposal": true`, `factual` free of
      causal keys, zero writes while unapproved (AS-4, SC-006); write-log ordering
      diary → artifacts → row update (AS-1, SC-005); artifact set + names incl.
      transcript copied from fixture path and `trace.jsonl` → `tool-trace.jsonl`
      (AS-6); missing transcript source → notice + omitted, close continues (R9);
      seeded diary failure → row lands `diary_pending: true` (AS-3); transient
      row-write failure (injector fails `update_record` once) → retried, row lands,
      marker deletion still read-back-gated (FR-008); read-back success
      → `.bb-session/` deleted; failed/mismatched read-back → directory intact (AS-2);
      timeline 1:1 from staged trace + checkpoint fixtures, timestamped, ordered, no
      transcript-derived events (AS-6, R10); shell `close_workspace` called /
      degraded printed (AS-7); no-session close → zero writes (edge)
- [x] T017 [P] [US4] Write `tests/contract/test_close_merge_ownership.py`: seeded
      duplicates → earliest canonical, links + duplicate folder folded, duplicate
      `superseded`, exactly one non-superseded row for the source ID, dual-write
      targets the canonical row, closing-session marker cleared on canonical read-back
      (AS-5, R12); displaced ownership → no merge/row writes after the failed pre-read,
      marker intact, `read_only` + `taken_over_by` reported (edge, R13)

**Checkpoint**: `make verify` green — `/close` independently testable end to end.

---

## Phase 6: US3 — Joining, not duplicating, an open session (P2)

**Goal**: join-vs-separate on the open-time read: explicit choice before any write,
join rehydrates + takes over + rewrites the marker (protocol extension R7), separate
appends exactly one distinct row.

**Independent test**: seed an open row (same source ID, dated yesterday); assert the
join offer, join rehydration from `latest_checkpoint` + take-over write, and separate
producing a distinct row only on explicit choice (spec US3).

- [ ] T018 [US3] Extend `tests/helpers/lifecycle_flows.py` — join:
      `open_command` surfaces `join_offer` (via `detect_open_session` on the open-time
      read) and **stops before any store write** pending the choice;
      `join_session(mock, state_dir, row, responder, ...)`: rehydrate via
      `read_latest_checkpoint` (overflow followed), take-over write, marker rewritten
      to the joined identity with confirmation = take-over read-back (R7);
      `open_separate(...)`: proceed with the normal append flow on explicit choice
- [ ] T019 [US3] Write `tests/contract/test_join_separate.py`: seeded yesterday-dated
      open row → join offer surfaced, matching by parsed source ID + non-terminal
      status (never recomputed ID), **zero mutating ops before the choice** (AS-1,
      SC-004); join → rehydrated state equals the seeded `latest_checkpoint` (and the
      overflow variant resolves), take-over writes `responder: <me> @ <ts>`, marker
      carries the joined `session_id` with `open_write_confirmed` true only after the
      take-over read-back (AS-2, R7, FR-002); separate → exactly one new row appended,
      marker tracks the new session only (AS-3); `handoff`-status row also joinable

**Checkpoint**: `make verify` green — join/separate independently testable.

---

## Phase 7: Polish & Cross-Cutting

- [ ] T020 [P] Write `tests/contract/test_lifecycle_full_sim.py` (SC-007): one full
      `/page` open → checkpoint → promotion → `/close` simulation on a temp state dir —
      every artifact assertion from the story suites re-checked end to end, and every
      mock invocation verified to be an operation-contract-v1 op (zero ops outside the
      contract); plus a `/page`→`/close` degraded-mode (no shell) variant
- [ ] T021 [P] Record the FR → test mapping: extend `specs/005-lifecycle-commands/
      quickstart.md`'s scenario table if any FR lacks a row (FR-001–FR-013 each mapped
      to ≥1 test — SC-001's checkable record); confirm the naming gate covers the three
      new command docs (run `pytest tests/contract/test_command_capability_naming.py -q`)
- [ ] T022 Full-suite pass: `make verify`; fix anything surfaced; confirm
      `tests/contract` runtime stays in seconds (plan Performance Goals)

---

## Dependencies

- Phase 1 → Phase 2 → US1 (Phase 3) → US2 (Phase 4) → US4 (Phase 5) → US3 (Phase 6) →
  Polish (Phase 7)
- US2 needs US1's `open_command`; US4 needs an openable session (US1) and closes over
  seeds independently; US3 needs US1's open read + the take-over/marker primitives
  (slice-3 `take_over` + R7 rewrite, exercised in US4's ownership work but importable
  from slice 3 directly — US3 may start once US1 lands if US4 is in flight)
- Within a phase, [P] tasks touch disjoint files and may run in parallel

## Implementation strategy

MVP = Phase 3 (US1): `/page` alone is the product's front door and independently
green. Each later phase is an independent increment with its own verify-green
checkpoint; SC-007's full simulation is deliberately last.
