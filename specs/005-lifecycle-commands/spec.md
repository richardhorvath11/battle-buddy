# Feature Specification: Lifecycle Commands

**Feature Branch**: `005-lifecycle-commands`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 5 of the battle-buddy MVP (design `bb-technical-design.md` §3.2, §4, §9; decisions D-5, D-8, D-11; PRD FR-1, FR-2, FR-3a, FR-4–4e, FR-8, NFR-1; Constitution I, II, V, VII, VIII): the session lifecycle surface — `/page`, `/incident`, `/close` — expressed as command prose plus hermetic contract tests against `bb-mock-mcp`. These commands *execute* the slice-3 session-store conventions and are the designated *writer* of the slice-2 local-state protocol's session marker.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One command from alert to briefing (Priority: P1)

At 3am, a responder runs `/page <alert-id>`. The command preflights cheaply (config block present? local green stamp matching? — no probes; a missing/stale stamp auto-runs responder-mode setup, seconds, only ever on a first page from a new machine), computes the session ID (`page-<alert-id>-<ISO date>`), writes the local session marker, opens the session-named shell workspace (a printed message in degraded mode), fetches alert context and flap history, resolves the alert to a service and fetches runbooks fresh, runs tier-0 retrieval, spawns the triage agent, validates the returned verdict, persists it as checkpoint zero, appends the session row (`status: open`), reads the row back — confirming the open write in the marker — and presents the briefing with evidence deep-links, driving the top-cited dashboard into view where a shell adapter exists.

**Why this priority**: This is the product's front door and the NFR-1 budget — one command → briefing. Everything else assumes an opened session. P1.

**Independent Test**: Drive the documented `/page` steps as a deterministic script against `bb-mock-mcp` with a fixture alert and seeded rows, using a temporary local-state directory: assert the marker lifecycle (created → `open_write_confirmed: true` only after row read-back), the row landing with correct `session_id`/`session_type`/`status`/fingerprint, checkpoint zero validated before persist, and the ordering of mock writes.

**Acceptance Scenarios**:

1. **Given** valid config and a matching green stamp, **When** `/page ALERT-123` runs, **Then** preflight performs no probe calls and proceeds straight to session open. *(§3.2 step 1, D-15/slice-4 stamp)*
2. **Given** a missing config block, **When** `/page` runs, **Then** it stops with "run /setup" — it never half-opens a session. *(§3.2 step 1)*
3. **Given** session open, **When** the row is appended, **Then** the session ID is `page-<alert-id>-<ISO date>`, the row lands with `status: open` and the slice-3 schema fields, the row is read back, and only then does the marker record the open write confirmed. *(§3.2 steps 2, 8; D-8, D-11; local-state protocol v1)*
4. **Given** a triage verdict returned, **When** it is persisted as checkpoint zero, **Then** it passes validation first (one re-prompt on failure; second failure persists flagged per slice-3 conventions). *(§3.2 step 8; §5.4, D-14; slice-3 FR-006)*
5. **Given** the briefing, **When** it is presented, **Then** every cited claim carries its evidence deep-link, and with a shell adapter configured the top-cited dashboard is navigated into view; in degraded mode links are printed instead. *(§3.2 step 9, FR-9, FR-26)*

---

### User Story 2 - Incidents get incident weight, and pages can become incidents (Priority: P1)

`/incident <incident-id>` runs the same flow with incident defaults: the session row carries `session_type: incident` and deep investigation is proposed immediately after triage. When `/incident` is invoked *inside an already-open page session*, it promotes instead of duplicating: the existing row's `session_type` is re-tagged to `incident` in place and deep investigation launches — no new session, no context loss.

**Why this priority**: FR-1 names promotion explicitly; incident weight is what distinguishes the two entry points. Co-P1 with the page flow they share.

**Independent Test**: Simulate `/incident` fresh (row lands `session_type: incident`) and `/incident` inside an open page fixture (same row re-tagged in place — same `session_id`, no second row; the mock write log shows an update, not an append).

**Acceptance Scenarios**:

1. **Given** `/incident INC-1` with no open session, **When** the row lands, **Then** `session_type: incident` and the deep-investigation proposal follows triage (responder confirms; auto-launch only if configured). *(§3.2; §3.4 launch conditions, FR-5f)*
2. **Given** an open page session, **When** `/incident` is invoked within it, **Then** the existing row is re-tagged `session_type: incident` in place — no new row, same session ID — and deep investigation launches. *(§3.2 promotion, FR-1; slice-3 FR-002 mutable set)*

---

### User Story 3 - Joining, not duplicating, an open session (Priority: P2)

