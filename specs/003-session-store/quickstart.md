# Quickstart: Session-Store Conventions

How to validate this slice end-to-end. Everything is hermetic — no credentials, no
network, no Google anything.

## Prerequisites

```bash
pip install pytest          # the harness's only dev dependency
make verify                 # baseline must be green before this slice's work
```

## Run it

```bash
make verify                 # both hermetic layers (unit + contract)
make test-contract          # just the contract layer (this slice's tests live here)
pytest tests/contract/test_close_flow.py -v        # one module during development
```

## Validation scenarios → where they're proven

| # | Scenario (spec source) | Test module |
|---|---|---|
| 1 | Exact-fingerprint hit surfaces; `test`/`superseded` never do; unresolved-catalog match downgraded; cap-20 truncation surfaced (US1) | `tests/contract/test_retrieval_flow.py` |
| 2 | Close writes land diary → artifacts → row in the mock's write log; read-back clears the marker; diary failure → `diary_pending: true`; artifact failure → link omitted, row still lands (US2 + edge case) | `tests/contract/test_close_flow.py` |
| 3 | In-cell vs overflow at the 45,000-char boundary; overflow link round-trips via `get_file`; validate-fail → one re-prompt → persist flagged; one-row-read resume (US3) | `tests/contract/test_checkpoint_conventions.py` |
| 4 | Take-over write; displaced writer's pre-write re-read denies the checkpoint; join-at-open on source ID + non-terminal status; merge-at-close leaves one canonical + one `superseded` row (US4) | `tests/contract/test_ownership.py` |
| 5 | Folder-per-session naming, the four artifact names, `trace.jsonl` → `tool-trace.jsonl` mapping, links resolve to content (US5) | `tests/contract/test_artifact_layout.py` |
| 6 | Schema doc column table == test canonical columns (SC-006); mutation policy enforced; no concrete MCP tool names in skill prose (FR-010) | `tests/contract/test_store_schema_doc.py` |
| 7 | Fingerprint doc version == helper `VERSION` == golden corpus; doc examples recompute through the real helper (FR-003) | `tests/contract/test_fingerprint_reference.py` |

## Reading the deliverable

The shipped artifact is documentation: start at `skills/session-store/SKILL.md`
(lifecycle conventions), then `references/schema.md` (columns + mutation policy +
`bb.schema.v1`), `references/fingerprint.md` (normative `bb.fp.v1` rules), and
`references/retrieval.md` (three-stage flow). The executable form of every convention is
`tests/helpers/store_flows.py` — each step cites the skill section it executes.

## Expected outcome

`make verify` green with the new contract modules included; every FR-001–FR-009
requirement traceable to ≥1 passing test (FR-011/SC-001); zero storage code anywhere
outside `tests/` (FR-012 — the packaging test enforces the fence mechanically).
