---
name: session-store
description: Use when reading or writing any part of the team's tier-0 session store — session rows, artifacts, retrieval, checkpoints, or the close flow. Documents the storage conventions (schema, fingerprint, retrieval, checkpoint, ownership, artifact layout) that stand in for shipped storage code.
---

# Session Store

## Overview

The team's session store is **tier-0**: no bespoke storage code ships (Constitution I,
FR-012). Instead, this skill documents the conventions — column set, mutation policy,
fingerprint construction, retrieval flow, checkpoint representation, ownership model,
artifact layout — as *documentation that behaves like a schema*. Every session-store
read or write an agent performs goes through the team's own storage via **operation
contract v1** (`append_record`/`read_records`/`update_record` for rows,
`put_file`/`get_file` for artifacts, `append_entry` for the diary) — never a
hardcoded server or tool name (Constitution VII, FR-010). Store-medium nouns (Sheet,
Drive, cell) describe the tier-0 medium and remain permitted.

These conventions are written to survive tier-1 migration unchanged — field names,
fingerprint construction, and checkpoint formats are declared migration-stable
(FR-013; see `references/schema.md`).

## References

| Reference | Covers |
|---|---|
| `references/schema.md` | The full column table, mutation classes, `session_id` format + source-ID parse rule, schema version (`bb.schema.v1`), the FR-013 stability commitment |
| `references/fingerprint.md` | The normative `bb.fp.v1` construction rules, normalization, the four-rung service-resolution ladder, `catalog_resolved` semantics |
| `references/retrieval.md` | The three-stage retrieval flow (fingerprint exact-match → keyword overlap → capped agent-ranked candidates), exclusions, downgrade rule |

## Open and close flow

### Open — append, then read back (the FR-008 twin)

1. Compute `session_id` as `{type}-{source-id}-{ISO date}` (`references/schema.md`'s
   row-key format) and `append_record` the row: `status: open` plus every write-once
   field this session already knows (`fingerprint`, `catalog_resolved`,
   `alert_signature`, `services`, `started_at`, …).
2. Read the row back — `read_records` filtered on `session_id`. Only a **confirmed
   match** (exactly one returned row whose `session_id` equals the one just appended)
   sets the local session marker's `open_write_confirmed: true` (local-state protocol
   v1's `marker.json`). A failed append, or a read-back that comes back empty or
   mismatched, leaves `open_write_confirmed: false` — the slice-2 session guard is the
   deterministic backstop that warns loudly if a marker is ever left in that state at
   session end.

The close flow below repeats this same append-then-confirm-by-read-back shape at its
own last step; the two together are the "dual-write, ordered" discipline FR-008 pins
end to end.

### Close — pinned write order (close-flow writes only)

