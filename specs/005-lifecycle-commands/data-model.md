# Data Model — Lifecycle Commands

Entities this slice reads, writes, or pins. Shapes marked **(authority)** are defined
normatively in [`contracts/lifecycle-protocol.md`](contracts/lifecycle-protocol.md);
everything else is consumed from an upstream slice and never redefined here.

## Consumed (upstream authorities)

| Entity | Authority | This slice's use |
|---|---|---|
| Session row (`bb.schema.v1`) | slice 3 `references/schema.md` | Appended at open (verdict riding the append), re-tagged on promotion, take-over on join, merged + closed at close; mutation classes obeyed (`store_flows.COLUMNS`) |
| Session marker (`marker.json`, `bb.local.v1`) | slice 2 local-state protocol | This slice is the designated writer — states 1–5 in the contracts doc (create, confirm, join rewrite, crash rewrite, delete-on-confirmed-close) |
| Trace / counters / staging | slice 2 local-state protocol | Read-only inputs: `trace.jsonl` call lines + `staging/checkpoints.jsonl` feed timeline derivation; `staging/` is the upload source at close |
| Checkpoint documents (`bb.verdict.v1`, `bb.ledger.v1`) | design §5.4 + `bb-validate` | Verdict validated before persist (one re-prompt, flagged on second failure); rehydration reads `latest_checkpoint`/`triage_verdict` with overflow following |
| Fingerprint (`bb.fp.v1`) | slice 2 `bb-fingerprint` + slice 3 reference | Computed at open through the real helper; ladder rung recorded as `catalog_resolved` |
| Retrieval flow | slice 3 `references/retrieval.md` / `retrieve_candidates` | The open-time read; doubles as join detection |
| Green stamp (`bb.stamp.v1`) + doctor report | slice 4 `contracts/doctor-protocol.md` | Preflight trusts `evaluate_stamp`; responder-mode auto-run on missing/stale |
| Config block (`bb.config.v1`) | slice 4 contracts doc | Read for store/diary/catalog/shell/budgets; two additive keys pinned this slice (below) |
| Operation contract v1 | slice 1 `contract.json` | The only I/O surface; close/open writes are `append_record`/`read_records`/`update_record`/`put_file`/`append_entry`/`read_recent`/`get_alert`/`list_alert_history` |

## Pinned by this slice (authority)

### Preflight decision (state machine)

Six ordered rows (contracts doc table): no-config → stop; malformed-config → repair
stop; confirmed marker → stop (offer close); unconfirmed marker → crash-residue
confirm-to-rewrite; stale/missing stamp → responder-mode auto-run; fresh → proceed,
zero probes.

### Briefing artifact — `bb.briefing.v1`

`{schema, session_id, alert_context_available, claims: [{statement, evidence:
[{url, excerpt}]}], top_cited_dashboard, degraded, printed_links}`. Invariants: every
claim ≥1 evidence pair, both fields non-empty; navigate-vs-printed branch exclusive on
`degraded`.

### Diary draft artifact — `bb.draft.v1`

`{schema, session_id, factual: {...}, proposals: {root_cause, contributing_factors,
action_items — each {"proposal": true, "value": ...}}, approved}`. Invariants: causal
values only under `proposals.*`; no causal keys in `factual`; zero writes while
`approved` is false.

### Timeline event

`{"at", "source": "trace" | "checkpoint", "seq", ...}` — trace events carry
`summary`/`outcome`, checkpoint events carry `phase`; ordered by `at`, ties by
(`source`, `seq`); 1:1 with input lines.

### Additive config keys

`battleBuddy.autoLaunchDeep` (bool, default false); `battleBuddy.diary.template`
(string, default absent → format-match `read_recent(5)`).

### Marker extensions (flagged for protocol reconciliation)

Join rewrite (confirmation = take-over read-back) and close-time ownership scope —
normative statements in the contracts doc.

## Fixture surfaces (dev-only, `tests/helpers/lifecycle_fixtures.py` + `tests/fixtures/lifecycle/`)

| Fixture | Stands in for | Shape |
|---|---|---|
| `verdicts/*.json` | slice-6 triage output | `bb.verdict.v1` documents (valid, invalid, invalid-then-valid re-prompt pairs, over-guard sized); validated by real `bb_validate` |
| `catalog.json` + resolver | slice-7 catalog adapter | fixture services (name, runbooks, dashboards, alert_matchers, depends_on); resolver walks the §5.2 ladder with caller-injected rung answers |
| `RecordingShellAdapter` | slice-9 `bb-shell` | records `open_pane`/`navigate_pane`/`notify`/`close_workspace` calls; `FailingShellAdapter` variant errors mid-flow; degraded mode = printed-message records in flow outcomes |
| `seeds/*.json` | prior store state | seeded rows for join (yesterday-dated open row), merge (same-source duplicates), promotion (open page row), ownership (displaced responder) |
| transcript source | runtime `transcript_path` | fixture markdown file path passed to the close flow |

## Flow outcomes (test-facing return shapes, `lifecycle_flows.py`)

Mirroring the slice-3/4 outcome-dict convention:

- `preflight(...)` → `{proceed, stopped_reason, responder_mode_ran, marker_state,
  stamp_state}`
- `open_command(...)` → `{session_id, marker, readback_confirmed, verdict_valid,
  verdict_overflowed, briefing, join_offer, shell_calls/printed, alert_context_available,
  deep_proposed, deep_launched}`
- `promote_session(...)` → `{session_id, retagged, deep_launched}`
- `join_session(...)` → `{session_id, rehydrated_checkpoint, takeover_result,
  marker_rewritten, marker_confirmed}`
- `draft_close(...)` → the `bb.draft.v1` artifact
- `close_command(...)` → `{merged, canonical_id, draft, diary_link, diary_pending,
  uploaded, omitted_artifacts, timeline, update_result, readback_confirmed,
  marker_cleared, read_only, taken_over_by, shell_closed/printed}`
