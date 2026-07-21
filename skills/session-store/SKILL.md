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

_Stub — filled by T014 (US3): `triage_verdict` vs `latest_checkpoint`, the 45,000-char
cell guard and overflow-pointer representation, checkpoint-history accumulation, and
the `bb-validate` re-prompt-then-flag gate._

## Session ownership

_Stub — filled by T019 (US4): the `responder` ownership token, take-over as a single
write, the mandatory pre-write ownership re-read, join-at-open detection, and
merge-at-close for duplicates._

## Artifact layout

_Stub — filled by T023 (US5): the per-session folder path, the four canonical artifact
names, the local-name-to-uploaded-name mapping, and row-discoverability of artifacts._
