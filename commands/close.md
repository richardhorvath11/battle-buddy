---
description: Closes the open session — drafts the diary entry with causal fields labeled as proposals for your approval, then writes diary, artifacts, and the row down in order, deletes local state only once the row read-back confirms, and closes the shell workspace.
---

# /close

`/close` is the must-not-lose write: it turns an open session into a durable record —
diary entry, uploaded transcript/trace/checkpoint history/report, and a closed session
row — in a pinned order, and never deletes anything local until the store confirms the
row landed.

## When to run

- **At the end of a session** — the incident is resolved, or the responder is done with
  this page for now. `/close` is the only thing that clears the local session marker.
- **Never blind.** The draft below is always presented for approval before a single
  write happens; approving it is part of running `/close`, not a separate step.

## No open session

If the local session marker is absent, `/close` reports "no open session" and performs
no writes of any kind — there is no resting closed state to act on, so there is nothing
to reconcile.

## Duplicate detection, first — read-only

Before anything else — and before the draft below — check for duplicate open rows
sharing this session's source ID (the same check the open flow's retrieval step runs
for join detection). This is a **read**, never a write: two responders can race closely
enough that both open a session for the same source ID before either one's read
observes the other's write, and whichever of them closes first is the one that resolves
it — but nothing about *detecting* that is a write in itself.

- The row with the **earliest** `started_at` is the **prospective canonical row** — the
  same one the merge writes below will pick, if this close goes on to perform them.
- The draft (below) is assembled against this prospective canonical row: its factual
  fields describe what canonical will look like, not necessarily the row this
  particular session opened.
- Fewer than two duplicate rows: there is nothing to merge, and canonical is simply this
  session's own row.

Nothing is written yet. Whether any merge write actually happens depends on the draft
being approved first.

## Draft the diary entry

Before any write — merge included — assemble the structured draft, against the
prospective canonical row above:

- **Factual fields** are auto-filled from that row and the derived timeline: services,
  severity, responder, `started_at`, `closed_at`, links.
- **Causal fields** — root cause, contributing factors, action items — are never
  auto-filled as fact. Each is an explicitly labeled **proposal**, carried in its own
  section of the draft, never mixed into the factual fields. No causal proposal is ever
  promoted to the row without the responder's own decision to approve it.
- **Rendering** uses the configured diary template
  (`battleBuddy.diary.template`, an additive workspace-config key) when one is set; when
  it isn't, the entry's format is matched against the diary's own recent entries
  (`diary.read_recent`) instead of inventing a new style. Either way, the rendered text
  carries the same explicit proposal labels on every causal section.

**No write of any kind happens before the draft is approved — not even a merge.** A
responder who reviews the draft and declines has changed nothing: no duplicate has been
superseded, no row has been touched, nothing about the session state is any different
than before the draft was looked at. Approval is the responder's decision on this exact
artifact — the causal sections as proposed, or as edited by the responder before
approving.

## Ownership, then merge writes

Immediately after approval, and before any close-flow write of any kind, this session's
own ownership of **its own row** — the one its local marker names — is re-read and
compared against this responder's own token. This is deliberately checked against this
session's *own* row, never the prospective canonical row from above: when this session
isn't itself canonical (the ordinary case a merge exists for — whichever of a
true-race pair happens to close first), the responder driving `/close` is never the
canonical row's own opener, so comparing canonical's responder against this responder's
token would be the wrong check entirely — it would deny the exact case merge-at-close
is meant to handle.

- **Mismatch**: someone else has taken this session over since it was opened. No write
  happens at all — not a merge write, not the diary, not an artifact, not the row
  update. The take-over is reported by name, and this close goes read-only.
- **Match**: only now, once approved and only once this check passes, do the merge
  writes actually run (when duplicates were found above) — earliest `started_at`
  canonical, every other row's links plus its artifacts folder (wrapped as one more
  `{url, excerpt}` link) folded into canonical's, each duplicate re-tagged
  `status: superseded` (never deleted — the store has no delete operation, and the
  superseded row remains as the record of how the race happened).