The open-time retrieval read doubles as duplicate detection: when an open row (non-terminal status — `open` or `handoff`) with the same source ID exists, the command offers **join** — rehydrate from the latest checkpoint, take ownership by writing the responder field — or explicitly open a separate session; it never silently duplicates. Matching is by source ID plus non-terminal status, never by recomputing the session ID (whose embedded date differs across days).

**Why this priority**: Handoff (FR-3a) is a headline flow, but it rides US1's machinery. P2.

**Independent Test**: Seed an open row for the same source ID (dated yesterday); run the open flow: assert the join offer is surfaced, join rehydrates from `latest_checkpoint` and writes the ownership take-over, and "separate" produces a distinct row only on explicit choice.

**Acceptance Scenarios**:

1. **Given** a seeded open row with the same source ID from a prior day, **When** `/page` or `/incident` runs, **Then** the join-vs-separate choice is surfaced explicitly and nothing is written until the responder chooses. *(§3.2 step 6, §4, D-8; slice-3 FR-009)*
2. **Given** the responder chooses join, **When** rehydration runs, **Then** state loads from the row's `latest_checkpoint` (following an overflow link if present) and the take-over writes `responder: <me> @ <timestamp>`. *(§4; slice-3 FR-005/FR-009)*
3. **Given** the responder explicitly chooses separate, **When** the new session opens, **Then** a distinct row is appended and the marker tracks the new session only. *(§3.2 step 6)*

---

### User Story 4 - Close writes everything down, in order, and proves it (Priority: P1)

`/close` drafts the diary entry (configured template if present, else matching the diary's existing format via its recent entries — the drafting inputs are slice-8's surface), with causal fields — root cause, contributing factors, action items — explicitly labeled as proposals requiring the responder's curation. After approval, it executes the slice-3 dual-write: diary first (capturing its link), then artifact upload — the staged transcript, the trace under its uploaded name, the checkpoint history, and the generated report with the timeline derived from the tool trace plus checkpoint history, never prose recall — then the session-row update with all close-time fields, then row read-back; only a successful read-back deletes the local session state (the protocol's deletion-is-cleared). Diary failure never blocks the row: the row lands `diary_pending: true` with a retry queued. If duplicate open rows share the source ID, close merges them — earliest canonical, links folded in, duplicate `superseded`.

**Why this priority**: The close write is the must-not-lose write (FR-4b, D-11); the memory flywheel is only as good as what lands here. P1.

**Independent Test**: Run the documented close steps against the mock with a fixture session (temp local-state dir, staged fixture artifacts): assert write ordering via the mock write log (diary → artifacts → row), read-back-then-delete marker semantics, `diary_pending` on seeded diary failure, causal-field proposal labeling in the draft artifact, and merge-at-close leaving exactly one non-`superseded` row.

**Acceptance Scenarios**:

1. **Given** an approved draft, **When** the dual-write runs, **Then** the mock write log shows diary append → artifact writes → row update, in that order, and the row carries the diary link and artifact links. *(§4 close steps 2–5; slice-3 FR-008)*
2. **Given** the row read-back succeeds and echoes the session ID, **When** close completes, **Then** the local session directory is deleted — deletion *is* the cleared state; a failed read-back leaves it in place for the session guard to catch. *(§4 step 5, D-11; local-state protocol v1)*
3. **Given** a diary write failure, **When** close continues, **Then** the row still lands with `diary_pending: true` and a queued retry — the row write is never skipped. *(§4 step 6, §9; slice-3 FR-008)*
4. **Given** the draft, **When** it is presented for approval, **Then** causal fields are explicitly labeled as proposals and factual fields are auto-filled — no causal proposal is promoted to fact without the responder's decision. *(§4 step 1, FR-8; Constitution V)*
5. **Given** two open rows sharing a source ID at close, **When** the merge runs, **Then** the earliest row is canonical, the duplicate's artifact links fold in, and the duplicate is `status: superseded`. *(§4; slice-3 FR-009)*
6. **Given** the artifacts, **When** the report and timeline are generated, **Then** the timeline derives from the tool trace and checkpoint history — timestamped, complete, never reconstructed from prose recall — and the trace uploads under its documented artifact name. *(§4 steps 3–4, D-5, D-12; slice-3 FR-004)*

---

### Edge Cases

