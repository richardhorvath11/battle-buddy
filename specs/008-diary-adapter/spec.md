# Feature Specification: Diary Adapter

**Feature Branch**: `008-diary-adapter`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 8 of the battle-buddy MVP (design `bb-technical-design.md` §6.2 including the v1.2.1 ordering commitment, §4 close steps 1–2, §2 division of knowledge; PRD FR-4a–4c; Constitution I, V, VII): the team-diary surface — the adapter interface behind the dual-write's first write, format resolution, and the read interface — expressed as diary skill prose plus hermetic tests. CI gates the documented decision rules via the slice-7 testing model (dev-only reference encoding); drafting *quality* is scenario-harness territory.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The close-time entry reads like the team wrote it (Priority: P1)

At close, the drafting step resolves the entry format: when the team has configured a template, the template wins; otherwise the adapter reads the diary's most recent entries (~5) and the draft matches their observed structure — headings, date format, field order. Either way the structured session row is completely unaffected by diary formatting: the diary is the team's readable artifact, the row is the machine's.

**Why this priority**: FR-4c is the adapter's core promise — the harness joins the team's diary culture instead of imposing one. P1.

**Independent Test**: Run the format-resolution decision rules (via the dev-only reference encoding) over fixture states: template-configured → template selected; no template + fixture entry sets → the extracted structure (headings, date format, field order) matches golden expectations; the row-formatting independence is a documented-property check.

**Acceptance Scenarios**:

1. **Given** a configured template, **When** format resolves, **Then** the template is used and no recent-entry read is needed for formatting. *(§6.2, FR-4c)*
2. **Given** no template and a diary with consistent recent entries, **When** format resolves, **Then** the draft structure mirrors the observed headings, date format, and field order from the last ~5 entries. *(§6.2, FR-4c)*
3. **Given** any diary formatting outcome, **When** the session row is written, **Then** row fields are identical regardless of diary format — formatting never leaks into the structured record. *(§6.2 "The structured session row is unaffected")*

---

### User Story 2 - The first write lands and hands back its link (Priority: P1)

The dual-write's first write goes through the adapter interface: `write_entry(content) → url`. The returned link is what the close flow carries into the session row's `diary_url` — the linkage that makes the diary entry findable from the store forever. The adapter appends to the team's configured diary through the diary capability; it never creates diaries, never writes anywhere else.

**Why this priority**: The entry→link→row linkage is the dual-write's connective tissue (FR-4a/4b); without the returned link the row can't reference the diary. Co-P1.

**Independent Test**: Drive the documented write flow against `bb-mock-mcp`: the append returns a link, the link is the value handed onward for the row's diary field, and the mock's write log shows exactly one diary append per close.

**Acceptance Scenarios**:

1. **Given** an approved entry, **When** the adapter writes it, **Then** the append operation returns a stable link, and that link is what the close flow receives for the row. *(§6.2 interface; §4 close step 2 "captures its URL"; operation contract v1 `append_entry` → `{link}`)*
2. **Given** the write flow, **When** inspected, **Then** it appends to the configured diary via the diary capability only — no diary creation, no alternate destinations. *(§6.2; Constitution VII)*

---

### User Story 3 - Recent entries always arrive newest-first (Priority: P2)

The read interface is `read_recent(n) → entries[]`, ordered most recent first — the v1.2.1 interface commitment: adapters over oldest-first stores reverse on read, so consumers never re-sort. The format-matching flow consumes this ordering directly (the first entries returned are the freshest structure to match).

**Why this priority**: The ordering commitment exists because a reviewer once caught a spec citing an ordering the contract never stated (design v1.2.1 changelog); consuming it correctly keeps that contract honest. P2.

