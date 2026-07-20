# Feature Specification: Session-Store Conventions

**Feature Branch**: `003-session-store`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 3 of the battle-buddy MVP (design `bb-technical-design.md` §4, §5.1–§5.5; decisions D-3, D-4, D-8, D-18, D-19; Constitution I, II, IV, VII, VIII): the tier-0 session-store conventions — the documented Sheet schema, the exact fingerprint reference, the Drive artifact layout, the checkpoint representation, and the three-stage retrieval flow — expressed as session-store skill instructions plus contract tests against `bb-mock-mcp`. Documentation that behaves like a schema; zero shipped storage code.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A repeat incident is recognized before investigation starts (Priority: P1)

A responder pages in on an alert the team has seen before. Following the retrieval conventions, the session's opening read finds the prior session by fingerprint exact match; when no exact hit exists, a keyword filter over affected services, alert signature, and severity selects candidates; the surviving candidates (capped) are handed to the triage agent to rank in context. Rows recording setup smoke tests (`session_type: test`) and merged duplicates (`status: superseded`) never surface at any stage. An exact fingerprint hit where either row was fingerprinted without catalog resolution is presented as a candidate, not a near-certain known issue.

**Why this priority**: Retrieval is the memory flywheel the whole product compounds on (FR-16a); the fingerprint carries the load embeddings would otherwise carry (design §5.2). If these conventions drift, recall silently dies. P1.

**Independent Test**: Seed the mock store with fixture rows (exact-fingerprint match, keyword-overlap rows, `test` and `superseded` rows, an unresolved-catalog match); execute the documented retrieval steps as deterministic reads through the operation contract; assert the candidate set at each stage — no agent, no credentials, no network.

**Acceptance Scenarios**:

1. **Given** a seeded prior session whose `fingerprint` equals the incoming session's fingerprint, **When** stage 1 (fingerprint exact-match) runs, **Then** that row is returned as a near-certain known-issue candidate. *(§5.5 stage 1)*
2. **Given** no exact-fingerprint hit but seeded rows overlapping on `services`, `alert_signature`, or `severity`, **When** stage 2 (keyword filter) runs, **Then** exactly the overlapping rows are selected as candidates. *(§5.5 stage 2)*
3. **Given** seeded rows with `session_type: test` or `status: superseded` that would otherwise match at any stage, **When** any retrieval stage runs, **Then** those rows appear in no candidate set. *(§5.5)*
4. **Given** an exact-fingerprint hit where either row carries `catalog_resolved: false`, **When** the match is classified, **Then** it is downgraded from "near-certain known issue" to "candidate". *(§5.2, §5.5, D-19)*
5. **Given** more matching rows than the documented candidate cap, **When** stage 3 (agent-ranked in-context) is prepared, **Then** at most the cap (20 rows) is passed on, and the truncation is stated, never silent. *(§5.5 stage 3)*

---

### User Story 2 - A closing session's record lands durably, in the documented order (Priority: P1)

