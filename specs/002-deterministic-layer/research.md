# Phase 0 Research: Deterministic Layer

No NEEDS CLARIFICATION markers in the Technical Context; decisions consolidated from the
design, the slice-2 spec, and Claude Code hook-runtime facts. Deferred items the spec
assigned to the plan are resolved here (R5, R6, R9).

## R1 — Hook registration: three scripts, five event bindings

**Decision**: Three shipped scripts with explicit event registrations in `hooks/hooks.json`:

| Script | PreToolUse | PostToolUse | SessionStart | Stop/SessionEnd |
|---|---|---|---|---|
| `guardrail_deny.py` | ✓ deny classes | — | — | — |
| `tool_trace.py` | ✓ turn-cap check (count from trace) | ✓ capture line + tripwire | — | — |
| `session_guard.py` | — | — | ✓ config-presence warning (FR-015) | ✓ marker check + transcript staging |

**Rationale**: Turn-cap *denial* must precede execution (PreToolUse); the `outcome` field
and tripwire need results (PostToolUse) — so `tool_trace.py` binds to both events and
dispatches on `hook_event_name`. The config warning fires once at session start, not on
every call. **Alternative rejected**: one mega-script on all events (harder to test as
pure functions, one crash risks all functions — fail-open blast radius).

## R2 — Local-state protocol v1: `.bb-session/` directory

**Decision**: All session-local state lives in `.bb-session/` at the workspace root
(already gitignored since the harness commit): `marker.json`, `trace.jsonl`,
`staging/transcript.md`. Formats, lifecycle, and versioning are pinned in
`contracts/local-state-protocol.md` — the FR-013 artifact; every assertion in it gets a
unit test (FR-013 acceptance).

**Rationale**: One directory = one cleanup boundary and one documented location for
slices 3/5. **Alternative rejected**: scattering marker/trace next to config (pollutes
workspace root; no single lifecycle).

## R3 — Deny classes as data + two-corpus fixture layout

**Decision**: Deny patterns live in a `DENY_CLASSES` table inside `guardrail_deny.py`
(class name → compiled patterns → message), not a separate config file. Fixtures:
`tests/fixtures/misbehaviors/*.json` (must-block, one file per documented misbehavior,
with source annotation) and `tests/fixtures/benign/*.json` (must-allow, per the spec's
corpus-membership rule). The suite iterates both directories — adding a fixture *is*
extending the gate.

**Rationale**: Shipped behavior must not depend on a loadable config a user could break
(fail-open would then silently disable the layer); in-code table keeps the deny layer
self-contained while the corpus stays data. **Alternative rejected**: user-extensible
deny config (deferred — teams can propose fixtures upstream; local extension is a later
feature with its own safety review).

## R4 — Outcome classification for trace lines

**Decision**: PostToolUse classifies results into `ok | error:auth | error:timeout |
error:other` via a small ordered heuristic table (HTTP 401/403, "permission denied",
"unauthorized", "forbidden" → `error:auth`; timeout strings → `error:timeout`; tool-error
flags → `error:other`). The deny hook's credential-scanning class reads the last N=10
trace lines for `error:auth` (window documented in the protocol doc).

**Rationale**: FR-008's `auth_error` requirement with a bounded, testable heuristic;
window-of-10 keeps the PreToolUse read O(1) (tail read, SC-002).

## R5 — Tripwire heuristics v1 (spec deferred the list to the plan)

**Decision**: Case-insensitive regex families, each with fixture pairs (trip/no-trip):
(1) instruction-override phrases ("ignore (all )?(previous|prior|above) (instructions|context)",
"disregard your (instructions|rules)", "new instructions:"); (2) execution directives
aimed at the agent ("run the following", "execute this command", "you must now");
(3) base64 blobs ≥ 200 chars; (4) tool-call syntax in prose (`<function_calls>`,
`antml:invoke`). Untrusted set v1: `alerting`, `observability` — per the spec's
narrowing; **ticket-shaped deferral discharged**: no ticket capability exists in contract
v1, so no classification is defined; the set grows only with the operation contract
(recorded here as the spec's required plan note).

**Rationale**: Start with high-precision families that have documented attack lineage;
every family ships with both fixture directions so precision regressions are caught.

## R6 — Config read protocol (spec: "this slice defines the read protocol")

**Decision**: Read-only helper shared by the hooks (stdlib `json`): workspace config =
`.claude/settings.json` → `battleBuddy` key. Keys consumed this slice:
`battleBuddy.budgets.triageTurnCap` (int, default **15** when absent),
`battleBuddy.bindings` (capability → tool map; absent ⇒ tripwire disabled with one
logged notice per session), plus key-presence itself for FR-015. Malformed JSON ⇒ treat
as absent (fail open), notice in diagnostics.

**Rationale**: D-10 named the location; defaults must exist because slice 4's `/setup`
(which writes these keys) doesn't exist yet.

## R7 — Helpers are libraries with CLI shims

**Decision**: `bb-fingerprint` and `bb-validate` each ship as a module
(`bin/bb_fingerprint.py` importable logic) plus an argv/stdin CLI entry (`bin/bb-fingerprint`),
so hooks and future slices import the same code tests exercise, and skills can shell out.
Exit codes: 0 pass / 1 violation(s) / 2 usage error. `bb-validate` emits the one-pass
violation list as JSON lines on stdout.

**Rationale**: One implementation serving both call styles (D-4's "one shared
implementation" for fingerprints generalized); parseable output feeds the re-prompt flow.

## R8 — Performance budget enforcement (SC-002)

**Decision**: A unit test times 100 sequential invocations of each hook entry function on
fixture payloads and asserts p95 < 100ms per call with a generous margin (fails only on
gross regressions, e.g. accidental subprocess spawns or unbounded trace reads).

**Rationale**: SC-002 needs a mechanical tripwire, not a benchmark suite; the risks are
categorical (O(n) trace scans, imports of heavy modules), which a coarse timing test
catches reliably on any hardware.

## R9 — bb-validate's `phase` enumeration (spec deferred to plan)

**Decision**: `bb.ledger.v1.phase` ∈ `triage-seeded | hypothesis-generation |
evidence-gathering | deep-dive | resolution` (superset of the design §5.4 example's
`evidence-gathering`). The ≥3-live/≥1-fresh invariant is enforced when
`phase ∈ {evidence-gathering, deep-dive}`. Unknown phase values are a schema violation.

**Rationale**: Matches the design's example while giving the ledger a full lifecycle;
closed enumeration keeps validation deterministic (unknown ⇒ error, never guess).