**Independent Test**: Against the mock (which implements the contract's most-recent-first pin), run the documented consumption flow: the entries used for structure extraction are the n most recent, in order, with no consumer-side re-sort step anywhere in the documented flow.

**Acceptance Scenarios**:

1. **Given** a diary with dated fixture entries, **When** `read_recent(5)` is consumed per the skill's flow, **Then** the five most recent entries arrive newest-first and are used as-is — the skill documents no re-sorting. *(§6.2 v1.2.1; operation contract v1 `read_recent` "most recent first")*
2. **Given** a diary with fewer than n entries, **When** read, **Then** all available entries return (newest-first) and format matching proceeds with what exists. *(informed default; contract v1 pins n ≥ 1, not diary size)*

---

### Edge Cases

- **Empty diary, no template**: nothing to match — the draft uses the skill's documented minimal default structure (date-titled entry with the standard close-report sections), and the structure is offered to the team as a template candidate. *(spec-pinned default — see Assumptions)*
- **Recent entries with inconsistent structure**: match the most recent entry's structure (freshest wins); the skill says so explicitly rather than leaving the model to average styles. *(spec-pinned default — see Assumptions)*
- **Template configured but malformed/empty**: fall back to match-recent with the template problem surfaced — a broken template must not block the close draft. *(informed default from the fail-soft posture)*
- **Very long recent entries**: structure extraction reads headings/date/field-order, not full content; the skill bounds what the matching step needs. *(informed default)*
- **Diary write failure**: not this slice's path — the close flow's `diary_pending` handling (slice 5, slice 3) owns it; the adapter's job is the attempt and the honest error. *(§4 step 6; slice-3 FR-008; slice-5 FR-008)*
- **Causal content in the draft**: the adapter carries the labeling through — proposal labels applied by the close flow's drafting rules (slices 5/6) survive format matching verbatim; format resolution never strips or rewords labeled fields. *(Constitution V; slice-5 FR-007)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The diary skill MUST document the adapter interface as the skill-level contract: `read_recent(n) → entries[]` ordered most recent first (the v1.2.1 commitment — adapters over oldest-first stores reverse on read; consumers never re-sort) and `write_entry(content) → url` (the dual-write's first write; the returned link is the row's diary linkage). *(§6.2; operation contract v1 diary ops)*
- **FR-002**: Format resolution MUST be: configured template wins when present; otherwise read the last ~5 entries and match their observed structure — headings, date format, field order; a malformed template falls back to match-recent with the problem surfaced. *(§6.2, FR-4c)*
- **FR-003**: The structured session row MUST be unaffected by diary formatting in every path — format resolution touches entry presentation only, never row fields. *(§6.2)*
- **FR-004**: The v1 implementation prose MUST target the team's configured diary via the diary capability (append-only, no diary creation); Confluence, Notion, and git-markdown adapters are explicitly deferred. *(§6.2; PRD §8)*
- **FR-005**: The skill MUST document the drafting handoff: inputs are the session row fields and artifacts the close flow supplies; output is entry content in the resolved format; causal-field proposal labels applied by the close flow's rules pass through format matching verbatim — the adapter never strips, rewords, or promotes them. *(§4 close step 1; Constitution V; slice-5 FR-007 boundary)*
- **FR-006**: All skill prose MUST reference the diary capability's operations only — no concrete MCP server or tool names. *(Constitution VII)*
- **FR-007**: Hermetic tests MUST cover: the format-resolution decision rules and structure-extraction golden cases (fixture entry sets → expected headings/date-format/field-order) via the dev-only reference encoding (slice-7 testing model — rules-coherence gate; drafting quality is scenario-harness territory, out of CI scope); the read-ordering consumption flow against `bb-mock-mcp` (newest-first honored, no re-sort); and the entry→link→row linkage through the operation contract (append returns the link the flow hands onward) — artifacts, never prose; no credentials, no network. *(design §10; Constitution VIII; slice-7 FR-008 precedent)*
- **FR-008**: This slice ships skill prose and tests only; the close flow that invokes drafting and executes the dual-write is slice 5, and causal-labeling requirements are slices 5/6 — consumed boundaries, not scope. *(Constitution I; slice map)*

### Key Entities

- **Adapter interface**: The two-operation skill-level contract (`read_recent`, `write_entry`) — the diary's entire surface to the rest of the system.
- **Format resolution**: The template-vs-match-recent decision plus the structure-extraction rules (headings, date format, field order).
- **Entry structure**: The extracted shape of recent entries; the match target when no template exists.
- **Reference encoding**: The dev-only test-side executable form of the decision/extraction rules (slice-7 model); never shipped.
- **Diary link**: The stable URL returned by the write; the session row's `diary_url` value.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement maps to at least one passing hermetic test; the suite is green on every commit via the standard verify gate.
- **SC-002**: 100% of format-resolution fixtures classify correctly: template-configured always selects the template; template-absent always matches recent structure; malformed-template always falls back with the problem surfaced.
- **SC-003**: 100% of structure-extraction golden cases match (headings, date format, field order), including the empty-diary minimal-default and inconsistent-entries freshest-wins cases.
- **SC-004**: In 100% of simulated write flows, the returned link equals the value handed onward for the row's diary field, and the mock write log records exactly one diary append per close.
- **SC-005**: The documented consumption flow contains zero re-sort steps, and ordering fixtures confirm newest-first arrival end-to-end — the v1.2.1 commitment consumed as pinned.
- **SC-006**: Zero concrete MCP server or tool names in the skill prose, verified mechanically.

## Assumptions

- **Empty-diary default structure**: a minimal date-titled entry with the standard close-report sections, offered to the team as a template candidate — spec-pinned; §6.2 covers only template-present and entries-present cases.
- **Inconsistent recent entries**: freshest-wins (match the most recent entry's structure) — spec-pinned; deterministic and testable where style-averaging is neither.
- **The ~5 read depth** follows §6.2's "last ~5 entries"; the exact n is a configuration default pinned at plan time (the design's tilde invites a config knob, not a hard constant).
- **Malformed-template fallback** is an informed default extending the repo's fail-soft posture; the design doesn't address broken templates.
- **Testing model** is slice 7's: CI tests execute a dev-only reference encoding of the documented decision/extraction rules over fixtures; whether a live agent drafts well is the scenario harness's question. Structure extraction here is rule-shaped (headings/date/field-order patterns), the reference encoding's home turf.
- **Template location/format** (where the configured template lives — workspace config vs a diary-adjacent document) is pinned at plan time; the decision rule (template wins) is independent of its storage.
- **Slice-5/6 dependency status**: the close flow (slice 5) and drafting/labeling rules (slices 5/6) are authored on open PRs (#10, #12); this spec consumes their pinned boundaries and declares the status.
