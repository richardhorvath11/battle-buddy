# Lifecycle-Command Protocol (cross-slice authority)

Normative pins the shipped command prose restates and later slices consume: slice 6
(triage hand-off, briefing consumption, deep-launch commitments), slice 8 (diary draft
rendering inputs), slice 9 (shell call points), and the local-state protocol's next
version (two documented extensions below). Shipped `commands/*.md` are runtime-facing
restatements; this document is the dev-side authority the contract tests bind to.
Changes here follow the same versioning duty as every `bb.*` contract: consumers
updated in the same change, never silently.

## Preflight decision table (`/page`, `/incident` — FR-001)

Evaluated in order, before any store read or probe. "Stamp state" is slice-4
`doctor_flows.evaluate_stamp` semantics — this document consumes slice 4's pin
(matching-only staleness), never redefines it.

| # | Observed state | Action |
|---|---|---|
| 1 | No `battleBuddy` config block | Stop: "run /setup". No session artifacts are created — never half-open |
| 2 | Config block malformed | Stop: repair case, surfaced explicitly (slice-4 posture — never treated as absent) |
| 3 | Marker present, `open_write_confirmed: true` | Stop: a session is already open — surface it, offer `/close` first (protocol v1 one-session rule) |
| 4 | Marker present, `open_write_confirmed: false` | Crash residue: surface it; proceed only on explicit responder confirmation, which **rewrites** the marker as part of the new open (never a standalone delete — deletion-is-cleared belongs to confirmed close alone) |
| 5 | Stamp missing or stale | Auto-run responder-mode setup (slice-4 `responder_mode`); on green, continue at 6 |
| 6 | Config valid, stamp fresh | Proceed to the open flow with **zero probe calls** (SC-002: write log untouched by preflight, no doctor report produced, stamp file byte-unchanged) |

**Ordering note**: marker rows 3–4 deliberately precede stamp row 5, although FR-001's
prose lists the stamp inside the preflight bundle first — the stale-stamp branch
auto-runs responder-mode setup, whose probes are store *reads*, and the crashed-open
Assumption requires marker detection **before any store read**. Marker-first is the
only order satisfying both.

## Open-flow order (the FR-001 pinned sequence)

After preflight: compute `session_id` = `{type}-{source-id}-{ISO date}` (date =
open-time **UTC** date) → write marker (`open_write_confirmed: false`) → shell
`open_pane` (session-named workspace; degraded: printed message) → alert context + flap
history (`alerting.get_alert` / `list_alert_history`; failure is fail-soft — see
below) → catalog resolve + fresh runbook/dashboard fetch (fixture surface until slice
7; fingerprint always via `bb-fingerprint`, ladder + `catalog_resolved` per slice-3
fingerprint reference) → tier-0 retrieval (slice-3 `retrieve_candidates`; the same
retrieval *point* also performs join detection via a client-side scan — the contract
has no source-ID server filter, so this is a second `read_records` by contract
limitation, not a second decision point — see Join) → triage (fixture verdict until slice 6) → verdict
validation (real validator; one re-prompt; second failure persists flagged
`schema_valid: false`) → **row append carrying the verdict** → read-back → marker
confirmation → briefing (+ `navigate_pane` to the top-cited dashboard).

**Checkpoint zero rides the append**: the validated (or flagged) verdict is serialized
with the slice-3 pinned serialization into the appended row's `triage_verdict` field —
never a separate post-append write. Cell guard applies at append: an over-guard verdict
is stored via `put_file` under `battle-buddy/<session_id>/checkpoint-0.json` **first**,
and the cell carries `{"overflow": "<link>", "seq": 0}`. The history line
(`staging/checkpoints.jsonl`, `{"seq": 0, "document": <full document>}`) is appended
per slice-3's history rule.

**Alert-fetch failure** (fail-soft, spec Assumption): the session still opens — marker,
row (`alert_signature` degraded to the alert ID), briefing notes "alert context
unavailable". Required-capability *absence* still fails loudly at session start.

## Marker lifecycle (writer-side; protocol v1 + two documented extensions)