**Scope of the ordering claim**: the four steps below are pinned in order for the
**close flow's own writes**. Mid-session writes — a checkpoint's `update_record` onto
`latest_checkpoint`/`triage_verdict`, or a checkpoint-overflow `put_file` under
`checkpoint-<seq>.json` (see this skill's checkpoints section) — happen throughout the
session, before `/close` ever runs, and are **not** part of this ordering claim;
nothing about their relative order is pinned here.

1. **Diary** — `append_entry` the diary entry and capture its returned link. On
   failure, do not block or reorder the remaining steps around it — continue straight
   to step 2; see "Diary failure" below for what the row carries instead.
2. **Artifacts** — upload every staged file with one `put_file` call each, under the
   folder-qualified name `battle-buddy/<session_id>/<artifact-name>`
   (`artifacts_folder_url` records this folder on the row). The local-name →
   uploaded-name mapping is owned by the slice-2 local-state protocol (`bb.local.v1`)
   and restated here:
   - `staging/transcript.md` → `transcript.md`
   - `trace.jsonl` → `tool-trace.jsonl`
   - `staging/checkpoints.jsonl` → `checkpoints.jsonl`
   - the generated investigation report → `report.md` (no local-staged counterpart —
     generated fresh at close)
   On a per-file failure, continue with the remaining files; see "Artifact failure"
   below.
3. **Row update** — `update_record` carrying the close-time field group (`closed_at`,
   `timeline`, `root_cause`, `resolution`, `links`, `runbook_refs`, `diary_url`,
   `diary_pending`, `report_url`, `artifacts_folder_url`) **plus every write-once field
   re-asserted at its open-time value** (`references/schema.md`'s mutation policy) —
   most importantly `fingerprint`, which this step never recomputes even if catalog
   resolution improved mid-session; that benefits future sessions' fingerprints, not
   this row's. `timeline` is always derived from the tool trace plus checkpoint
   history, never assembled from prose recall of the transcript — this slice documents
   that rule; the derivation itself executes in slice 5.
4. **Read-back** — `read_records` filtered on `session_id`, confirming the returned
   row's `session_id` matches. **Only** a confirmed match deletes the local session
   marker (`marker.json`) — deletion of that file *is* the cleared state (local-state
   protocol v1; there is no separate "closed" marker state on disk). A failed or
   mismatched read-back leaves the marker in place; the slice-2 session guard warns
   loudly at session end, same as a marker stuck at `open_write_confirmed: false`.

### Diary failure

The diary write may fail without stopping the close flow. On failure, steps 2–4 run
unchanged and the row lands with `diary_pending: true` instead of a `diary_url`.
`diary_pending: true` on the row **is** the retry queue (research R10) — there is no
separate local queue file, and none is needed: a later pass finds every session still
owing a diary entry with `read_records` filter `{diary_pending: true}`, writes the
diary entry, then `update_record`s the row (`diary_url` set, `diary_pending: false`).
The row write — the write that must not be lost — is never skipped or delayed to
compensate for a diary failure.

### Artifact failure (per file)

Each staged file's `put_file` call is independent of the others and of the row write.
A failure on one file does not stop the remaining uploads, and never blocks step 3: the
failed file's link is simply omitted from `links` (or whichever field would have
carried it), and the gap is surfaced so a later pass can retry that one upload. The row
write proceeds with whatever links did land.

### `update_record` returns `not_found`

A `not_found` error on `update_record` — at close, or at any other write — means the
target `session_id` is stale, mistyped, or the store was swapped out from under the
session; it is never a signal to retry the identical call. Re-locate the session
instead: parse the source ID out of the attempted `session_id`
(`references/schema.md`'s parse rule), read rows with non-terminal `status` (`open` or
`handoff`), match by that parsed source ID, and reconcile against whatever is found
there.

### Timeline derivation

The close-time `timeline` field is always produced mechanically from the tool trace and
the checkpoint history — never from prose recall of the transcript. This is a normative
rule of the close flow; the derivation logic itself is out of this slice's scope and
executes in slice 5.

## Checkpoints

### Representation — `triage_verdict` vs `latest_checkpoint`

Checkpoint zero — the triage verdict — lives in the row's `triage_verdict` cell. Every
later checkpoint (the deep investigator's ledger, checkpointed on every update) lives in
`latest_checkpoint`, overwriting the previous value on each write — the row only ever
holds the *latest* state, never a running history (`references/schema.md`'s column
table).

**One-row-read resume rule**: the latest state is always recoverable from
`latest_checkpoint` — or `triage_verdict` if no `latest_checkpoint` has landed yet —
alone, following its overflow link (below) when present. That is one `read_records`
call and at most one artifact `get_file` call; resuming an investigation never scans
the checkpoint history.

### Cell guard — the 45,000-character boundary

Every checkpoint write serializes the winning document with `json.dumps`, sorted keys,
compact separators, no whitespace — the pinned serialization this guard measures *and*
the one the cell (or overflow artifact) stores, so the boundary this convention checks
and the boundary the store's field-size limit enforces can never disagree.

- **≤ 45,000 characters** (the boundary itself included — the store's field-size limit
  rejects only values strictly above it): the full serialized document goes straight
  into the cell.
- **> 45,000 characters**: the full document is written to the artifact store via
  `put_file` **at write time** — never deferred to close — under the folder-qualified
  name `battle-buddy/<session_id>/checkpoint-<seq>.json`, so its link exists
  immediately. The cell then holds an overflow pointer,
  `{"overflow": "<link>", "seq": n}` (also serialized the same way). Readers **MUST**
  follow the link — a cell holding an overflow pointer is never itself the checkpoint.

Because the guard decision is made from the exact serialized length the store would
check, a checkpoint write is never attempted that the store's field-size limit would
reject: the write either already fits the cell, or is diverted to the artifact store
first.

### History — session-local accumulation, uploaded at close

The artifact contract has no append operation, so the full checkpoint history cannot
accumulate remotely mid-session (research R1). Instead, every checkpoint write —
checkpoint zero included, and an overflowed checkpoint's *full* document included, never
just its pointer — appends one line to `.bb-session/staging/checkpoints.jsonl`. Each
line is a JSON object `{"seq": n, "document": <the full checkpoint document as
written, including the "schema_valid": false flag when the validation gate below set
one>}` — wrapped rather than merged into the document so this write's ordinal `n` never
collides with a ledger checkpoint's own internal `seq` field (its ledger-turn counter,
a different number). At close, this file uploads under the artifact name
`checkpoints.jsonl` (this skill's "Artifact layout" section). The history file is the
complete record; the row cell is only ever the latest state.

### Validation gate — `bb-validate` before every write

Before any checkpoint write lands — in the cell or via overflow — the candidate document
passes slice 2's validator (`bb-validate`). The pinned failure path (D-14, Constitution
VI):

1. Validate the producing agent's document.
2. **On failure**: re-prompt the producing agent once, handing back the validator's
   error list, and validate the re-prompted document.
3. **On a second failure**: persist the second document anyway, flagged
   `"schema_valid": false`, and surface the degradation to the responder. A checkpoint
   is never dropped over a schema fight — losing an investigation's state is worse than
   persisting an unvalidated one at 3am.

### Ownership pre-read

Every checkpoint write **re-reads the row's `responder` cell first** — before
validating or writing anything else. (This is the ownership model's rule; the full
model — the `responder` token, take-over-as-a-write, join-at-open, merge-at-close —
lives in the "Session ownership" section below.) If the cell
no longer names the writing session's responder, the session has been taken over: no
write is performed — not the validation-gated document, not the history line — the
session is told it was taken over, and it goes read-only.

## Session ownership

Optimistic ownership (D-18): no lock, lease, or reservation record exists anywhere in
the store. The whole model rests on one field and a disciplined read-before-write habit
around it.

### Ownership token — `responder`

The `responder` field (`references/schema.md`'s column table) **is** the ownership
token, in the format `<responder> @ <ISO timestamp>` — whoever's name and timestamp
currently sit in that one cell is the session's current owner. There is nothing else to
check: no separate "owner" column, no lock table, no external coordination.

### Take-over — a write, not a request

Rehydrating an open or handed-off session **is** the take-over: the rehydrating
responder issues a single `update_record` write setting `responder` to
`<themselves> @ <now>`. There is no request-then-approve exchange and no "claim"
operation to call first — whoever's write lands overwrites whoever was there, full
stop. The previous responder isn't notified synchronously; they find out the way the
next section describes.

### Pre-write ownership re-read (mandatory before every checkpoint write)

This is the rule the "Checkpoints" section's "Ownership pre-read" step performs and
forward-cites here: **every checkpoint write** — never any other kind of write; this is
the scope FR-009 pins — re-reads the row's `responder` cell **immediately before
writing**, as its very first step, before validation and before touching the local
history file. If the cell no longer names the writing session's own responder token,
the session has been displaced:

- the write is **not performed** — not the validation-gated document, not the history
  line, nothing;
- the session is told it was taken over, naming the current `responder`; and
- the session goes **read-only** — every checkpoint write it attempts afterward re-reads
  the same cell and fails the same check, since a take-over is a durable store write,
  not a flag that could clear itself.

**Race bound**: at most one stale checkpoint can land after a take-over. Whichever of
the displaced session's checkpoint writes was already past its own pre-read at the
instant the take-over's `update_record` landed completes normally (its check already
passed before the responder cell changed); every write the displaced session attempts
afterward observes the new `responder` and is denied. The store's edit history is the
audit trail for reconstructing exactly which write that was (see "Audit trail" below).

### Join-at-open — duplicate detection on the opening read

The read that opens a session already looks for a prior row (`references/retrieval.md`'s
fingerprint/keyword stages); ownership piggybacks on a read at the same point for a
second purpose: **duplicate detection**. Before appending a new row, read for an
existing row on the same source ID whose `status` is non-terminal — `open` or
`handoff` (`references/schema.md`'s join/rehydrate set). The row-side source ID comes
from **parsing** the candidate row's `session_id` per `references/schema.md`'s
source-ID parse rule (strip the leading `{type}-` and the trailing `-{YYYY-MM-DD}`) —
**never** by recomputing today's `session_id` and comparing it directly. The reason is
the cross-day case: a session opened yesterday and still open today carries yesterday's
date baked into its `session_id`, so a same-day recomputed-ID comparison would miss it
outright and a fresh row would be appended — silently forking one incident's history in
two. Matching on the parsed source ID plus non-terminal status finds the row regardless
of which day it was opened. The contract exposes only field-equality filters, so this
check is a full `read_records` read, filtered client-side — the same shape as
`references/retrieval.md`'s stage-2 client-side filtering.

When a match is found, the convention surfaces an **explicit join-or-separate choice —
never a silent duplicate**:

- **Join** (the default, and by far the common case): treat this as the same session —
  rehydrate from its latest checkpoint ("Checkpoints" -> "One-row-read resume rule") and
  take over ownership (above). No new row is appended.
- **Separate**: only when the responder deliberately determines this is genuinely a
  distinct session that happens to share a source ID (rare) — a new row is appended as
  normal. If that determination turns out to have been wrong — a true race rather than a
  deliberate separation — `/close` reconciles it below.

### Merge-at-close — true-race duplicates

Despite join-at-open, two responders can still race closely enough that both append an
open row for the same source ID before either one's read observes the other's write —
the tier-0 store has no locking to prevent it (D-18). `/close` is where this gets
resolved, for whichever of the pair closes: among the same-source-ID, non-terminal
duplicates, the row with the **earliest `started_at`** is canonical; every other row is
a duplicate to fold in and retire.

The fold-in shape is exact, and nothing else moves:

- every entry in the duplicate row's `links` is appended into the canonical row's
  `links`;
- the duplicate row's `artifacts_folder_url` — its own artifact folder, holding
  whatever it accumulated before the merge — is wrapped as one more `{url, excerpt}`
  entry (the `excerpt` naming it as the duplicate's artifacts folder) and appended into
  the canonical row's `links` alongside them.

Nothing else moves in either direction: the canonical row's own `root_cause`,
`resolution`, `timeline`, and every other field stay exactly as the canonical session
produced them — the duplicate is a fork whose evidence is preserved, not a second
source of truth to reconcile field-by-field.

The duplicate row is then `update_record`d to `status: superseded` — **never deleted**
(the contract has no delete operation; nothing in this store is ever deleted).
`status: superseded` is exactly the value `references/retrieval.md`'s stage-0
exclusions drop at every stage, so the superseded row stops surfacing as a retrieval
candidate immediately, while remaining in the store — and in the store's edit history —
as the complete record of how the race happened.

### Audit trail

Every ownership write — every take-over, and every merge's `status: superseded` — is an
`update_record` call, and every mutating call is durably recorded in the store's own
edit history. Optimistic ownership carries no separate audit log because it doesn't
need one: the store's history already is that record. Tier 1's server replaces all of
this with real transactions.

## Artifact layout

_Stub — filled by T023 (US5): the per-session folder path, the four canonical artifact
names, the local-name-to-uploaded-name mapping, and row-discoverability of artifacts._
