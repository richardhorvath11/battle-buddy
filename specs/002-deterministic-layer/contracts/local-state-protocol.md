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
  "open_write_confirmed": false,
  "closed_confirmed": false
}
```

Lifecycle: created at session open (slice 5 writes it; this slice reads it) →
`open_write_confirmed: true` after the open-time row append read-back → the whole file is
**deleted** on confirmed close (deletion *is* the cleared state — no
`closed_confirmed: true` resting state exists on disk; the field exists for in-flight
atomic rewrites only). Session-guard trigger (spec FR-011): **file present at
Stop/SessionEnd ⇒ warn/block**, regardless of `open_write_confirmed`.

## trace.jsonl

Append-only; one JSON object per line per tool call; never rewritten or read-modified by
the appender.

```json
{"protocol": "bb.local.v1", "seq": 12, "agent": "triage", "tool": "mcp__sheets__append_row",
 "capability": "storage", "at": "<iso8601>", "summary": "append_record session_id=…",
 "outcome": "ok"}
```

- `seq`: monotonic from 1 per session; PreToolUse reserves, PostToolUse writes the final
  line (a call denied at PreToolUse writes a line with `outcome: "denied:<reason-class>"`).
- `capability`: from the binding map when present, else omitted.
- `outcome` ∈ `ok | error:auth | error:timeout | error:other | denied:<class>`
  (classification per research R4).
- Auth-context window: consumers reading "recent" trace context (deny hook's
  credential-scanning class) read the **last 10 lines** — the window is part of this
  protocol.
- Tripwire events append a supplementary line: `{"protocol":"bb.local.v1","seq":n,
  "event":"tripwire","tool":…,"at":…,"matched":"<family>"}`.

## staging/

`staging/transcript.md` — copied by `session_guard.py` from the runtime's
`transcript_path` at Stop/SessionEnd; upload to Drive is slice 5's close flow. Missing
transcript ⇒ logged notice, no failure.

## Config keys read by this layer (workspace `.claude/settings.json` → `battleBuddy`)

| Key | Type | Default when absent |
|---|---|---|
| `budgets.triageTurnCap` | int | 15 |
| `bindings` | map capability→tool | tripwire disabled (one notice/session); `capability` omitted from trace lines |
| *(key presence)* | — | absence of the whole `battleBuddy` block ⇒ FR-015 warning at SessionStart |

Malformed config JSON is treated as absent (fail open) with a diagnostic notice.
