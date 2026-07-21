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

_Stub — filled by T011 (US2): the pinned close-time write order (diary → artifacts →
row update → read-back → marker clearance), the open-time append/read-back twin, and
the diary/artifact/not-found failure paths._

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
