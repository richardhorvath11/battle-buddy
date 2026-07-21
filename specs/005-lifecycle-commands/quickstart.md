# Quickstart — Lifecycle Commands validation

Prerequisites: repo checkout, `pip install pytest` (dev-only). Everything is hermetic —
no credentials, no network, no Google.

## Run the gate

```bash
make verify                 # both hermetic layers — the pre-done gate
make test-contract          # layer 2 only (this slice's tests live here)
pytest tests/contract/test_lifecycle_full_sim.py -q   # the SC-007 end-to-end sim
```

## Scenario → assertion map

| Scenario (spec) | Test module | Proves |
|---|---|---|
| US1 AS-1/SC-002 — happy-path preflight, no probes | `test_page_preflight.py` | write log untouched, no doctor report, stamp byte-unchanged |
| US1 AS-2 — missing config | `test_page_preflight.py` | stop with "run /setup", zero session artifacts |
| FR-001 marker handling — confirmed / crash residue | `test_page_preflight.py` | confirmed ⇒ stop+offer-close; unconfirmed ⇒ rewrite only on confirmation |
| US1 AS-3 — open append + read-back + marker confirm | `test_open_flow.py` | row fields, `open_write_confirmed` only after read-back |
| US1 AS-4 / edge "triage returns nothing usable" | `test_open_flow.py` | real-validator gate: pass / re-prompt / flagged persist; verdict rides the append (no separate write); overflow stores artifact first |
| Edge — alert fetch fails | `test_open_flow.py` | session still opens, degradation surfaced |
| Edge — catalog resolution fails | `test_open_flow.py` | ladder walked, `catalog_resolved: false`, briefing notes downgrade |
| US1 AS-5 / FR-006 | `test_briefing_properties.py` | every claim `{url, excerpt}`; navigate-pane vs printed links |
| US2 AS-1/AS-2, SC-003 | `test_incident_flows.py` | incident defaults, deep proposal/auto-launch, promotion = update not append |
| US3 AS-1–3, SC-004 | `test_join_separate.py` | no writes before choice; join = rehydrate + take-over + marker rewrite; separate = exactly one new row |
| US4 AS-1–4/6, SC-005/SC-006 | `test_close_command.py` | draft structure (causal-only-under-proposals), dual-write order via write log, `diary_pending`, read-back-then-delete, transcript capture, timeline 1:1 from trace+checkpoints |
| US4 AS-5/AS-7, edges — merge, ownership, no session | `test_close_merge_ownership.py` | one non-superseded row after merge; displaced close goes read-only; no-marker close writes nothing |
| SC-007 — full open→close | `test_lifecycle_full_sim.py` | end-to-end artifact assertions; zero ops outside operation contract v1 |
| FR-011 naming gate | `test_command_capability_naming.py` (existing) | new `commands/*.md` auto-covered by glob |

Shapes and invariants cited by these tests: [`contracts/lifecycle-protocol.md`](contracts/lifecycle-protocol.md);
entity map: [`data-model.md`](data-model.md).
