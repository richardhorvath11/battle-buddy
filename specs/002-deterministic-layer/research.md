# Phase 0 Research: Deterministic Layer

No NEEDS CLARIFICATION markers in the Technical Context; decisions consolidated from the
design, the slice-2 spec, and Claude Code hook-runtime facts. Deferred items the spec
assigned to the plan are resolved here (R5, R6, R9).

## R1 — Hook registration: three scripts, five event bindings

**Decision**: Three shipped scripts with explicit event registrations in `hooks/hooks.json`:

| Script | PreToolUse | PostToolUse | SessionStart | SessionEnd |
|---|---|---|---|---|
| `guardrail_deny.py` | ✓ deny classes; on block, appends the `denied:guardrail:<class>` trace line | — | — | — |
| `tool_trace.py` | ✓ turn-cap check (count from `counters.json`); on deny, appends `denied:turn_cap` line | ✓ capture call line (outcome) + tripwire | — | — |
| `session_guard.py` | — | — | ✓ config-presence warning (FR-015) | ✓ marker check + transcript staging |

**Rationale**: Turn-cap *denial* must precede execution (PreToolUse); the `outcome` field
and tripwire need results (PostToolUse) — so `tool_trace.py` binds to both events and
dispatches on `hook_event_name`. Denying hooks append their own `denied:*` lines so every
tool call yields exactly one trace line with no PostToolUse dependency (FR-008 — blocked
calls never reach PostToolUse). The marker check registers on **SessionEnd only**: Stop
fires after every conversational turn and would nag a legitimately-open session; the
blocking variant of FR-011 is deferred until the runtime has a clean blocking
end-of-session point (protocol doc records this). **Alternative rejected**: one
mega-script on all events (harder to test as pure functions, one crash risks all
functions — fail-open blast radius).

## R2 — Local-state protocol v1: `.bb-session/` directory

**Decision**: All session-local state lives in `.bb-session/` at the workspace root
(already gitignored since the harness commit): `marker.json`, `trace.jsonl`,
`counters.json` (seq + per-actor turns, R11), `agents.json` (actor roles, R10), and
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
`battleBuddy.budgets.triageTurnCap` (int, default **15** when absent), and
`battleBuddy.bindings` as an **operation-level map** — `capability.operation → tool name`
per design §7.2/D-13 (e.g. `"storage.append_record": "mcp__sheets__append_row"`); a flat
capability→tool map could not represent one capability whose operations bind to
different tools. Tool→capability classification is the reverse lookup with prefix parse
(protocol doc pins the rule, incl. multi-capability tools). Bindings absent ⇒ tripwire
disabled with one logged notice per session. Key presence itself feeds FR-015. Malformed
JSON ⇒ treated as absent (fail open), notice in diagnostics.

**Rationale**: D-10 named the location and §7.2 the shape; matching slice 4's future
writer exactly is what keeps the tripwire classifying on real rosters. Defaults must
exist because slice 4's `/setup` doesn't exist yet.

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

## R10 — Agent identity: derived actor keys + convention-registered roles

**Decision**: Hook payloads carry no agent name, so identity is derived: actor key = a
stable hash-suffix of the payload's `transcript_path` (distinct per agent instance). Role
mapping (`triage` / `deep` / `specialist:*`) is registered in `.bb-session/agents.json`
by the investigation skill's spawn flow (slice 6) — mechanism here, policy there.
**Unregistered actor ⇒ no turn cap (fail open)**: enforcement without identity would cap
the wrong agents. The triage turn cap is therefore fully deterministic once registration
exists, and harmlessly inert before slice 6 — matching how the config seam (R6) treats
slice 4.

**Rationale**: The one identity signal the runtime reliably provides is the per-agent
transcript path; everything else would be model-cooperation. **Alternative rejected**:
capping all subagents when unregistered (would throttle the deep investigator — a worse
failure than an uncapped triage).

## R11 — Seq and counting: atomic append-time assignment, sidecar counters, no reservation

**Decision**: `seq` is a line sequence assigned at append time from
`.bb-session/counters.json` under `fcntl.flock`; denying hooks append their own
`denied:*` lines at PreToolUse; completed calls append at PostToolUse; tripwire event
lines consume their own seq and are excluded from call counts by the `event` field.
Per-agent turn counts live in the same counters file — **the trace is never read by its
appender** (spec edge case; R8's O(1) requirement).

**Rationale**: The naive "reserve at Pre, finalize at Post" cannot be simultaneously
gap-free, completion-ordered, and reservation-crash-safe under the spec's parallel-
subagent edge case; append-time assignment gives all three by construction. A crash
between counter increment and append can skip a seq value at most — never duplicate,
never reorder (protocol doc records this bound). **Alternative rejected**: per-call
reservation with a pending-file handshake (two writes + cleanup per call, more failure
states, no property gained).

## R12 — Fingerprint normalization: the disambiguations FR-007's "exactly" leaves open

**Decision** (recorded because FR-007 requires implementing design §5.2 *exactly*, and
these three points are §5.2 ambiguities the implementation had to resolve — a later
change to any of them forces a re-fingerprint pass, so they are versioned rule decisions,
not style, per the design's Development Workflow duty):

1. **Volatile-rule application order** (§5.2 lists the substitutions but not their order):
   `uuid → iso_timestamp → ipv4 → hostname → hex_id → integer`, earlier wins. Timestamps
   MUST run before `integer`/`hex_id` or `2026-07-20` would collapse to `<n>-<n>-<n>`;
   uuid before hex_id so a full UUID is one `<id>`, not several. Order changes fingerprints.
2. **Hex rule requires ≥1 letter** (§5.2 says "hex strings ≥8 chars"): a pure-digit run is
   classified `<n>` (integer), not `<id>`, so ordinary large decimal ids (order numbers,
   epoch-ish counters) don't masquerade as hex ids. A hex token needs at least one `a–f`.
3. **Hostname requires ≥3 dotted labels** (§5.2 says "hostnames/IPs" unqualified): a bare
   2-label domain (`example.com`) stays literal — collapsing every 2-label token would
   over-normalize common words-with-dots and shrink the fingerprint's discriminating power.
   IPv4 is matched separately and always collapses.
4. **"IPs" in v1 means IPv4 only**: an IPv6 literal (colon-separated) is *not* collapsed —
   it stays literal, so a repeat alert carrying a volatile IPv6 address would not
   fingerprint identically. Recorded as a known v1 limitation rather than a silent gap;
   adding IPv6 later is fingerprint-behavioral and so forces a version bump. v1 accepts
   this because IPv6 addresses are rare in the alert-type text this normalizes.

The golden corpus (`tests/fixtures/fingerprint/golden.json`) pins each of these as an
executable rule (`bb.fp.v1`); the design §5.2 rules-home file
(`skills/session-store/references/fingerprint.md`) lands with slice 3 and will cite this
entry. **Alternative rejected**: implementing §5.2 literally without pinning order/edges —
leaves the fingerprint under-specified exactly where silent drift breaks recall.
