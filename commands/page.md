---
description: One command from alert to briefing — preflights cheaply, opens the session, fetches alert and catalog context, retrieves prior history, spawns triage, and presents a deep-linked briefing.
---

# /page

`/page <alert-id>` is the product's front door: one command carries a responder
from an alert to a deep-linked briefing, in the documented order below, every
step degrading gracefully rather than blocking a live page.

## When to run

- **At the alert.** `/page <alert-id>` opens a `session_type: page` session for
  that alert and briefs the responder immediately.
- **Never twice in the same workspace.** The local session state pins one open
  session at a time per workspace directory — a second `/page` while one is
  already open surfaces it and offers `/close` first, rather than opening a
  second session.

## Preflight

Evaluated in this exact order, before any store read or probe of any kind:

| # | Observed state | Action |
|---|---|---|
| 1 | No `battleBuddy` config block | Stop: "run /setup". No session artifacts are created — never half-open |
| 2 | Config block malformed | Stop: repair case, surfaced explicitly — never treated as absent |
| 3 | Local session marker present, its open write confirmed | Stop: a session is already open — surface it, offer `/close` first |
| 4 | Local session marker present, its open write unconfirmed | Crash residue: surface it; proceed only on explicit responder confirmation, which **rewrites** the marker as part of the new open below — never a standalone delete |
| 5 | Local green stamp missing or stale | Auto-run responder-mode setup; on green, continue at row 6 |
| 6 | Config valid, stamp fresh | Proceed to the open flow below with **zero probe calls** |

**Ordering note.** Rows 3-4 (the marker) are checked *before* row 5 (the
stamp), even though the stamp is logically part of the same preflight bundle:
the stale-stamp branch's auto-run performs store reads, and a crashed-open
marker must be detected before any store read at all. Marker-first is the
only order that satisfies both requirements at once.

Row 5's auto-run is exactly `/setup`'s responder mode (see that command) —
seconds of work, and only ever the first page from a new machine. A
responder-mode run that doesn't come back green stops here too, naming
whatever gap responder-mode itself reported; nothing beyond it runs.

## Open flow

Compute `session_id` = `{type}-{source-id}-{ISO date}`
(`page-<alert-id>-<date>`), the date being the open-time date in **UTC**.
Cross-day handoff never recomputes this ID once a session exists, so the
timezone choice affects only the ID's cosmetic readability, never
correctness.

1. **Write the local session marker** — protocol shape, open write
   unconfirmed. Written early, before any store activity of any kind, so a
   crash between here and the row landing (below) is exactly what preflight
   row 4 detects on the next run.
2. **Open the session-named shell workspace** (`open_pane`). Degraded mode
   (no shell adapter configured, or the adapter's call fails) prints a message
   instead — this step never blocks the rest of the open.
3. **Fetch alert context and flap history** (`alerting.get_alert`,
   `alerting.list_alert_history`). A failed fetch is fail-soft: the session
   still opens, the row's alert signature degrades to the alert ID alone, and
   the briefing notes that alert context is unavailable — a broken alerting
   tool must never block a session capture. Required-capability *absence*,
   unlike a transient call failure, still fails loudly at session start.
4. **Resolve the catalog and fetch fresh runbooks and dashboards.** Catalog
   resolution walks the fingerprint service-resolution ladder: a direct
   catalog match resolves the service; a miss falls to a responder-provided
   name, then the alert's own service/team tag, then a fingerprint over the
   alert source and rule name alone when nothing else names a service. Every
   rung below the first sets `catalog_resolved: false` on the row, and the
   briefing notes the downgrade. The fingerprint itself is always computed
   through the shipped fingerprint helper, never re-derived by hand.
5. **Retrieve prior history** (tier-0 retrieval, per the session-store
   skill's retrieval reference). The same read this step performs also
   detects whether a non-terminal (open or handoff) row already exists for
   this source ID — see "Join or open separately" below. When one does, this
   command stops here, before any store write of any kind, and surfaces the
   choice.
6. **Spawn triage** — budgeted, read-only against the store — to produce a
   verdict.
7. **Validate the verdict** against its schema. One re-prompt on failure; a
   second failure persists the verdict flagged `schema_valid: false` rather
   than dropping it — a schema fight must never block a 3am briefing, and the
   responder is told plainly.
8. **Append the session row** (`storage.append_record`), `status: open`,
   carrying the validated verdict as the row's own field — checkpoint zero
   rides this append; it is never a separate write. A verdict too large for
   its cell is written to an artifact first (`artifacts.put_file`, under
   `battle-buddy/<session_id>/checkpoint-0.json`), and the row's field then
   holds an overflow pointer to it instead of the document itself. The
   checkpoint history line for this checkpoint is appended locally alongside
   the row write.
9. **Read the row back** (`storage.read_records`). Only a confirmed
   single-row match flips the local marker's open-write flag to confirmed —
   this is the one and only place that flag ever becomes true on the open
   path.
10. **Present the briefing** — see below.

## Join or open separately

The retrieval read in step 5 doubles as duplicate detection: an existing row
for this source ID with a non-terminal status means someone already opened a
session for it. When that happens, the choice is explicit and **nothing is
written before it is made**:

- **Join** rehydrates from that session's latest checkpoint (following an
  overflow link when present) and takes over ownership — no new row, no new
  session ID; the local marker is rewritten to the joined session's identity.
- **Open separately** proceeds with the normal open flow above, appending a
  distinct row; the local marker tracks only the new session.

## Briefing

Assembled from the validated verdict: every cited claim carries at least one
deep-linked `{url, excerpt}` piece of evidence — never prose alone. Across
every claim's evidence, the most-cited link is the top-cited dashboard (ties
broken by whichever was cited first); with a shell adapter configured, that
dashboard is brought into view automatically (`navigate_pane`). In degraded
mode — no adapter configured, or its call fails — that same link is printed
instead: the briefing is complete either way, only the delivery differs.

## Fail-soft postures

Every step above that touches something outside this command's own session
row is fail-soft: a failed alert fetch degrades the row and the briefing,
never the open itself; a missing or failing shell adapter degrades every
shell step to a printed message or link; a catalog miss walks the resolution
ladder and downgrades `catalog_resolved` rather than failing the page
outright. The one write this command never skips, and never retries away
from, is the session row itself.

## Session state

One open session at a time per workspace. A confirmed local marker means
`/page` stops and offers `/close` first; an unconfirmed marker is crash
residue from a session that never finished opening — it is surfaced, and only
responder confirmation lets a new open proceed, which rewrites the marker as
part of that new open. Deletion of the local session state belongs to a
confirmed `/close` alone; `/page` never deletes it.
