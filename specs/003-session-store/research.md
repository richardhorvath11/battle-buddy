# Research: Session-Store Conventions (plan-time pins)

Every item the spec deferred to plan time, resolved. Format per speckit: decision /
rationale / alternatives considered.

## R1 — Checkpoint-history local accumulation file

**Decision**: History accumulates at `.bb-session/staging/checkpoints.jsonl` — one JSON
line per checkpoint, appended at checkpoint-write time; uploaded at close under the
artifact name `checkpoints.jsonl`. Recorded in
`specs/002-deterministic-layer/contracts/local-state-protocol.md` as an additive
`staging/` entry in the same change (that doc's versioning duty: "changes require … a
same-change update of every consumer — never silent"). No protocol version bump: the
addition changes no existing file's format and no existing consumer's parse — the same
standard the protocol itself applied when recording the `denied:*` outcome extension
without a bump.

**Rationale**: `staging/` is exactly the protocol's "files awaiting close-time upload"
area (it already holds `transcript.md` with the same accumulate-locally-upload-at-close
lifecycle). The artifact contract has no append op (spec assumption), so local
accumulation is forced; putting it anywhere but `.bb-session/` would invent a second
local-state root.

**Alternatives considered**: a new top-level `.bb-session/checkpoints.jsonl` (rejected:
staging/ is the defined upload-staging area; top level is protocol machinery —
marker/trace/counters/agents); keeping history only in the row (rejected by design D-3:
cell limits); protocol version bump to `bb.local.v2` (rejected: nothing existing
changes shape; a bump would force slice-2 consumer churn for an addition).

## R2 — Schema version representation in a live Sheet

**Decision**: The schema documentation declares `schema_version: bb.schema.v1`
(versioned like every other `bb.*` contract). In a live Sheet, the version lives in a
**header-row sentinel cell**: row 1, one column to the right of the last schema column,
holding the literal version string (e.g. `bb.schema.v1`). It is not a data column — no
session row carries it — so the column set stays exactly §5.1's.

**Rationale**: §2.1's version seam needs `/doctor` (slice 4) to read the version
cheaply; the header row is already the thing `/setup` writes and `/doctor` validates
("Sheet reachable with expected header row", design §7.2), so the sentinel rides an
existing read. Contract v1 has no header/cell-level operation, so no representation is
contract-testable in this slice — the pin is documentation for slice 4, and this slice's
SC-006 test verifies the *documented* version string and column list instead.

**Alternatives considered**: a `schema_version` data column on every row (rejected:
redundant per-row storage; mutation-policy noise); a named range (rejected: not
expressible through any operation the contract or the recommended roster guarantees);
a config-block-only version (rejected: §2.1 explicitly versions the Sheet itself so
`/doctor` can catch a workspace whose Sheet predates its config).

## R3 — Retrieval prose placement

**Decision**: The normative retrieval conventions land at
`skills/session-store/references/retrieval.md` (this slice). Slice 6's investigation
skill will *reference* it from `skills/investigation/references/retrieval.md` or
directly — either way, the session-store copy is the single normative text, as the
spec's assumption already defaults.

**Rationale**: This slice owns the conventions and their tests; retrieval is a store
convention (it reads store columns and statuses) before it is investigation methodology.
Design §3.1's sketch placing `retrieval.md` under the investigation skill is a routing
choice for the *consumer*, not ownership — flagged in the spec for design-doc
reconciliation.

**Alternatives considered**: land it under `skills/investigation/` now (rejected: that
skill doesn't exist until slice 6; shipping a lone reference file inside an absent skill
is a broken bundle); duplicate normative text in both (rejected: two sources of truth).

## R4 — Executable form of the conventions in tests

**Decision**: A dev-only helper module `tests/helpers/store_flows.py` implements each
documented flow as a deterministic script over a `MockMcp` instance plus a local state
dir: `open_session`, `retrieve_candidates` (stages 1–3 preparation), `write_checkpoint`
(ownership re-read → validate → guard/overflow → row update → history append),
`take_over`, `close_session` (diary → artifacts → row update → read-back → marker
clear), `merge_duplicates`. Each step carries a comment citing the skill section it
executes; contract tests drive these flows and assert on mock artifacts
(`write_log.entries`, `records.records`, `artifacts.files`) and the local state dir.

**Rationale**: FR-011 demands the conventions be *exercised*, and prose can't run. The
flow scripts are to the skill docs what `bb-mock-mcp` is to the operation contract: the
executable specification, living in dev-only test space. FR-012 stays intact — nothing
under `tests/` ships (the slice-1 packaging test fences it mechanically).

**Alternatives considered**: inline the flows in each test module (rejected: the close
flow appears in US2, US4, and US5 tests — divergent copies would let tests pass while
disagreeing about the convention); shipping a `bb-store` helper (rejected outright:
FR-012 / Constitution I — that is the tier-1 server's job).

## R5 — SC-006 mechanical cross-check design

**Decision**: `tests/contract/test_store_schema_doc.py` owns a canonical column tuple
(name + mutation class per FR-002) as test-side constants; a parser extracts the column
table from `skills/session-store/references/schema.md` (first markdown table with a
`Column` header) and the test asserts name-set and order equality both ways, plus
mutation-class agreement for every column. `store_flows.py` builds rows only through the
same constants, so a doc column the tests never write — or a test field the doc never
documents — fails the gate.

**Rationale**: Two-sided check with exactly two sides (doc, tests) — introducing a third
machine-readable column file would add a drift pair instead of removing one. Parsing the
doc keeps the *human-readable artifact* authoritative, which is the point of
documentation-as-schema.

**Alternatives considered**: JSON column manifest consumed by both doc generation and
tests (rejected: doc becomes generated output, violating the docs-are-the-deliverable
model and adding a build step); grep-for-each-name (rejected: passes on stale tables
that mention names in prose).

## R6 — FR-003 consistency check (doc ↔ helper ↔ corpus)

**Decision**: `tests/contract/test_fingerprint_reference.py` asserts: (a) the version
tag stated in `references/fingerprint.md` equals `bb_fingerprint.VERSION` (`bb.fp.v1`);
(b) it equals the golden corpus's version field; (c) every worked example in the doc
(input pair → 16-hex output, marked as a fenced example block) recomputes exactly via
the real helper. The doc carries ≥2 worked examples (one catalog-resolved, one ladder
rung 4) so (c) has teeth.

**Rationale**: FR-003 names the three artifacts and demands a consistency check tying
them together; version-tag equality catches silent rule drift at the cheapest point, and
example recomputation catches a doc whose prose rules diverge from the helper while the
tag still matches.

**Alternatives considered**: re-deriving the normalization rules from the doc prose and
executing them (rejected: building a second fingerprint implementation is exactly the
drift-generator D-4 forbids); corpus-only check without doc examples (rejected: leaves
the documented prose untested).

## R7 — Skill file layout

**Decision**: Four files: `SKILL.md` (lifecycle conventions: open/close dual-write with
both read-back confirmation points, checkpoint representation + validation gate,
optimistic ownership, artifact layout, failure paths) and three references —
`schema.md`, `fingerprint.md`, `retrieval.md`. No separate lifecycle/ownership reference
files.

**Rationale**: Matches design §3.1's session-store layout exactly (SKILL.md +
schema/fingerprint references) plus retrieval.md per R3. The lifecycle conventions are
the skill's core behavior — the thing an agent loads the skill *for* — while the
references are lookup material (column tables, normalization rules, staged flows).
Progressive disclosure per skill conventions: SKILL.md stays the routing + behavior
layer.

**Alternatives considered**: per-FR reference files (rejected: nine tiny files with
heavy cross-linking; slice-5/6 consumers need the close flow and ownership rules
together, not scattered); everything in SKILL.md (rejected: the column table and
normalization rules are reference lookups, and SC-006/FR-003 tests want stable parse
targets).

## R8 — Schema version identifier value

**Decision**: `bb.schema.v1`, declared in `references/schema.md` alongside the FR-013
stability commitment.

**Rationale**: Follows the established `bb.*.v1` family (`bb.fp.v1`, `bb.verdict.v1`,
`bb.ledger.v1`, `bb.local.v1`, `bb.capabilities.v1`).

**Alternatives considered**: bare `v1` (rejected: the family convention exists and
`/doctor` will compare version strings across seams — uniform namespacing helps).

## R9 — Validation-failure re-prompt in deterministic tests

**Decision**: Fixture *pairs*: an invalid checkpoint document plus its "re-prompted"
successor (fixed, or still-invalid for the second-failure path). `write_checkpoint`
takes an ordered candidate list standing for the produce → re-prompt sequence: validate
first; on failure take the next candidate (the one re-prompt); on second failure
persist the *second* document flagged `"schema_valid": false`. Tests assert the
validator ran (via its real error list), the flag, and that no candidate was dropped.

**Rationale**: The re-prompt is agent behavior (slice 6); what this slice pins and tests
is the *decision procedure* — one retry, then persist-flagged, never drop. An ordered
candidate list is that procedure's deterministic skeleton.

**Alternatives considered**: mocking `bb_validate` (rejected: FR-006 cites the real
validator; slice-2 is in tree — bind to it); testing only the happy path (rejected:
the flagged-persist path is the Constitution II/VI teeth).

## R10 — Diary-retry "queued" representation

**Decision**: `diary_pending: true` on the row *is* the queue. The conventions document
recovery as: any later session (or the close flow of a retry) finds pending entries via
`read_records` with filter `{diary_pending: true}`, writes the diary entry, then updates
the row (`diary_url`, `diary_pending: false`). No local queue file, no new state.

**Rationale**: The row is the durable record that must not be lost (FR-4b); a separate
queue artifact would be a second must-not-lose write with no backstop. Filterable
recovery is contract-expressible (`read_records` field-equality filter) and therefore
testable now.

**Alternatives considered**: a `.bb-session/` retry file (rejected: the session dir is
deleted on confirmed close — exactly when the retry must survive); leaving retry
representation to slice 5 (rejected: US2/AS-3 requires "the diary retry is recorded as a
follow-up" to be testable in this slice; the flag is the record).
