# Session-Store Schema Reference

Normative for the `session-store` skill (FR-001, FR-002, FR-013; design §5.1). One row
per session in the team's session store. This document is the SC-006 parse target — its
column table is the mechanically cross-checked source of truth for the store's shape.

## Schema version

**`bb.schema.v1`** — versioned like every other `bb.*` contract (`bb.fp.v1`,
`bb.verdict.v1`, `bb.ledger.v1`, `bb.local.v1`).

**Tier-1 stability commitment (FR-013)**: field names, fingerprint construction, and
checkpoint formats declared here are **migration-stable** — a future tier-1 ingestion is
a column mapping onto this schema, not a redesign. Any breaking change to this document
bumps the version and ships alongside a documented migration note.

**Live-Sheet representation** (research R2): in a live Sheet the version lives in a
**header-row sentinel cell** — row 1, one column to the right of the last schema column
— holding the literal version string (e.g. `bb.schema.v1`). It is **not a data column**:
no session row carries it, and the column set stays exactly the table below. `/doctor`
(slice 4) reads this cell as part of validating "Sheet reachable with expected header
row".

## `session_id` — row key format and source-ID parse rule

Format: **`{type}-{source-id}-{ISO date}`** (D-8), where `type` is a `session_type`
enum value and the trailing date is the session's open date. Example:
`page-ALERT-123-2026-07-19`.

**Source-ID parse rule**: to recover the source ID from a `session_id`, strip the
leading `{type}-` (where `type` is one of the closed `session_type` enum values) and
the trailing `-{YYYY-MM-DD}` (a fixed-shape ISO date). Everything left between the two
is the source ID **verbatim** — hyphens inside the source ID are legal.

```
page-ALERT-123-2026-07-19
└┬─┘ └───┬───┘ └───┬────┘
type  source-id   ISO date

strip leading "page-" and trailing "-2026-07-19" → source ID: "ALERT-123"
```

This parse rule is what join-at-open and merge-at-close (`references/../SKILL.md`
ownership section) use to match rows by source ID, never by recomputing `session_id`
(whose embedded date differs across days).

## Column table

Mutation classes (FR-002): **`A`** = write-once at append (immutable after; the
close-time update re-asserts open-time values, never recomputes), **`M`** = enumerated
mid-session mutable, **`C`** = close-time field group.

| Column | Type | Mutation | Notes |
|---|---|---|---|
| `session_id` | string | `A` | Row key; format `{type}-{source-id}-{ISO date}`; embeds open date — never recomputed for matching (D-8) |
| `session_type` | enum: `incident` / `page` / `test` | `M` | Promotion re-tag (§3.2); `test` excluded from retrieval |
| `status` | enum: `open` / `closed` / `handoff` / `superseded` | `M` | Non-terminal = `open` or `handoff` (join/rehydrate set); `superseded` excluded from retrieval |
| `fingerprint` | string (16 hex) | `A` | `bb.fp.v1` (`references/fingerprint.md`); re-asserted at close at its open-time value, never recomputed |
| `catalog_resolved` | bool | `A` | Ladder rung 1 vs 2–4; downgrades a stage-1 exact match to "candidate" when false on either row |
| `alert_signature` | string | `A` | Raw alert identity |
| `services` | string list | `A` | Catalog `metadata.name` values |
| `severity` | string | `M` | Triage-assessed; responder-correctable |
| `responder` | string | `M` | Ownership token: `<responder> @ <ISO timestamp>` (D-18) |
| `started_at` | ISO 8601 | `A` | Open timestamp |
| `closed_at` | ISO 8601 | `C` | Close timestamp |
| `triage_verdict` | JSON (`bb.verdict.v1`) | `M` | Checkpoint zero; refreshed on mid-session triage re-invocation |
| `latest_checkpoint` | JSON (`bb.ledger.v1` or overflow pointer) | `M` | Cell-guarded at 45,000 chars — see `SKILL.md`'s checkpoints section |
| `timeline` | JSON | `C` | Derived from tool trace + checkpoint history, never prose recall (D-5) |
| `root_cause` | string | `C` | **Human-curated** (Constitution V) |
| `resolution` | string | `C` | Human-approved |
| `links` | JSON | `C` | `{url, excerpt}` pair list (Constitution IV) |
| `runbook_refs` | JSON | `C` | URL + commit SHA where git-hosted |
| `diary_url` | URL | `C` | Dual-write link |
| `diary_pending` | bool | `C` | Diary-failure flag; `true` is the retry queue (research R10) |
| `report_url` | URL | `C` | Regenerable investigation report |
| `artifacts_folder_url` | URL | `C` | Per-session artifact folder |

## Mutation policy (FR-002)

Rows are **appended at open**; thereafter only this enumerated set mutates:

- `status`
- `session_type` (promotion re-tag)
- `responder` (ownership take-over)
- `severity` (responder correction)
- `triage_verdict` (mid-session triage re-invocation on new alerts)
- `latest_checkpoint`
- the **close-time field group**: `closed_at`, `timeline`, `root_cause`, `resolution`,
  `links`, `runbook_refs`, `diary_url`, `diary_pending`, `report_url`,
  `artifacts_folder_url`

Every other field is **immutable after append**. Write-once fields the close-time
update *carries* (notably `fingerprint`) are **re-asserted at their open-time values,
never recomputed** — improved catalog resolution mid-session benefits future sessions'
fingerprints, not the open row's.

## Evidence and causal fields (Constitution IV, V)

- `root_cause` and `resolution` are **human-curated** — no convention here auto-promotes
  a hypothesis into either field (Constitution V).
- `links` (and every other evidence-bearing field, including the duplicate fold-in at
  merge-at-close) is a list of `{url, excerpt}` pairs — never prose alone
  (Constitution IV).
