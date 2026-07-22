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
| 6 | Schema doc column table == test canonical columns (SC-006); mutation policy enforced; `bb.schema.v1` + stability commitment present | `tests/contract/test_store_schema_doc.py` |
| 7 | Fingerprint doc version == helper `VERSION` == golden corpus; doc examples recompute through the real helper (FR-003) | `tests/contract/test_fingerprint_reference.py` |
| 8 | No `mcp__` marker anywhere; no concrete MCP server/product name in normative prose (fenced worked-example data exempted); every doc-cited operation exists in `contract.json` (FR-010) | `tests/contract/test_skill_capability_naming.py` |

## FR-001–FR-013 → test module mapping (SC-001's record)

Every functional requirement this slice owns, traced to the module(s) that actually
assert it — not just cite it in a docstring.

| FR | What it requires | Proven by |
|---|---|---|
| FR-001 | Schema doc: full column table, `session_id` format + source-ID parse rule, `bb.schema.v1` version | `tests/contract/test_store_schema_doc.py` |
| FR-002 | Append-mostly mutation policy: the enumerated mutable/close-time sets; write-once fields (`fingerprint`) re-asserted, never recomputed, at close | `tests/contract/test_store_schema_doc.py` (doc↔`store_flows` enumeration match); `tests/contract/test_close_flow.py` (`test_close_reasserts_write_once_fields_never_caller_values`) |
| FR-003 | Fingerprint reference: `bb.fp.v1` rules, ladder, `catalog_resolved` semantics, version tied to the helper + golden corpus | `tests/contract/test_fingerprint_reference.py` |
| FR-004 | Artifact layout: per-session folder, the four documented names, local→uploaded mapping, row discoverability | `tests/contract/test_artifact_layout.py` |
| FR-005 | Checkpoint representation: `triage_verdict`/`latest_checkpoint`, session-local history accumulation, 45,000-char cell guard + overflow pointer | `tests/contract/test_checkpoint_conventions.py` |
| FR-006 | Validation gate before every checkpoint write: one re-prompt, second failure persists flagged `schema_valid: false` | `tests/contract/test_checkpoint_conventions.py` (AS-3 tests) |
| FR-007 | Three-stage retrieval: exclusions at every stage, fingerprint exact-match, keyword overlap, cap-20 with truncation surfaced | `tests/contract/test_retrieval_flow.py` |
| FR-008 | Close-time dual-write order + read-back-gated marker clearance; open-time twin (`open_write_confirmed`); diary-failure and `not_found` paths | `tests/contract/test_close_flow.py` |
| FR-009 | Optimistic ownership: take-over write, mandatory pre-write re-read, join-at-open by source ID, merge-at-close | `tests/contract/test_ownership.py` |
| FR-010 | Skill prose names capabilities/operations only, never a concrete MCP server or tool name | `tests/contract/test_skill_capability_naming.py` |
| FR-011 | Every convention exercised by ≥1 hermetic contract test; schema doc mechanically cross-checked against test constants (SC-006) | the `tests/contract/` suite as a whole; `test_store_schema_doc.py`'s doc↔`store_flows` cross-check is SC-006's specific instrument |
| FR-012 | No shipped storage code — documentation and tests only, all I/O through the operation contract | `tests/unit/test_packaging.py` (bundle-boundary fence) plus the absence of any storage code outside `tests/` |
| FR-013 | Tier-1 stability commitment recorded alongside the schema version | `tests/contract/test_store_schema_doc.py` (`bb.schema.v1` + "migration-stable" presence checks) |

## Reading the deliverable

The shipped artifact is documentation: start at `skills/session-store/SKILL.md`
(lifecycle conventions), then `references/schema.md` (columns + mutation policy +
`bb.schema.v1`), `references/fingerprint.md` (normative `bb.fp.v1` rules), and
`references/retrieval.md` (three-stage flow). The executable form of every convention is
`tests/helpers/store_flows.py` — each step cites the skill section it executes.

## Expected outcome

`make verify` green with the new contract modules included; every FR-001–FR-013
requirement traceable to ≥1 passing test (FR-011/SC-001 — see the mapping table
above); zero storage code anywhere outside `tests/` (FR-012 — the packaging test
enforces the fence mechanically); zero concrete MCP server/tool names anywhere in
the skill docs (FR-010).
