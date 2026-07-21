# Data Model: Session-Store Conventions

The canonical shapes this slice documents and tests. The shipped normative text lives in
`skills/session-store/references/` (plan: Project Structure); this file is the design
summary the tasks build from.

## Session row (design §5.1; FR-001/FR-002)

Row key: `session_id` = `{type}-{source-id}-{ISO date}` (D-8). Schema version
`bb.schema.v1` (research R2/R8). One row per session.

Mutation classes (FR-002): **A** = write-once at append (immutable after; the close-time
update re-asserts open-time values, never recomputes), **M** = enumerated mid-session
mutable, **C** = close-time field group.

| Column | Type | Class | Notes |
|---|---|---|---|
| `session_id` | string | A | row key; embeds open date — never recomputed for matching (D-8) |
| `session_type` | enum `incident\|page\|test` | M | promotion re-tag (§3.2); `test` excluded from retrieval |
| `status` | enum `open\|closed\|handoff\|superseded` | M | non-terminal = `open\|handoff` (join/rehydrate set); `superseded` excluded from retrieval |
| `fingerprint` | string (16 hex) | A | §5.2 / `bb.fp.v1`; re-asserted at close at its open-time value |
| `catalog_resolved` | bool | A | ladder rung 1 vs 2–4; downgrades stage-1 matches when false on either row |
| `alert_signature` | string | A | raw alert identity |
| `services` | string list | A | catalog `metadata.name` values |
| `severity` | string | M | triage-assessed, responder-correctable |
| `responder` | string | M | ownership token: `<responder> @ <ISO timestamp>` (D-18) |
| `started_at` | ISO 8601 | A | |
| `closed_at` | ISO 8601 | C | |
| `triage_verdict` | JSON (`bb.verdict.v1`) | M | checkpoint zero; refreshed on triage re-invocation (FR-5a) |
| `latest_checkpoint` | JSON (`bb.ledger.v1` or overflow pointer) | M | cell-guarded (below) |
| `timeline` | JSON | C | derived from tool trace + checkpoint history, never prose recall (D-5) |
| `root_cause` | string | C | **human-curated** (Constitution V) |
| `resolution` | string | C | human-approved |
| `links` | JSON | C | `{url, excerpt}` list (Constitution IV) |
| `runbook_refs` | JSON | C | URL + commit SHA where git-hosted |
| `diary_url` | URL | C | dual-write link |
| `diary_pending` | bool | C | diary-failure flag; `true` is the retry queue (research R10) |
| `report_url` | URL | C | FR-4d report |
| `artifacts_folder_url` | URL | C | per-session folder (§5.3) |

The SC-006 test parses exactly this table's shipped copy in `references/schema.md` and
compares names, order, and mutation class against the test-side constants
(research R5).

## Checkpoint cell shapes (design §5.4, D-3; FR-005)

- **In-cell**: serialized checkpoint ≤ 45,000 chars — stored whole in
  `triage_verdict` (seq 0) or `latest_checkpoint` (seq ≥ 1). At exactly 45,000 the cell
  holds it (store rejects only strictly-above; spec edge case).
- **Overflow**: serialized length > 45,000 — full document to artifacts
  (`put_file`) at write time; cell holds `{"overflow": "<link>", "seq": n}`. Readers
  MUST follow the link.
- **Validation gate** (FR-006): `bb-validate` before every write; fail → one re-prompt
  with the error list; second fail → persist flagged `"schema_valid": false`, surfaced.
- **History**: every checkpoint appends one line to
  `.bb-session/staging/checkpoints.jsonl` (research R1); uploaded at close as
  `checkpoints.jsonl`. Overflowed checkpoints append their full document line locally
  too — the history file is the complete record.

## Artifact folder (design §5.3; FR-004)

`battle-buddy/<session_id>/` containing exactly:
`transcript.md`, `tool-trace.jsonl`, `checkpoints.jsonl`, `report.md`.
Name mapping owned by local-state protocol v1: local `trace.jsonl` → uploaded
`tool-trace.jsonl`; local `staging/transcript.md` → `transcript.md`;
local `staging/checkpoints.jsonl` → `checkpoints.jsonl` (R1 addition).
Discoverable from the row via `artifacts_folder_url` + per-artifact links in `links`.
Contract note: `put_file` takes a `name` — the conventions pin the name as the full
folder-qualified path `battle-buddy/<session_id>/<artifact>`, which is what the mock
stores and returns a link for.

## Close flow (design §4; FR-008) — ordering claim scope: close-flow writes only

1. Diary `append_entry` (capture link). On failure: continue; row gets
   `diary_pending: true`.
2. Artifact `put_file` × staged files. On failure per file: continue; omit that link;
   surface gap for retry (spec edge case).
3. Storage `update_record`: close-time field group + re-asserted write-once values.
4. Read-back (`read_records` filtered on `session_id`), confirm `session_id` matches →
   only then delete `.bb-session/marker.json` (deletion-is-cleared, protocol v1).
   Read-back fails/mismatch → marker stays; slice-2 session guard warns at SessionEnd.

Open-time twin (FR-008): row `append_record` at open is read back before the marker
records `open_write_confirmed: true`.

## Retrieval (design §5.5; FR-007)

Stage 0 exclusion filter everywhere: drop `session_type: test` and
`status: superseded`. Stage 1 fingerprint exact match — hit = near-certain known issue,
downgraded to "candidate" if either row has `catalog_resolved: false`. Stage 2 (no
stage-1 hit): keyword overlap on `services` / `alert_signature` / `severity`. Stage 3:
hand ≤ 20 candidates to triage; if more matched, state the truncation — never silent.
Empty result at every stage = normal fresh-investigation outcome, not an error.

## Ownership (design §4, D-18; FR-009)

- Token: `responder` field, `<me> @ <timestamp>`; take-over is a single
  `update_record` write.
- Pre-write re-read: every checkpoint write reads the row's `responder` first; mismatch →
  no write, session informed + read-only.
- Join-at-open: match on `source_id` embedded in the alert + `status ∈ {open, handoff}`,
  never a recomputed `session_id`.
- Merge-at-close: earliest `started_at` is canonical; fold duplicate's artifact links
  into canonical `links`; duplicate → `status: superseded`.

## Local state touched (protocol v1 + R1 addition)

| File | This slice's use |
|---|---|
| `marker.json` | read-back confirmation points: `open_write_confirmed` at open; file deletion at confirmed close |
| `staging/checkpoints.jsonl` | NEW (additive, R1): per-checkpoint history accumulation |
| `staging/transcript.md`, `trace.jsonl` | upload sources at close (name mapping above) |

## Test fixtures (shape summary)

- `seed-retrieval.json` (mock `load_seed`): rows covering exact-match,
  keyword-overlap-only, `test`, `superseded`, `catalog_resolved: false`, and >20
  keyword matches for the cap case.
- `seed-ownership.json`: same-source-ID `open`/`handoff` rows (yesterday's date in
  `session_id`), duplicate-open pair for merge.
- `checkpoints/*.json`: valid ledger; invalid + fixed pair; invalid + still-invalid
  pair; at-guard (serialized exactly 45,000 chars — built programmatically in the test,
  fixture holds the template); over-guard template.