- **`/close` with no open session** (no marker): reports "no open session", performs no writes. *(informed default; the protocol defines no resting closed state to act on)*
- **Alert fetch fails at open**: the session still opens — marker, row, briefing degrade to "alert context unavailable" with the failure surfaced; a broken alerting tool must not block session capture. *(informed default from §9's fail-soft posture; see Assumptions)*
- **Catalog resolution fails**: the fingerprint falls down the slice-3 resolution ladder (responder asked once → alert tag → rule-based), `catalog_resolved: false` lands on the row, and the briefing notes the downgrade. *(§9; §5.2, D-19; slice-3 FR-003)*
- **Triage returns nothing usable** (validation fails twice): checkpoint zero persists flagged `schema_valid: false` per slice-3, the responder is told, and the session continues — a schema fight never blocks a 3am briefing. *(§5.4, D-14; slice-3 FR-006)*
- **Shell adapter absent or its calls fail mid-flow**: every shell step degrades to printed links/messages; the investigation flow is unaffected. *(§6.3 degraded, §9, FR-26)*
- **Second `/page` for a different alert while a session is open**: out of scope for v1 commands — the local-state protocol pins one session at a time per workspace directory; the command surfaces the open session and offers `/close` first. *(local-state protocol v1 "one session at a time"; see Assumptions)*
- **Ownership lost before close** (another responder took over): close's row update hits the slice-3 pre-write ownership check, goes read-only, and reports the take-over instead of writing. *(§4, D-18; slice-3 FR-009)*
- **Marker exists but its session row was never confirmed** (crash between marker write and row append): re-running `/page` for the same source finds no open row, offers a clean re-open, and the stale marker is replaced — the session guard's warning covers the crashed session's end. *(informed default; D-11)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `/page <alert-id>` MUST execute the documented open flow in order: cheap preflight (config presence; green-stamp match per slice-4 semantics — no probes on the happy path; missing config stops with "run /setup"; missing/stale stamp auto-runs responder-mode setup), session-ID computation (`{type}-{source-id}-{ISO date}`), marker write, shell workspace open, alert context + flap history fetch, catalog resolve + fresh runbook fetch, tier-0 retrieval, triage spawn, verdict validation, checkpoint-zero persist, row append (`status: open`), row read-back, marker confirmation, briefing. *(§3.2; D-8; NFR-1)*
- **FR-002**: The commands are the local-state protocol's designated marker writer: marker created at open with the protocol's fields; `open_write_confirmed: true` set only after the open-time append's read-back; the whole local session directory deleted only by a confirmed close — this slice writes exactly the protocol shapes slice 2 reads. *(local-state protocol v1; D-11; Constitution II)*
- **FR-003**: `/incident <incident-id>` MUST run the open flow with incident defaults — `session_type: incident`, deep investigation proposed immediately after triage (responder confirms; auto-launch per configuration) — and, invoked inside an open page session, MUST promote in place: re-tag `session_type` on the existing row, launch deep investigation, create no new session. *(§3.2; FR-1; §3.4 FR-5f)*
- **FR-004**: The open-time retrieval read MUST double as duplicate detection: an existing row with the same source ID and non-terminal status (`open` or `handoff`) triggers an explicit join-vs-separate choice — join rehydrates from `latest_checkpoint` (following overflow links) and writes the ownership take-over; separate appends a distinct row only on explicit choice; nothing silently duplicates. *(§3.2 step 6, §4, D-8; slice-3 FR-005/FR-009)*
- **FR-005**: The triage verdict MUST pass validation before persisting as checkpoint zero, with the slice-3 failure path (one re-prompt; persist flagged on second failure, surfaced to the responder). This slice owns the orchestration step — invoking validation and persisting — not triage internals (slice 6). *(§3.2 step 8, §5.4, D-14; slice-3 FR-006)*
- **FR-006**: The briefing MUST deep-link every cited claim's evidence and, when a shell adapter is configured, navigate the top-cited dashboard into view; degraded mode prints links — full function, no shell. *(§3.2 step 9; FR-2, FR-9, FR-26)*
- **FR-007**: `/close` MUST draft the diary entry from the configured template when present, else match the diary's existing format from its recent entries (the read surface is slice 8's; this slice consumes it), auto-filling factual fields and labeling all causal fields — root cause, contributing factors, action items — as explicit proposals requiring responder curation before any write. *(§4 close step 1; FR-4c, FR-8; Constitution V)*
- **FR-008**: After approval, `/close` MUST execute the slice-3 dual-write in order — diary (capturing its link) → artifact upload → row update with all close-time fields → row read-back — deleting the local session directory only on read-back success; on diary failure the row still lands with `diary_pending: true` and a queued retry. *(§4 close steps 2–6; FR-4b; slice-3 FR-008; local-state protocol v1)*
- **FR-009**: Close-time artifacts MUST be the hook-captured files uploaded mechanically — the staged transcript, the local trace under its documented uploaded name, the checkpoint history, and the generated report — with the structured timeline derived from the tool trace plus checkpoint history, never from prose recall. *(§4 close steps 3–4; D-5, D-12; slice-3 FR-004; local-state protocol v1 staging)*
- **FR-010**: `/close` MUST merge duplicate open rows sharing the source ID: earliest row canonical, artifact links folded in, duplicate marked `superseded`; and close's row writes MUST honor the slice-3 pre-write ownership check, going read-only with a take-over report when displaced. *(§4, D-18; slice-3 FR-009)*
- **FR-011**: All command prose MUST reference capabilities and operations only — no concrete MCP server or tool names — and every shell interaction MUST go through the shell-adapter interface with a degraded path that prints links/messages. *(Constitution VII; §6.3, FR-22, FR-26)*
- **FR-012**: Every requirement above MUST be exercised by hermetic contract tests against `bb-mock-mcp` with a temporary local-state directory: full open→close simulation asserting mock write-log ordering, marker lifecycle states, join-vs-separate, promotion re-tag (update not append), diary-failure, ownership-displacement, and merge-at-close — asserting on artifacts, never prose, no credentials, no network. *(design §10 layer 2; Constitution VIII)*
- **FR-013**: This slice ships no storage code and no agent definitions: deliverables are the three command documents and tests; triage/deep internals (slice 6), catalog parsing (slice 7), diary format matching (slice 8), and the shell adapter implementation (slice 9) are consumed surfaces, each already bounded by its own slice. *(Constitution I; §1 build order)*