**Every step from here on targets the canonical row.** If this session's own row turns
out to be the one superseded by the merge, its local marker is still cleared, gated on
the *canonical* row's read-back at the very end: the incident's one true record is what
has to land, not necessarily the row this particular session opened.

## The dual-write, in order

The writes below run in this pinned order, on the canonical row, immediately after any
merge writes above:

1. **Diary** (`diary.append_entry`) — captures the returned link. A failure here never
   blocks or reorders anything that follows: the row still lands, `diary_pending: true`
   instead of a diary link, and that flag **is** the retry queue — a later pass finds
   every row still owing an entry and writes it then.
2. **Artifacts** (`artifacts.put_file`, one call per file) — the session transcript, the
   local trace under its documented uploaded name, the checkpoint history, and the
   generated report (see below), each uploaded under the session's own artifact folder.
   A failure on any one file omits just that file's link and continues; it never blocks
   the row write or the remaining uploads.
3. **Row update** (`storage.update_record`) — the close-time fields (`closed_at`, the
   derived timeline, the approved causal values, links, the diary/artifact fields above)
   plus every write-once field re-asserted at its open-time value. Immediately before
   this write, canonical's ownership is checked again (see "The close-time ownership
   check" below — a second, distinct check from the one above); a transient failure here
   is retried, bounded — close blocks on this write's success, it is never skipped.
4. **Row read-back** (`storage.read_records`) — only a confirmed match deletes the whole
   local session directory. A failed or mismatched read-back leaves everything in place;
   the deterministic session guard is the backstop that catches it.

## Transcript capture

The session transcript is copied from the runtime's own transcript file at the moment
`/close` runs, then uploaded through the normal mapping above. A missing or unreadable
source is a logged notice — the transcript artifact is simply omitted, and close
continues; nothing about the rest of the close is blocked by it. Because this copy
happens mid-session rather than at the runtime's own end-of-session point, turns that
happen after `/close` runs are not part of the uploaded transcript — an accepted
limitation of capturing it here rather than later.

## Timeline and the report

The row's `timeline` field is never assembled from prose recall of the transcript. It is
derived mechanically, purely from two local sources: every tool-call line in the local
trace, and every entry in the checkpoint history — each input line becomes exactly one
timestamped event, ordered by time. The generated report is, in turn, purely a rendering
of the row plus its artifacts: it introduces no fact that isn't already in one of them.

## The close-time ownership check

This is the *second* of `/close`'s two ownership checks — the same pre-write re-read the
session-store conventions require before every checkpoint write, extended to this
close-time row update. It runs immediately before the row update above, and it checks a
**different row** than "Ownership, then merge writes" did: canonical's, not necessarily
this session's own.

Its comparison point isn't this responder's own token — it's whatever canonical's
responder was already found to be during duplicate detection, at the very start. If
nothing else touched canonical's row in the time since, this check simply confirms that;
if some *other* responder took canonical over in that window (a genuine race, distinct
from the "is this still my own session" question the first checkpoint already answered),
this is what catches it:

- No row write happens — not the close-time update, not the read-back, not the
  local-directory deletion.
- Whatever diary and artifact writes already landed by that point stand — they are
  harmless, additive records; only the row-mutating write itself is gated.
- The take-over is reported by name, and this close goes read-only.

When there was nothing to merge (canonical simply *is* this session's own row), this
check and the first one are protecting the same row — this is not a second opportunity
to be denied for the same reason twice, it's the same guarantee reconfirmed immediately
before the write it actually protects.

## Shell close

Last, and only after everything above has run: close the session's shell workspace
(`close_workspace`), leaving its state restorable. In degraded mode — no shell adapter
configured, or its call fails — a message is printed instead; the close itself has
already completed by this point, so nothing about this last step can undo it.