This slice is the protocol's designated marker writer. States it writes:

1. **Created at open**: protocol-v1 shape, `open_write_confirmed: false`.
2. **Confirmed**: set `true` only after the open-time append's read-back returns
   exactly one row with the matching `session_id`.
3. **Join rewrite** (*protocol extension — flagged for the protocol's next version*):
   on join, the marker is rewritten to the joined session's identity — `session_id`
   (the joined row's), `source_id` (parsed per schema.md's rule), `opened_at` (the
   joined row's `started_at`) — and its confirmation is the **take-over write's
   read-back** (row's `responder` now names the joining responder).
4. **Crash-residue rewrite**: preflight row 4 above — rewrite on confirmation, never
   standalone deletion.
5. **Deleted**: only by confirmed close (read-back success), deleting the whole
   `.bb-session/` directory. A failed read-back leaves everything in place for the
   slice-2 session guard.

**Close-time ownership scope** (*second documented extension*): the slice-3 pre-write
ownership re-read — spec'd there for checkpoint writes — extends to `/close`'s row
writes: re-read `responder` immediately before the merge's row updates and immediately
before the close-time `update_record`. On displacement: no row write, no marker
deletion; close goes read-only and reports the take-over. Earlier diary/artifact
writes stand (additive).

## Join-vs-separate (FR-004)

Detection is slice-3 `detect_open_session` (source ID parsed from `session_id`,
non-terminal status), performed on the open-time retrieval read. On a match: surface
the explicit choice; **no store write of any kind before the choice**. Join =
rehydrate from `latest_checkpoint`/`triage_verdict` (overflow followed) + take-over
write + marker rewrite (state 3 above); no new row. Separate = append a distinct row
(normal open flow) only on explicit choice; the marker tracks the new session only.

## Promotion (`/incident` inside an open page session — FR-003)

Promotion is one `update_record` re-tagging the existing row's
`session_type: incident` — never an append; same `session_id`; marker untouched (same
session). Deep investigation launches on promotion (FR-5f(b)). A fresh `/incident`
runs the open flow with `session_type: incident` and `deep_proposed` immediately after
triage; `deep_launched` requires responder confirmation unless
`battleBuddy.autoLaunchDeep` is true (additive config key, below). Spawn mechanics and
the ledger are slice 6's; these flags are the command-side commitment.

## Briefing artifact — `bb.briefing.v1`

Assembled mechanically from the verdict (content/format beyond these properties is
slice 6's `references/briefing.md`):

```json
{
  "schema": "bb.briefing.v1",
  "session_id": "page-ALERT-123-2026-07-21",
  "alert_context_available": true,
  "claims": [
    {"statement": "...", "evidence": [{"url": "...", "excerpt": "..."}]}
  ],
  "top_cited_dashboard": "<url or null>",
  "degraded": false,
  "printed_links": []
}
```

Structural invariants (tested): every claim carries ≥1 `{url, excerpt}` evidence entry
with both fields non-empty (Constitution IV); `top_cited_dashboard` is the dashboard
URL most cited across claim evidence (ties → first citation order); with a shell
adapter the flow issues `navigate_pane(top_cited_dashboard)`, degraded mode records
the same links in `printed_links` instead.

## Diary draft artifact — `bb.draft.v1` (FR-007, Constitution V)

Produced at `/close` draft time, **before** any write; the approval step operates on
this artifact; the rendered diary entry is generated from it.

```json
{
  "schema": "bb.draft.v1",
  "session_id": "...",
  "factual": {
    "timeline": [...],
    "links": [{"url": "...", "excerpt": "..."}],
    "services": [...], "severity": "...", "responder": "...",
    "started_at": "...", "closed_at": "..."
  },
  "proposals": {
    "root_cause":            {"proposal": true, "value": "..."},
    "contributing_factors":  {"proposal": true, "value": [...]},
    "action_items":          {"proposal": true, "value": [...]}
  },
  "approved": false
}
```

Structural invariants (SC-006, tested): causal values appear **only** under
`proposals.*` entries each carrying `"proposal": true`; `factual` contains no causal
keys; no write of any kind occurs while `approved` is false. Rendering: configured
template when `battleBuddy.diary.template` is set, else format-matched to
`diary.read_recent(5)` (slice-8 surface, consumed not defined); rendered causal
sections carry an explicit proposal label. The approved values land on the row's
`root_cause`/`resolution` fields only through the responder's curation of this
artifact.

## Close order (FR-008) and ordering-claim scope

1. **Merge-at-close first** (when same-source-ID non-terminal duplicates exist):
   slice-3 `merge_duplicates` — earliest `started_at` canonical, links + duplicate's
   artifacts folder folded in, duplicates `superseded`. All subsequent close steps
   target the **canonical** row, whichever session invoked `/close`; the closing
   session's marker deletion is gated on the canonical row's read-back.
2. **Draft + approval** (artifact above; no writes before approval).
3. **Dual-write, pinned order** (the FR-008/slice-3 ordering claim's scope — merge
   writes in step 1 precede the scope, exactly as slice 3 scopes mid-session writes
   out): diary `append_entry` (failure ⇒ continue, row lands `diary_pending: true` —
   the flag is the retry queue) → staged-artifact `put_file`s (transcript, trace under
   `tool-trace.jsonl`, checkpoint history, generated report; per-file failure ⇒ omit
   link, continue) → close-time `update_record` (close field group + re-asserted
   write-once fields; ownership re-read immediately before; transient failure ⇒ retry,
   close blocks on row-write success; displacement ⇒ read-only, above) → read-back →
   marker + `.bb-session/` deletion on confirmed match only.
4. **Shell close**: `close_workspace(session_id)`, state restorable; degraded: printed
   message. Runs last; fail-soft.

**No open session** (no marker): `/close` reports "no open session" and performs zero
writes.

## Transcript capture at close (FR-009)

Close copies the runtime's transcript file (the same `transcript_path` hooks receive;
tests supply a fixture path) into `staging/transcript.md`, then uploads through the
normal mapping. Missing/unreadable source ⇒ logged notice, artifact omitted (slice-3
artifact-failure posture), close continues. Turns after close are absent from the
upload — accepted v1 limitation. *Flagged for local-state-protocol reconciliation*
(protocol v1 stages the transcript at SessionEnd only).

## Timeline derivation (FR-009, D-5)

A pure function over the local trace and checkpoint history — never transcript text:

- each `trace.jsonl` **call line** (no `event` field) →
  `{"at", "source": "trace", "seq", "summary", "outcome"}`;
- each `staging/checkpoints.jsonl` entry →
  `{"at", "source": "checkpoint", "seq", "phase"}` (`at`/`phase` from the wrapped
  document where present);
- ordered by `at`, ties by (`source`, `seq`).

The mapping is 1:1 and complete: every input line yields exactly one event; no event
exists without an input line.

## Additive config keys (extend `bb.config.v1`; additive, no version bump)

| Key | Type | Default when absent | Read by |
|---|---|---|---|
| `battleBuddy.autoLaunchDeep` | bool | `false` — deep launch requires responder confirmation | `/incident`, promotion |
| `battleBuddy.diary.template` | string | absent — draft rendering format-matches `read_recent(5)` | `/close` drafting |

Same additive standard the local-state protocol applied to `denied:*` outcomes: no
existing key's shape or consumer changes.

## Fixture surfaces (consumed slices, pinned stand-ins)

| Consumed surface | Slice | Hermetic stand-in |
|---|---|---|
| Triage verdict | 6 | Fixture `bb.verdict.v1` documents + ordered re-prompt lists; validated by the real `bb-validate` |
| Catalog resolution | 7 | Fixture catalog data + deterministic resolver walking the §5.2 ladder; fingerprints via the real `bb-fingerprint` |
| Diary recent entries | 8 | Mock `diary.read_recent` |
| Shell adapter | 9 | `RecordingShellAdapter` (open_pane / navigate_pane / notify / close_workspace) + failing variant; degraded = printed-message records |
| Alert fetch failure | — | `get_alert` on an unseeded alert (`not_found`); richer fault injection deliberately deferred (research R15) |