At close, the writes happen in the pinned order: the diary entry first (capturing its link), then the session artifacts to the artifact store, then the session-row update carrying the fingerprint, all schema fields, the diary link, and the artifact links — followed by reading the row back and confirming its `session_id`. Only a successful read-back clears the local session marker (the slice-2 protocol's deletion-is-cleared state). If the diary write fails, the row still lands, flagged `diary_pending: true`, with a retry queued — the row write is the one that must not be lost.

**Why this priority**: The dual-write with read-back is the must-not-lose write of Constitution II and FR-4b; the deterministic detector (slice 2's session guard) is only as good as the convention that defines "confirmed." P1.

**Independent Test**: Simulate the close flow as a deterministic script against the mock store: assert diary-before-row ordering from the mock's write log, read-back success as the marker-clearance precondition, and the diary-failure path landing the row with `diary_pending: true` — asserting on artifacts (rows, write log, marker file), never prose. *(design §10 layer 2)*

**Acceptance Scenarios**:

1. **Given** a close flow executed per the conventions, **When** the mock's write log is inspected, **Then** the diary append precedes every artifact write, which precede the session-row update — in that order, every run. *(§4 close steps, FR-4b)*
2. **Given** the session-row update has been written, **When** the read-back returns the row with the expected `session_id`, **Then** and only then is the local session marker cleared. *(§4, D-11; local-state protocol v1)*
3. **Given** a diary write that fails, **When** the close flow continues, **Then** the session row still lands with `diary_pending: true` and the diary retry is recorded as a follow-up — the row write is never skipped or reordered to compensate. *(§4, §9, FR-4b)*
4. **Given** a read-back that fails or returns a mismatched row, **When** the close flow evaluates it, **Then** the marker is not cleared — leaving the slice-2 session guard to warn loudly at session end. *(§4, D-11)*

---

### User Story 3 - An interrupted investigation resumes from its last checkpoint (Priority: P2)

Every checkpoint write keeps the latest state in the session row (`triage_verdict` for checkpoint zero, `latest_checkpoint` thereafter) for one-read resume, while the full history appends to the session's checkpoint artifact file. A checkpoint whose serialized form exceeds the cell guard is not truncated: the cell holds an overflow pointer `{"overflow": "<link>", "seq": n}` and readers follow the link. Before any checkpoint write, the document passes validation (slice 2's `bb-validate`); on failure the producing agent is re-prompted once, and a second failure persists the checkpoint flagged `"schema_valid": false` rather than losing data.

**Why this priority**: Pause/resume/handoff (FR-3a) rides entirely on this representation (D-3); the validation gate is how Constitution VI's invariants stay enforced rather than hoped for. Valuable but consumed by later slices' flows — P2.

**Independent Test**: Write fixture checkpoints (small, exactly-at-guard, over-guard, valid, invalid) through the conventions against the mock store; assert row-cell contents, per-checkpoint history appends, overflow pointers resolving to full state via the artifact read-back op, and the validate-fail path persisting flagged.

**Acceptance Scenarios**:

1. **Given** a validated checkpoint within the cell guard, **When** it is written, **Then** the row cell holds the full checkpoint and one matching entry is appended to the session's checkpoint history artifact. *(§5.4, D-3)*
2. **Given** a checkpoint whose serialized form exceeds 45,000 characters, **When** it is written, **Then** the full document goes to the artifact store, the row cell holds `{"overflow": "<link>", "seq": n}`, and a reader following the link recovers the complete checkpoint — and no store write is ever attempted that the store's field-size limit would reject. *(§5.4, D-3)*
3. **Given** a checkpoint that fails validation twice (original and one re-prompt), **When** it is persisted, **Then** it lands flagged `"schema_valid": false` and the degradation is surfaced to the responder — data is never dropped over a schema fight. *(§5.4, D-14)*
4. **Given** a session resuming from the store, **When** it reads the row, **Then** the latest state is recoverable from `latest_checkpoint` (or its overflow link) alone — one row read, no history scan. *(§5.4, FR-3a)*

---

### User Story 4 - Handoff and duplicate sessions resolve without locking (Priority: P2)

The `responder` field is the ownership token. A responder rehydrating an open session writes `responder: <me> @ <timestamp>` — taking over is a write, not a request. Every checkpoint write re-reads that one cell first; a displaced session's next checkpoint fails the check, is told the session was taken over, and goes read-only. At open, the retrieval read doubles as duplicate detection: an open row with the same source ID triggers an explicit join-or-separate choice (matching on source ID plus open status, never by recomputing the session ID, whose embedded date differs across days). If a true race still produces same-source-ID duplicate open rows, close merges them: the earliest row is canonical, the duplicate's artifact links fold in, and it is marked `status: superseded`.

**Why this priority**: Clean handoff (FR-3a) and duplicate safety without infrastructure the tier-0 store cannot provide (D-18). Consumed by slice 5's commands — P2.

**Independent Test**: Simulate two writers against one mock store: take-over write, displaced writer's pre-write re-read failing, join-at-open detection on a seeded open row, and the merge-at-close producing exactly one canonical row plus one `superseded` row.

**Acceptance Scenarios**:

1. **Given** an open session row owned by responder A, **When** responder B rehydrates it, **Then** B's take-over is a single ownership-field write recording B and a timestamp. *(§4, D-18)*
2. **Given** a displaced session (ownership cell no longer names it), **When** it attempts its next checkpoint write, **Then** the pre-write re-read fails the ownership check, the write is not performed, and the session is told it was taken over and goes read-only. *(§4, D-18)*
3. **Given** an open row with the incoming session's source ID (opened yesterday, so its session ID differs), **When** a responder opens a session on that source, **Then** the conventions surface join-vs-separate explicitly — matching on source ID and open status, never on a recomputed session ID — and never silently duplicate. *(§4, D-8)*
4. **Given** two open rows sharing a source ID at close, **When** the merge runs, **Then** the earliest row is canonical, the duplicate's artifact links are folded into it, the duplicate becomes `status: superseded`, and subsequent retrieval never surfaces it. *(§4, §5.5, D-18)*

---

### User Story 5 - The audit trail is findable and regenerable later (Priority: P3)

Every session owns one artifact folder, named by session ID, holding the four documented artifacts: the full transcript, the tool trace, the checkpoint history, and the investigation report. The locally staged trace file (the slice-2 protocol's `trace.jsonl`) uploads under the documented artifact name `tool-trace.jsonl` — the name mapping is part of the conventions. The report is purely a rendering of the row plus artifacts — regenerable at any later time because every evidence entry is a `{url, excerpt}` pair, never prose alone.

**Why this priority**: The audit trail (NFR-2) and regenerable reports (FR-4d) matter, but nothing else in this slice depends on them. P3.

**Independent Test**: Run the documented artifact-upload conventions against the mock artifact store; assert folder-per-session naming, the four artifact names (including the `trace.jsonl` → `tool-trace.jsonl` mapping), and that the row's artifact links resolve to the uploaded content via the read-back op.

**Acceptance Scenarios**:

1. **Given** a closing session, **When** artifacts upload, **Then** each lands under the session's own folder path with the four documented names — `transcript.md`, `tool-trace.jsonl`, `checkpoints.jsonl`, `report.md`. *(§5.3)*
2. **Given** the locally staged trace file named per the slice-2 local-state protocol, **When** it uploads, **Then** it is stored under the artifact name `tool-trace.jsonl` — the local and uploaded names differ by documented mapping, not accident. *(§5.3; local-state protocol v1, staging)*
3. **Given** a persisted session row and its artifacts, **When** the report is regenerated later, **Then** no information is needed beyond the row and artifact contents — evidence entries carry `{url, excerpt}`, satisfying Constitution IV. *(§5.3, FR-4d, FR-4e)*

---

### Edge Cases

- **Retrieval over an empty or all-excluded store**: no candidates is a normal outcome — the conventions proceed to fresh investigation, never error. *(§5.5)*
- **Checkpoint serialized length exactly at the guard**: at 45,000 characters the checkpoint still fits the cell (the store limit rejects only values above it); overflow triggers strictly above the guard, so no write ever bounces. *(D-3; operation contract v1 field limit)*
- **Artifact upload fails at close**: the row write still proceeds (the must-not-lose write is never blocked); the affected links are omitted from `links`/artifact fields and the gap is surfaced for retry — mirroring the `diary_pending` spirit. *(§4, §9)*
- **Cross-day handoff**: the open row's session ID embeds yesterday's date; matching is by source ID + open status only (D-8) — a recomputed-ID lookup would silently miss and duplicate.
- **Ownership take-over racing a checkpoint write**: the pre-write re-read bounds the damage to at most one stale checkpoint landing before the displaced session observes the take-over; the store's edit history is the audit trail. *(§4, D-18)*
- **Row update targets a session ID the store doesn't know** (e.g. a merge already removed it): the operation's not-found error surfaces to the flow; the conventions treat it as an ownership/merge signal to re-read, never retry-blind. *(operation contract v1 `update_record`)*
- **Fingerprint computed without catalog resolution on either side of a match**: downgrade applies if *either* row carries `catalog_resolved: false` — the flag travels with the row so future matches can honor it. *(§5.2, §5.5, D-19)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The session-store skill MUST document the complete Sheet schema — every design §5.1 column with its name, type, and meaning; `session_id` as row key in the `{type}-{source-id}-{ISO date}` format; and a schema version identifier supporting the versioned upgrade seam. *(§5.1, FR-21, D-8, §2.1)*
- **FR-002**: The schema documentation MUST pin the append-mostly mutation policy: rows are appended at open; thereafter only this enumerated set mutates — `status`, `session_type` (promotion re-tag), `responder` (ownership take-over), `severity` (responder correction), `latest_checkpoint`, and the close-time field group (`closed_at`, `timeline`, `root_cause`, `resolution`, `links`, `runbook_refs`, `diary_url`, `diary_pending`, `report_url`, `artifacts_folder_url`) — with every other field immutable after append. *(§5.1 append-mostly; §3.2 promotion; §4 ownership; reconciliation pinned by this spec — see Assumptions)*
- **FR-003**: The skill MUST include the fingerprint reference: the versioned normalization rules and 16-hex-character construction of design §5.2 and the four-rung service-resolution ladder with `catalog_resolved` semantics — stated as the single documented source of the rules, byte-identical in effect to the slice-2 fingerprint helper, with any rule change requiring a version bump and a documented re-fingerprint pass. *(§5.2, D-4, D-19)*
- **FR-004**: The skill MUST document the artifact layout: one folder per session named by session ID containing `transcript.md`, `tool-trace.jsonl`, `checkpoints.jsonl`, and `report.md`; the local `trace.jsonl` → uploaded `tool-trace.jsonl` name mapping from the slice-2 local-state protocol; and the row fields (`artifacts_folder_url`, artifact links) that make the folder discoverable from the store. *(§5.3; local-state protocol v1)*
- **FR-005**: The skill MUST document the checkpoint representation: latest checkpoint in the row (`triage_verdict` for checkpoint zero, `latest_checkpoint` thereafter); full history appended per checkpoint to `checkpoints.jsonl`; and the cell guard — a checkpoint serialized above 45,000 characters is stored in the artifact store with the row cell holding `{"overflow": "<link>", "seq": n}`, which readers MUST follow. *(§5.4, D-3)*
- **FR-006**: The skill MUST require validation before every checkpoint write (slice 2's validator), with the pinned failure path: one re-prompt of the producing agent with the validator's error list; on second failure, persist flagged `"schema_valid": false` and surface the degradation — never drop the data. *(§5.4, D-14; Constitution II, VI)*
- **FR-007**: The skill MUST document the three-stage retrieval flow — fingerprint exact-match, then keyword filter on `services`/`alert_signature`/`severity` overlap, then agent-ranked in-context with a candidate cap of 20 — with `session_type: test` and `status: superseded` rows excluded at every stage, and stage-1 matches downgraded to "candidate" when either row carries `catalog_resolved: false`. *(§5.5, §5.2, FR-16a, D-19)*
- **FR-008**: The skill MUST document the close-time dual-write: diary entry first (capturing its link), then artifacts, then the session-row update with fingerprint, schema fields, diary link, and artifact links; then read the row back and confirm its `session_id` — only read-back success clears the local session marker. On diary failure the row still lands with `diary_pending: true` and a queued retry. *(§4, FR-4b, D-11; local-state protocol v1)*
- **FR-009**: The skill MUST document optimistic session ownership: the `responder` field as ownership token; take-over as a recorded write (`responder: <me> @ <timestamp>`); a mandatory ownership re-read immediately before every checkpoint write, with a failed check putting the displaced session read-only and informing it of the take-over; join-at-open detection by source ID + open status (never recomputed session ID); and merge-at-close for duplicate open rows — earliest canonical, links folded in, duplicate marked `superseded`. *(§4, D-8, D-18)*
- **FR-010**: All skill prose MUST reference capabilities and operations only (the operation contract's `append_record`, `read_records`, `update_record`, `put_file`, `append_entry`, `read_recent`), never concrete MCP server or tool names. *(Constitution VII; operation contract v1)*
- **FR-011**: Every convention in FR-001–FR-009 MUST be exercised by at least one hermetic contract test against `bb-mock-mcp` through operation contract v1 — write ordering asserted via the mock's write log, durability via read-back operations, retrieval via seeded fixtures — asserting on artifacts, never prose, and running with no credentials and no network. *(design §10 layer 2; Constitution VIII)*
- **FR-012**: This slice MUST ship no storage code: deliverables are skill documentation and tests only; all I/O in tests flows through the operation contract. Any storage-shaped helper need discovered during implementation is a recorded scope decision, not a convenience add. *(Constitution I)*
- **FR-013**: The documented conventions MUST be tier-1-stable: field names, fingerprint construction, and checkpoint formats are declared migration-stable, so future ingestion is a column mapping, not a redesign; the schema documentation records this stability commitment alongside its version. *(§5 preamble, §2.1)*

### Key Entities

- **Session row**: One row per session in the team's session store; the §5.1 column set; row key `session_id`; append-mostly per FR-002.
- **Fingerprint**: 16-hex retrieval key computed from normalized service + alert type per §5.2; carried in the row; paired with `catalog_resolved` recording which resolution-ladder rung produced the service name.
- **Checkpoint documents**: The versioned verdict/ledger JSON documents (`bb.verdict.v1`, `bb.ledger.v1`, defined by design §5.4 and validated by slice 2); this slice defines where they live, not their internal schema.
- **Artifact folder**: The per-session folder of §5.3 with its four named artifacts; addressed from the row by links.
- **Session marker**: The slice-2 local-state protocol's `marker.json`; this slice defines the read-back-then-clear convention that governs its lifecycle end.
- **Operation contract v1**: The slice-1 capability/operation shapes (`tools/bb-mock-mcp/contract.json`) — the only I/O surface the conventions and their tests may name.
- **Mock write log**: The slice-1 test-inspection surface recording ordered mutating operations; the ordering oracle for FR-011.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement FR-001–FR-009 maps to at least one passing contract test; the suite is hermetic (zero credentials, zero network) and green on every commit via the standard verify gate.
- **SC-002**: In 100% of simulated close flows, the mock write log shows diary-append before artifact writes before row update; in 100% of simulated diary-failure closes, the row lands with `diary_pending: true`.
- **SC-003**: In retrieval simulations, the seeded exact-fingerprint match surfaces as a candidate in 100% of runs; `session_type: test` and `status: superseded` rows appear in 0% of candidate sets; every unresolved-catalog exact match is classified "candidate", never "near-certain".
- **SC-004**: In 100% of simulated ownership races, the displaced writer's checkpoint write is not performed after take-over; after merge-at-close, exactly one non-`superseded` row exists per source ID.
- **SC-005**: In 100% of oversized-checkpoint round-trips, the full checkpoint is recovered by following the overflow pointer, and zero store writes are rejected by the field-size limit.
- **SC-006**: The documented column set is mechanically cross-checked: a test compares the schema documentation's column list against the canonical column list the contract tests use, and fails on any divergence.

## Assumptions

- **Slice-2 implementation timing**: slice 2's spec, plan, and local-state protocol are merged, but `bb-fingerprint`/`bb-validate` implementations have not landed yet. Conventions here bind to slice 2's *documented* behavior; contract tests needing the helpers are sequenced after slice-2 implementation merges (or use slice-2 golden-corpus values as fixtures until then). The consistency claim in FR-003 becomes mechanically enforced the moment both are in tree.
- **Mutable-field reconciliation**: design §5.1's append-mostly sentence names only `status`, `latest_checkpoint`, and close-time fields, while §3.2 (promotion re-tags `session_type`), §4 (take-over writes `responder`), and §5.1's own `severity` note ("responder-correctable") each mutate one more field. FR-002 pins the union as the documented policy; flagged here for design-doc reconciliation rather than treated as a conflict.
- **Cell-guard value**: design D-3 says "~45k chars"; this spec pins 45,000 characters, matching the mock's emulated single-field limit, so the overflow convention and the store guard agree exactly.
- **Candidate cap**: design §5.5 says "cap ~20"; this spec pins 20.
- **Retrieval prose placement**: design §3.1 sketches `retrieval.md` under the investigation skill (slice 6) while this slice owns the retrieval *conventions*. Default: the normative retrieval conventions land in the session-store skill's references in this slice; slice 6's investigation skill references them (placement finalized at plan time; the conventions' content is normative here either way).
- **Schema version representation**: the schema documentation declares its version (per the §2.1 version seam); how the version is represented inside a live Sheet (header cell, named range) is pinned at plan time — slice 4's `/setup`/`/doctor` are its consumers.
- **Report generation is out of scope**: `report.md` is generated by the close flow (slice 5, FR-4d); this slice documents only its place in the artifact layout and the row-plus-artifacts regenerability property.
- **Skill enforcement split**: skill prose carries the behavior; the deterministic backstops (marker detection, validation, fingerprint identity) are slice-2 components this slice consumes — per Constitution II, no new enforcement code is introduced here.
