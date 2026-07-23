# Local-State Protocol v1 (the FR-013 artifact)

Versioned contract for session-local files. Slices 3 (session-store skill) and 5
(lifecycle commands) build on this document, never on the hook source. Every assertion
here is exercised by at least one unit test (FR-013 acceptance). Changes require a
version bump and a same-change update of every consumer — never silent.

**Location**: `.bb-session/` at the workspace root (gitignored). Created lazily by the
first writer. One session at a time per workspace directory (the design's session model);
the directory is removed by a confirmed close (slice 5) after artifact upload.

## marker.json

```json
{
  "protocol": "bb.local.v1",
  "session_id": "page-ALERT-123-2026-07-20",
  "source_id": "ALERT-123",
  "opened_at": "<iso8601>",
  "open_write_confirmed": false
}
```

Lifecycle: created at session open (slice 5 writes it; this slice reads it) →
`open_write_confirmed: true` after the open-time row append read-back → the whole file is
**deleted** on confirmed close (deletion *is* the cleared state — no resting "closed"
state exists on disk). Session-guard trigger (spec FR-011): **file present at SessionEnd
⇒ warn loudly**, regardless of `open_write_confirmed`.

## trace.jsonl

Append-only; never rewritten; **the appender never reads it on the normal path** (spec
edge case — counts and seq come from `counters.json`, below). *One exception:* the cold
`counters.json`-corruption recovery path (see counters.json) does a single bounded tail
read to re-seed `seq`; this preserves the never-duplicate invariant and keeps the O(1)
append property on the normal path. Three line types share one monotonic `seq`:

```json
{"protocol":"bb.local.v1","seq":12,"agent":"agent-3f2a","tool":"mcp__sheets__append_row",
 "capability":"storage","at":"<iso8601>","summary":"append_record session_id=…","outcome":"ok"}
{"protocol":"bb.local.v1","seq":13,"agent":"agent-3f2a","tool":"Bash","at":"<iso8601>",
 "summary":"kubectl delete deploy …","outcome":"denied:guardrail:destructive_infra"}
{"protocol":"bb.local.v1","seq":14,"event":"tripwire","agent":"agent-3f2a",
 "tool":"mcp__opsgenie__get_alert","at":"<iso8601>","matched":"instruction_override"}
```

- **seq is a line sequence**, not a call count: assigned atomically at append time from
  `counters.json` under an OS file lock; file order = seq order, gap-free **absent a
  process crash between counter-increment and append** (a crash can skip one value —
  never duplicate, never reorder; see counters.json). There is **no reservation step** — a call denied at PreToolUse gets its
  line appended *by the denying hook* at denial time (`outcome: denied:guardrail:<class>`
  or `denied:turn_cap`); a completed call gets its line at PostToolUse with its outcome.
  One line per tool call in the normal case (spec FR-008); under parallel subagents,
  per-line atomicity and uniqueness hold, and ordering is by append (completion/denial)
  time. **Double-deny bound**: Claude Code runs matching PreToolUse hooks concurrently
  with no cross-visibility, so a call that is *both* guardrail-dangerous *and* past-cap
  can produce two `denied:*` lines (one per denying hook) — an accepted, bounded case;
  call-counting deduplicates denied lines sharing the same tool-call identity within one
  PreToolUse batch. **Tool-call identity** (pinned by this slice's implementation;
  `call_id` is an additive optional field on denied lines only — no version bump, no
  consumer-parse change, same precedent as corruption recovery below): denied lines
  carry the runtime's tool-call id as an optional `call_id` field whenever
  the hook payload provides one (`tool_use_id`); two `denied:*` lines with the same
  `call_id` are one call — exact, order-independent. When `call_id` is unavailable the
  fallback is identical `agent` + `tool` + `summary` on **adjacent** denied *call* lines
  (event lines between them do not break adjacency; both denying hooks derive `summary`
  through the same shared helper, so the identity is well-defined). The fallback is
  best-effort, not exact: a parallel subagent's append can land between the two denied
  appends (double-count) and an identical immediately-retried denied call merges
  (under-count) — bounded miscounts, accepted only for `call_id`-less runtimes.
- **Call lines** have no `event` field; **tripwire event lines** carry
  `event: "tripwire"` and consume their own seq. Consumers counting *calls* filter on
  the absence of `event` (SC-005's 100 calls ⇒ exactly 100 call lines).
- `agent`: the actor key (see agents.json). `capability`: from the binding map when
  present, else omitted. A tool serving ops of **several** capabilities serializes as a
  **sorted, comma-joined** string (e.g. `"alerting,observability"`); consumers split on
  `,` to recover the set. (The guardrail deny hook already emits this on `denied:*` lines
  when a binding map is configured.)
- `outcome` ∈ `ok | error:auth | error:timeout | error:other | denied:guardrail:<class> |
  denied:turn_cap`. Mapping to spec FR-008 vocabulary: spec "success" ≡ `ok`, spec
  "auth_error" ≡ `error:auth`; the `denied:*` values extend the spec's enumeration via
  this protocol (recorded here per the protocol's versioning duty).
- **Auth-context window**: consumers reading "recent" context (deny hook's
  credential-scanning class) read the **last 10 lines**; the window is part of this
  protocol. (The deny hook is a reader, not the appender of completed-call lines, so the
  appender-never-reads rule is untouched.)

## counters.json

Sidecar for everything that must not require scanning the trace:

```json
{"protocol":"bb.local.v1","seq":14,"turns":{"agent-3f2a":9,"agent-77c1":41}}
```

Read-increment-write under `fcntl.flock` (POSIX — macOS/Linux, the supported runtime
platforms); crash between increment and trace append can skip a seq value at most (never
duplicate). **Turn accounting**: the cap is *checked* at PreToolUse (read `turns[actor]`
vs config) but *incremented* at PostToolUse — so only calls that actually executed
consume a turn, and a guardrail-blocked or cap-denied call (never reaching PostToolUse)
consumes none. This makes turn-consumption independent of the concurrent guardrail hook
(finding A): no coordination between the two PreToolUse hooks is required.

**Corruption recovery** (this slice's implementation; no version bump — no format or
consumer-parse change, only a hardening of the never-duplicate guarantee): a
`counters.json` that is unparseable, a non-object, a non-empty object lacking `seq`, or an
object whose `seq`/`turns` is the wrong type is treated as corrupt. The next writer re-seeds `seq` from the **maximum valid seq in the
bounded trace tail** (the one sanctioned appender read — see trace.jsonl) rather than
resetting to 0, so a corrupt counter can never cause a duplicate seq. Per-actor `turns`
that survive in the file are preserved; turns lost to corruption reset to 0 — meaning a
corrupt counter grants the triage actor a fresh turn window, an accepted degradation
(the cap is a budget bound, not a security layer). Every corruption recovery, and any
`fsync` failure that could later manifest as a duplicate, is written to hook `stderr`
(FR-004 visibility), never silent. The counter write is write-then-truncate,
partial-write-safe, and `fsync`-ed so the increment is durable before the dependent trace
append.

**Once-only notices** (additive field, this slice; no version bump — no consumer-parse
change, same precedent as corruption recovery above): the sidecar may carry a `notices`
object of `{key: true}` entries recording session-scoped diagnostics already emitted
once — e.g. `tripwire_disabled:<session id>`, backing the tripwire's
one-disabled-notice-per-session rule (the key embeds the runtime session id so a
`.bb-session/` surviving a skipped close still yields one notice in each later
session). Consumers never parse it; a wrong-typed `notices` resets to `{}` and is
**not** treated as corruption (it feeds no seq/turn guarantee).

## agents.json — actor identity and roles

Hook payloads carry no agent name; identity is **derived**: the actor key is a stable
hash-suffix of the hook payload's `transcript_path` (distinct per agent instance,
including the main session). Role mapping is **registered by convention**: the
investigation skill's spawn flow (slice 6) writes `{actor_key: "triage" | "deep" |
"specialist:<name>"}` entries at spawn time. The mechanism/policy split is deliberate:
this layer provides deterministic identity + enforcement; the skill provides role
registration. **Fallback when an actor is unregistered: no turn cap applies (fail open)**
— enforcement without identity would cap the wrong agents.

```json
{"protocol":"bb.local.v1","roles":{"agent-3f2a":"triage"}}
```

## staging/

`staging/transcript.md` — copied by `session_guard.py` from the runtime's
`transcript_path` at SessionEnd; slice 5's close flow uploads it, and uploads
`trace.jsonl` under the design's artifact name **`tool-trace.jsonl`** (design §5.3 — the
local and uploaded names differ; this mapping is part of the protocol). Missing
transcript ⇒ logged notice, no failure. **Known v1 limitation** (recorded, not silent):
staging is unconditional at every SessionEnd and the staged name is single, so the copy
reflects the *most recent* session to end in the workspace — under the design's
one-session-per-workspace model that is the incident session, but an unrelated session
ending in the same directory while a marker is open will overwrite the staged copy. The
runtime's own transcript at `transcript_path` remains the authoritative source; slice
5's close flow should treat the staged copy as a convenience snapshot, not the only
copy.

`staging/checkpoints.jsonl` — one JSON line appended per checkpoint at
checkpoint-write time by the session-store skill's checkpoint conventions (slice 3);
uploaded at close under the artifact name `checkpoints.jsonl` (design §5.3/§5.4).
Recorded here as an **additive** `staging/` entry per this protocol's versioning duty —
**no version bump**, the same standard already applied to the `denied:*` outcome
extension above: the addition changes no existing file's format and no existing
consumer's parse. The accumulation is forced local-first because the artifact contract
has no append operation; `staging/` is already this protocol's "files awaiting
close-time upload" area, so the checkpoint history belongs here rather than inventing a
second local-state root.

## Hook event bindings (which component touches what, when)

| Event | guardrail_deny.py | tool_trace.py | session_guard.py |
|---|---|---|---|
| PreToolUse | evaluate deny classes; on block: append `denied:guardrail:*` line | turn-cap check via counters; on deny: append `denied:turn_cap` line | — |
| PostToolUse | — | append call line (outcome classified); tripwire evaluation | — |
| SessionStart | — | — | config-presence warning (FR-015; a settings file that exists but cannot be parsed gets a fix-the-file variant instead of the run-from-workspace-repo remedy); stale-marker warning on a **fresh `startup` only** — `resume`, `clear`, `compact`, and unknown sources are exempt (all fire mid-session with the marker legitimately open; compaction has no preceding SessionEnd) |
| SessionEnd | — | — | marker check (warn if present); transcript staging |

Session-guard note: v1 registers the marker check on **SessionEnd only** — it fires once
at session termination and cannot block, satisfying FR-011 as a loud warning; a Stop-hook
registration would re-fire after every conversational turn of a live session (constant
false nags for a legitimately-open marker). A blocking variant is deferred until the
runtime offers a clean end-of-session blocking point (recorded as a research decision).
"Loud" is delivered on the runtime's user-visible channel: the FR-011 and FR-015
warnings are emitted as a `systemMessage` JSON object on stdout (exit 0) *in addition
to* stderr — an exit-0 hook's stderr alone is debug-log-only and would reach nobody.
Fail-open/degraded diagnostics remain stderr-only (R13); only the spec-required
warnings use the user-visible surface. Because `systemMessage` rendering *during
session teardown* (SessionEnd) is not explicitly documented by the runtime, the marker
check is mirrored at **SessionStart** on a fresh `startup` only (see the event table:
`resume`/`clear`/`compact` and unknown sources fire mid-session over a legitimately
open marker — warning there would be the same false-nag failure that keeps this check
off the Stop event): a marker already present at a fresh startup is the same
skipped-`/close` state, warned at a point where rendering is unambiguous. The two
checks together make D-11's detection robust to either surface failing.

## Config keys read by this layer (workspace `.claude/settings.json` → `battleBuddy`)

| Key | Type | Default when absent |
|---|---|---|
| `budgets.triageTurnCap` | int | 15 |
| `bindings` | map **`capability.operation` → tool name** (design §7.2, D-13 — e.g. `"storage.append_record": "mcp__sheets__append_row"`) | tripwire disabled (one notice/session); `capability` omitted from trace lines |
| *(key presence)* | — | absence of the whole `battleBuddy` block ⇒ FR-015 warning at SessionStart |

Tool→capability classification (tripwire, trace lines) is the **reverse lookup**: find
binding entries whose value equals the tool name; the capability is the key's prefix
before the first `.`. One tool serving ops of several capabilities classifies as the set
of matching capabilities (tripwire fires if any is untrusted). Malformed config JSON is
treated as absent (fail open) with a diagnostic notice.