### Key Entities

- **Session marker / local session directory**: The slice-2 protocol's `marker.json` and `.bb-session/` lifecycle — this slice is its designated writer (create, confirm, delete).
- **Session row**: The slice-3 schema row these commands append, re-tag, checkpoint, and close.
- **Checkpoint zero / latest checkpoint**: The validated verdict persisted at open; the rehydration source at join.
- **Briefing**: The responder-facing synthesis presented at open — every claim deep-linked to `{url, excerpt}` evidence.
- **Diary draft**: The close-time entry — factual fields auto-filled, causal fields labeled proposals.
- **Green stamp**: Slice-4's local artifact; preflight's trusted input, never probed at 3am.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement maps to at least one passing hermetic contract test; the suite is green on every commit via the standard verify gate.
- **SC-002**: In 100% of simulated happy-path opens, the mock write log records zero probe/verification calls before the session-open writes (the preflight is trust-the-stamp cheap), and the marker reaches `open_write_confirmed: true` only after the row read-back.
- **SC-003**: In 100% of simulated promotions, the store shows an update to the existing row (`session_type: incident`) and no second row for the source ID.
- **SC-004**: In 100% of join simulations, no store write occurs before the explicit join/separate choice; join writes exactly the ownership take-over; separate appends exactly one new row.
- **SC-005**: In 100% of simulated closes, write ordering (diary → artifacts → row), read-back-then-delete marker semantics, and — under seeded diary failure — the `diary_pending: true` row all hold; the local directory survives every failed read-back.
- **SC-006**: In 100% of close drafts, causal fields carry the explicit proposal label and no causal content appears outside labeled fields (asserted on the draft artifact).
- **SC-007**: A full open→close simulation completes with every artifact assertion passing and zero operations outside the operation contract.

## Assumptions

- **Consumed surfaces are fixtures until their slices land**: triage (slice 6) is simulated by a fixture verdict; catalog resolution (slice 7) by fixture catalog data; diary recent-entries (slice 8) by mock `read_recent`; shell (slice 9) by the degraded path plus a fixture adapter. The command flows are testable now because each consumed surface has a pinned contract.
- **Alert-fetch failure keeps the session opening** (informed default): §9 pins fail-soft for shell and catalog but is silent on alerting-fetch failure at open; a dead alerting tool must not prevent session capture, so the flow proceeds with the failure surfaced. Required-capability *absence* still fails loudly at session start per §9 — this default covers transient call failure, not missing capability.
- **One session at a time per workspace directory** (local-state protocol v1): a second concurrent `/page` in the same directory is out of scope for v1; the command surfaces the open session. Multi-session workspaces are a protocol-version concern, not a command concern.
- **Crashed-open recovery** (marker present, row never confirmed, session gone): re-running the open command replaces the stale marker after finding no open row — informed default; D-11's guard covers the crashed session's own end, and the protocol's one-session rule needs an unbrick path.
- **Preflight stamp semantics are slice 4's**: matching-only staleness, no probes; this slice consumes the stamp, never redefines it.
- **Deep-investigation launch mechanics** (spawn, ledger) are slice 6's; this slice pins only the orchestration commitments: proposal-after-triage for incidents, launch-on-promotion, responder confirmation (with the configured auto-launch exception).
- **Briefing content/format** is slice 6's investigation-skill surface (design `references/briefing.md`); this slice pins the command-level properties: deep-linked evidence, degraded-mode links, top-cited-dashboard navigation.
- **Session-ID date** is the open-time date in ISO 8601 (`YYYY-MM-DD`), UTC — informed default; the design writes `<ISO date>` without pinning a timezone, and cross-day handoff never recomputes IDs, so the choice only affects cosmetic ID readability.
