# Session-Store Retrieval Reference

Normative for the `session-store` skill (FR-007; design §5.5, §5.2, D-19). The
three-stage retrieval flow, run at session open, that recognizes a repeat incident before
investigation starts. Placement note: this content is normative here regardless of which
skill *invokes* it — slice 6's investigation skill references this document rather than
duplicating it (research R3). Follow these instructions in order.

## Contract note — read this before stage 1

`storage`'s `read_records` offers only field-equality filters, returned in insertion
order (operation contract v1) — no keyword/overlap matching, no server-side ranking. So:

- Stage 1's fingerprint match MAY use a store-side filter:
  `read_records({"filter": {"fingerprint": <incoming fingerprint>}})`.
- Everything else — the exclusions below, and stage 2's keyword overlap — is computed
  **client-side over a full `read_records` read** (empty/absent filter — every row).

Relevance ranking beyond the stage-3 cap is stage-3 **agent** work, out of scope here.

## Stage 0 — exclusions (apply before every stage's match)

Before matching at any stage, drop any row where:

- `session_type == "test"` (setup smoke session), or
- `status == "superseded"` (merged duplicate — see the ownership section of `SKILL.md`).

These exclusions apply at **every** stage — stage 1's exact match and stage 2's keyword
overlap both operate only over rows that survive this filter. A row failing either check
must never surface as a candidate, no matter how strongly it would otherwise match.

## Stage 1 — fingerprint exact match

Compute the incoming session's fingerprint (`references/fingerprint.md`). Read rows whose
`fingerprint` field equals it via the store-side filter, then apply the stage-0
exclusions to the result client-side (the filter has no way to express them; `test`/
`superseded` rows can come back from the store-side call and must be dropped before
anything below looks at the result).

- **Hit, no downgrade**: at least one row survives, and neither the incoming session's own
  `catalog_resolved` nor **any** surviving matched row's `catalog_resolved` is `false` →
  classification `"known_issue"` (near-certain known issue).
- **Hit, downgraded**: at least one row survives, but the incoming session's
  `catalog_resolved` is `false`, or **any** surviving matched row's `catalog_resolved` is
  `false` → classification `"candidate"`, never `"known_issue"` (`references/fingerprint.md`
  service-resolution ladder; the flag travels with the row so a later match can honor it —
  checking only the stored side would miss the incoming session's own unresolved-catalog
  case).
- **No surviving row**: proceed to stage 2.

If stage 1 produces at least one surviving match, it **fully determines** the candidate
set for this retrieval — stage 2 does not run.

## Stage 2 — keyword overlap (only when stage 1 found nothing)

Over the full `read_records` read (empty filter — every row), apply the stage-0
exclusions, then select every surviving row that overlaps the incoming session on **any**
of:

- `services` — list overlap: at least one element in common with the incoming session's
  `services`.
- `alert_signature` — equality.
- `severity` — equality.

Every row selected this way classifies `"candidate"` — keyword overlap is never
"near-certain", regardless of how many of the three fields overlap.

## Stage 3 — cap and hand-off

Whichever stage produced candidates, the set handed onward is capped at **20**. The cap
keeps the **first 20 surviving matches in insertion order** — the one ordering guarantee
this convention makes (ranking the kept set by relevance is stage-3 agent work, out of
scope here); this keeps the truncated set reproducible across repeated runs of the same
seed.

Truncation is **stated, never silent**. The result handed to the triage stage is the
surfacing shape:

```
{candidates, classification, truncated, total_matched}
```

- `candidates` — the (possibly capped) surviving rows, in insertion order.
- `classification` — `"known_issue"` | `"candidate"` | `None` (no row survived any
  stage).
- `truncated` — `true` iff more than 20 rows survived before the cap; `false` otherwise.
- `total_matched` — the pre-cap count of surviving matches (equals `len(candidates)`
  whenever `truncated` is `false`).

## Empty result

Zero surviving candidates — whether the store is empty, or every row is dropped by stage
0, or nothing overlaps at stage 2 — is a **normal outcome, never an error**: retrieval
returns `{candidates: [], classification: None, truncated: false, total_matched: 0}` and
the flow proceeds straight to fresh investigation. No stage of this convention has a
failure mode for "nothing matched" (spec Edge Cases).
