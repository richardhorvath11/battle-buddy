# Investigation Schemas Reference

Normative for the `investigation` skill (FR-011; design §5.4, D-14; Constitution VI).
This is the documented statement of `bb.verdict.v1` (the triage structured verdict) and
`bb.ledger.v1` (the deep-investigation hypothesis ledger checkpoint). The **normative
implementation** is `bin/bb-validate` / `bin/bb_validate.py` — every field table, phase
rule, and vocabulary below states exactly what that validator enforces in v1, no more
and no less. See "Validator relationship" for how the two are kept from diverging
silently.

## bb.verdict.v1 — triage structured verdict

| Field | Type | Required | v1 validation |
|---|---|---|---|
| `schema` | str | yes | must equal `bb.verdict.v1` |
| `session_id` | str | yes | presence + type |
| `severity` | str | yes | presence + type |
| `no_strong_signal` | bool | yes | presence + type (honest no-signal is first-class) |
| `budget_spent` | dict | yes | presence + type; carries `turns` (hook-counted) and `seconds` (measured wall-clock — reported, never enforced) |
| `candidates` | list | yes | each entry per Candidate below |
| `known_issue` | dict | no | when present, `validation` MUST be `VALIDATED`/`INVALIDATED` (recalled memory); other sub-fields carried but unvalidated in v1 |
| `flap_assessment` | str | no | type only |
| `next_step` | str | no | type only |
| `deploy_window` | list | no | type only |

### Candidate (verdict `candidates[]`)

| Field | Type | Required | v1 validation |
|---|---|---|---|
| `statement` | str | yes | presence + type |
| `provenance` | str | yes | ∈ `triage` \| `recall` \| `fresh` |
| `validation` | str | non-`fresh` only | ∈ `VALIDATED` \| `INVALIDATED`; required whenever provenance ≠ `fresh` |
| `confidence` | number | no | within [0, 1]; bool rejected |
| `evidence` | list | no | each entry per Evidence below |

## bb.ledger.v1 — hypothesis ledger checkpoint

| Field | Type | Required | v1 validation |
|---|---|---|---|
| `schema` | str | yes | must equal `bb.ledger.v1` |
| `seq` | int | yes | presence + type (ledger-turn counter; distinct from the checkpoint history wrapper's ordinal — slice-3 pin) |
| `at` | str | yes | presence + type (ISO 8601 by convention) |
| `phase` | str | yes | ∈ closed phase enumeration below; unknown ⇒ error, never guess |
| `hypotheses` | list | yes | each entry per Hypothesis below |
| `services_touched` | list | no | type only |
| `tool_call_count` | int | no | type only |

### Hypothesis (ledger `hypotheses[]`)

| Field | Type | Required | v1 validation |
|---|---|---|---|
| `id` | str | yes | presence + type |
| `statement` | str | yes | presence + type |
| `status` | str | yes | any string accepted; only `"live"` counts toward the anchoring invariant (unknown status shrinks the live set — fails loud via `ledger.min_live_hypotheses`, never silently passes) |
| `provenance` | str | yes | ∈ `triage` \| `recall` \| `fresh` |
| `validation` | str | non-`fresh` only | ∈ `VALIDATED` \| `INVALIDATED` |
| `confidence` | number | no | within [0, 1]; bool rejected |
| `evidence_for` | list | no | each entry per Evidence below |
| `evidence_against` | list | no | each entry per Evidence below |

## Evidence entry (Constitution IV — everywhere evidence appears)

| Field | Type | Required |
|---|---|---|
| `url` | str, non-empty after strip | yes |
| `excerpt` | str, non-empty after strip | yes |

Prose-only evidence — a bare string, or a dict missing or blanking either key — is
invalid by schema: rule `evidence.not_url_excerpt_pair`. This applies identically
wherever an evidence list appears: a candidate's `evidence`, a hypothesis's
`evidence_for`/`evidence_against`. The same shape is the discipline for briefings and
findings summaries too (`references/briefing.md`), even though those are not
`bb-validate`-checked documents in v1.

## Phase model and anchoring guard (FR-002)

```
triage-seeded → hypothesis-generation → evidence-gathering → deep-dive → resolution
```

- **Invariant phases** (`evidence-gathering`, `deep-dive`): ≥3 `live` hypotheses
  (rule `ledger.min_live_hypotheses` when short) and ≥1 *live* `fresh` hypothesis
  (rule `ledger.fresh_required` when absent) — a **dead** `fresh` hypothesis does not
  satisfy this; only a `fresh` hypothesis with `status == "live"` counts.
- **Early phases** (`triage-seeded`, `hypothesis-generation`): sparse or empty ledgers
  are legal — this is what makes immediate escalation lawful before a full triage
  verdict exists. "Empty" means `hypotheses: []`: the `hypotheses` field itself is
  **always required**, in every phase — omitting it trips `schema.missing_field`
  regardless of phase.
- **`resolution`**: non-invariant — no minimum live count, no fresh requirement.
- **Enforcement**: the slice-2 validator (`bin/bb-validate`), at every checkpoint
  write (Constitution II/VI). The skill instructs; the validator verifies. Nothing in
  this document or in an agent definition self-enforces the guard.

## v1 scope note

This document tracks the validator's own recorded v1 scope exactly (its docstring is
the source of this note — restated here so the normative doc carries it too, per
FR-011/R9):

- `known_issue`'s sub-fields beyond `validation` (`matched_session_id`,
  `prior_resolution`, and similar) are **carried but unvalidated** in v1 — present in
  the design's worked examples, not yet schema-checked.
- Hypothesis `status` accepts **any string**. Only the literal value `"live"` counts
  toward the anchoring invariant's live count. An unknown or misspelled status (e.g.
  `"open"` where `"live"` was meant) silently shrinks the live set rather than being
  rejected outright — but this fails **loud**, never silently: a shrunk live set is
  exactly what trips `ledger.min_live_hypotheses` in an invariant phase. There is no
  quiet path where a wrong status both goes unflagged and defeats the guard.

Anything stricter documented as normative here that the validator does not enforce
would break the doc↔validator agreement this document exists to guarantee — so this
scope note is a boundary, not an aspiration: future tightening is a versioned change
to both the validator and this document together.

## Validator relationship (slice-3 FR-003 precedent)

Same shape as `skills/session-store/references/fingerprint.md`'s doc↔helper↔corpus
tie:

- **`bin/bb-validate` / `bin/bb_validate.py`** is the implementation of record for
  this document. `validate(doc)` returns every violation of a parsed document in one
  pass (never partial, never mutates input); the CLI wraps it with exit codes
  (0 = pass, 1 = violations found, 2 = usage/parse error).
- **`tests/fixtures/validate/*.json`** is the validator's own fixture corpus — its
  executable form, one case per rule at minimum, asserted exactly against
  `bb_validate.validate()` by `tests/unit/test_validate.py`.
- **`tests/contract/test_schemas_reference.py`** is the consistency check that ties
  this document to that implementation: every worked example below is parsed out of
  this file and run through the real `bb_validate.validate()`, and the vocabulary
  block immediately following is compared for exact set-equality against the
  validator's own constants (`PHASES`, `INVARIANT_PHASES`, `PROVENANCE_VALUES`,
  `VALIDATION_VALUES`, `MIN_LIVE_HYPOTHESES`, `VERDICT_SCHEMA`/`LEDGER_SCHEMA`). A doc
  edit that silently drifts from the validator fails there, not in review.

## Vocabulary (machine-readable)

```
phases: triage-seeded | hypothesis-generation | evidence-gathering | deep-dive | resolution
invariant-phases: evidence-gathering | deep-dive
provenance: triage | recall | fresh
validation: VALIDATED | INVALIDATED
min-live: 3
schemas: bb.verdict.v1 | bb.ledger.v1
```

## Violation rules

The complete rule vocabulary the validator can emit — every documented-invalid worked
example below names one or more of these:

`schema.not_object`, `schema.unknown_version`, `schema.missing_field`,
`schema.wrong_type`, `provenance.unknown`, `validation.unknown_value`,
`memory.unvalidated_non_fresh`, `confidence.out_of_range`,
`evidence.not_url_excerpt_pair`, `ledger.unknown_phase`,
`ledger.min_live_hypotheses`, `ledger.fresh_required`.

## Worked examples

Each example is an HTML comment marker line immediately followed by a fenced JSON
block: `<!-- bb-example: <id> expect=valid -->` for a document that must produce zero
violations, or `<!-- bb-example: <id> expect=invalid rule=<rule>[,<rule>] -->` for a
document that must produce every named rule among its violations (a document may
legitimately trip more than the named rule or rules; the test asserts membership, not
an exact set). `tests/contract/test_schemas_reference.py` parses every marker+fence
pair here and runs it through the real validator.

### Valid verdict — mixed provenance, non-fresh validated, evidence pairs

<!-- bb-example: valid-verdict-mixed-provenance expect=valid -->
```json
{
  "schema": "bb.verdict.v1",
  "session_id": "page-checkout-api-high-latency-2026-07-19",
  "severity": "sev3",
  "no_strong_signal": false,
  "budget_spent": {"turns": 9, "seconds": 87},
  "known_issue": {
    "matched_session_id": "page-checkout-api-2026-06-02",
    "prior_resolution": "Rolled back the retry-backoff change; latency recovered within 4 minutes.",
    "validation": "VALIDATED"
  },
  "candidates": [
    {
      "statement": "Recalled: pod memory pressure caused the same alert last month.",
      "provenance": "recall",
      "validation": "INVALIDATED",
      "confidence": 0.3,
      "evidence": [
        {"url": "https://dashboards.example/checkout-api/memory", "excerpt": "Memory usage flat at 40% for the incident window, no pressure detected."}
      ]
    },
    {
      "statement": "A deploy 12 minutes before alert onset touched the checkout-api request path.",
      "provenance": "fresh",
      "confidence": 0.7,
      "evidence": [
        {"url": "https://code.example/commit/abc123", "excerpt": "Changed retry backoff in checkout-api request handler."}
      ]
    },
    {
      "statement": "Triage's own read of the alert payload: p99 latency crossed 3x baseline.",
      "provenance": "triage",
      "validation": "VALIDATED",
      "confidence": 0.9,
      "evidence": [
        {"url": "https://dashboards.example/checkout-api/latency", "excerpt": "p99 latency 1450ms vs 480ms baseline at alert time."}
      ]
    }
  ],
  "flap_assessment": "real",
  "next_step": "deep_investigation",
  "deploy_window": [
    {"pr_url": "https://code.example/pr/456", "merged_at": "2026-07-19T03:29:00Z", "touches": ["checkout-api"]}
  ]
}
```

### Valid verdict — honest no-strong-signal, budget-truncated

<!-- bb-example: valid-verdict-no-signal-budget-truncated expect=valid -->
```json
{
  "schema": "bb.verdict.v1",
  "session_id": "page-orders-worker-2026-07-20",
  "severity": "sev4",
  "no_strong_signal": true,
  "budget_spent": {"turns": 15, "seconds": 118},
  "candidates": []
}
```

This is the truncation case: the turn cap (default 15, `budgets.triageTurnCap`) was
hit before a strong signal emerged. `no_strong_signal: true` and a `budget_spent` that
shows the cap is what makes this an **honest** verdict rather than a failure — there is
no separate "truncated" signal to invent; these two fields already say it.

### Invalid verdict — recalled candidate without validation

<!-- bb-example: invalid-verdict-unvalidated-recall expect=invalid rule=memory.unvalidated_non_fresh -->
```json
{
  "schema": "bb.verdict.v1",
  "session_id": "page-billing-api-2026-07-18",
  "severity": "sev2",
  "no_strong_signal": false,
  "budget_spent": {"turns": 6, "seconds": 52},
  "candidates": [
    {
      "statement": "Recalled from a prior session: database connection pool exhaustion.",
      "provenance": "recall",
      "confidence": 0.5,
      "evidence": [
        {"url": "https://dashboards.example/billing-api/db-pool", "excerpt": "Connection pool utilization at 62%, no exhaustion this window."}
      ]
    }
  ]
}
```

Recalled memory is a hypothesis, never a conclusion: a `recall`-provenance candidate
missing `validation` trips `memory.unvalidated_non_fresh` — recalled candidates must be
marked `VALIDATED`/`INVALIDATED` against current-incident evidence before being acted
on.

### Valid ledger — seeded from triage, early phase

<!-- bb-example: valid-ledger-seeded-from-triage expect=valid -->
```json
{
  "schema": "bb.ledger.v1",
  "seq": 0,
  "at": "2026-07-19T03:32:10Z",
  "phase": "triage-seeded",
  "hypotheses": [
    {
      "id": "h1",
      "statement": "Deploy 12 minutes before alert onset touched the request path.",
      "status": "live",
      "provenance": "triage",
      "validation": "VALIDATED",
      "confidence": 0.7,
      "evidence_for": [
        {"url": "https://code.example/commit/abc123", "excerpt": "Changed retry backoff in checkout-api request handler."}
      ]
    },
    {
      "id": "h2",
      "statement": "Recalled memory-pressure pattern from a prior incident.",
      "status": "live",
      "provenance": "recall",
      "validation": "INVALIDATED",
      "confidence": 0.2,
      "evidence_against": [
        {"url": "https://dashboards.example/checkout-api/memory", "excerpt": "Memory usage flat at 40% for the incident window."}
      ]
    }
  ]
}
```

`triage-seeded` is an early phase: only 2 hypotheses is sparse and legal — the
anchoring guard's ≥3-live/≥1-fresh minimum applies only inside the invariant phases
below, never here. What is **not** relaxed by phase: both hypotheses are non-`fresh`
(`triage`, `recall`), and both already carry `validation` — the triage verdict that
seeded this ledger already marked its candidates VALIDATED/INVALIDATED, and seeding
carries that mark forward rather than dropping it. The provenance-and-validation pair
is checked on every hypothesis in every phase; only the ≥3-live/≥1-fresh anchoring
minimum is phase-scoped.

### Valid ledger — invariant phase

<!-- bb-example: valid-ledger-invariant-phase expect=valid -->
```json
{
  "schema": "bb.ledger.v1",
  "seq": 4,
  "at": "2026-07-19T03:41:00Z",
  "phase": "evidence-gathering",
  "hypotheses": [
    {
      "id": "h1",
      "statement": "Deploy 12 minutes before alert onset touched the request path.",
      "status": "live",
      "provenance": "triage",
      "validation": "VALIDATED",
      "confidence": 0.6,
      "evidence_for": [
        {"url": "https://code.example/commit/abc123", "excerpt": "Changed retry backoff in checkout-api request handler."}
      ],
      "evidence_against": []
    },
    {
      "id": "h2",
      "statement": "A dependency's error rate spiked in the same window.",
      "status": "live",
      "provenance": "fresh",
      "confidence": 0.5,
      "evidence_for": [
        {"url": "https://dashboards.example/payments-svc/error-rate", "excerpt": "Error rate rose from 0.2% to 4.1% starting 03:28 UTC."}
      ]
    },
    {
      "id": "h3",
      "statement": "Recalled: this alert matched a known flapping pattern.",
      "status": "live",
      "provenance": "recall",
      "validation": "INVALIDATED",
      "confidence": 0.15,
      "evidence_against": [
        {"url": "https://dashboards.example/checkout-api/alert-history", "excerpt": "No prior occurrence of this alert in the last 90 days."}
      ]
    },
    {
      "id": "h4",
      "statement": "Speculative config-drift theory on the canary; ruled out early.",
      "status": "dead",
      "provenance": "fresh",
      "confidence": 0.1
    }
  ],
  "services_touched": ["checkout-api", "payments-svc"],
  "tool_call_count": 37
}
```

Three `live` hypotheses (`h1`, `h2`, `h3`) satisfy the minimum; `h2` is `live` **and**
`fresh`, satisfying the tunnel-vision guard. `h4` is `fresh` but `dead` — it does not
count toward either invariant, which is exactly the point: a dead fresh hypothesis
does not satisfy `ledger.fresh_required` on its own, so the guard here is genuinely
carried by `h2`, not incidentally by `h4`.

### Invalid ledger — prose-only evidence

<!-- bb-example: invalid-ledger-prose-only-evidence expect=invalid rule=evidence.not_url_excerpt_pair -->
```json
{
  "schema": "bb.ledger.v1",
  "seq": 1,
  "at": "2026-07-19T03:33:00Z",
  "phase": "triage-seeded",
  "hypotheses": [
    {
      "id": "h1",
      "statement": "Fresh read: the alert's error signature matches a known request-path bug.",
      "status": "live",
      "provenance": "fresh",
      "confidence": 0.4,
      "evidence_for": ["saw it in the logs"]
    }
  ]
}
```

A bare string in an evidence list is prose, not a `{url, excerpt}` pair — invalid by
schema regardless of phase or provenance.

### Invalid ledger — invariant phase with only 2 live hypotheses

<!-- bb-example: invalid-ledger-evidence-gathering-two-live expect=invalid rule=ledger.min_live_hypotheses -->
```json
{
  "schema": "bb.ledger.v1",
  "seq": 5,
  "at": "2026-07-19T03:45:00Z",
  "phase": "evidence-gathering",
  "hypotheses": [
    {
      "id": "h1",
      "statement": "Deploy 12 minutes before alert onset touched the request path.",
      "status": "live",
      "provenance": "triage",
      "validation": "VALIDATED",
      "confidence": 0.6,
      "evidence_for": [
        {"url": "https://code.example/commit/abc123", "excerpt": "Changed retry backoff in checkout-api request handler."}
      ]
    },
    {
      "id": "h2",
      "statement": "A dependency's error rate spiked in the same window.",
      "status": "live",
      "provenance": "fresh",
      "confidence": 0.5,
      "evidence_for": [
        {"url": "https://dashboards.example/payments-svc/error-rate", "excerpt": "Error rate rose from 0.2% to 4.1% starting 03:28 UTC."}
      ]
    }
  ]
}
```

Deliberately isolating: one of the two live hypotheses (`h2`) is already `fresh`, so
`ledger.fresh_required` does **not** also fire here — only the live count (2, short of
the minimum 3) is at fault. A construction with 2 live and neither fresh would trip
both anchoring rules at once, which is also legitimate but is not what this example
demonstrates.

### Invalid ledger — 3 live hypotheses, none fresh

<!-- bb-example: invalid-ledger-three-live-none-fresh expect=invalid rule=ledger.fresh_required -->
```json
{
  "schema": "bb.ledger.v1",
  "seq": 6,
  "at": "2026-07-19T03:47:00Z",
  "phase": "evidence-gathering",
  "hypotheses": [
    {
      "id": "h1",
      "statement": "Deploy 12 minutes before alert onset touched the request path.",
      "status": "live",
      "provenance": "triage",
      "validation": "VALIDATED",
      "confidence": 0.6,
      "evidence_for": [
        {"url": "https://code.example/commit/abc123", "excerpt": "Changed retry backoff in checkout-api request handler."}
      ]
    },
    {
      "id": "h2",
      "statement": "Recalled memory-pressure pattern from a prior incident.",
      "status": "live",
      "provenance": "recall",
      "validation": "INVALIDATED",
      "confidence": 0.2,
      "evidence_against": [
        {"url": "https://dashboards.example/checkout-api/memory", "excerpt": "Memory usage flat at 40% for the incident window."}
      ]
    },
    {
      "id": "h3",
      "statement": "Recalled: this alert matched a known flapping pattern.",
      "status": "live",
      "provenance": "recall",
      "validation": "INVALIDATED",
      "confidence": 0.15,
      "evidence_against": [
        {"url": "https://dashboards.example/checkout-api/alert-history", "excerpt": "No prior occurrence of this alert in the last 90 days."}
      ]
    }
  ]
}
```

The live count meets the minimum (3), so `ledger.min_live_hypotheses` does not fire —
but none of the three is `fresh`, so `ledger.fresh_required` fires alone: three
well-validated recalled/triage hypotheses are still tunnel vision without at least one
freshly-generated one in the mix.

### Invalid ledger — unknown phase

<!-- bb-example: invalid-ledger-unknown-phase expect=invalid rule=ledger.unknown_phase -->
```json
{
  "schema": "bb.ledger.v1",
  "seq": 2,
  "at": "2026-07-19T03:35:00Z",
  "phase": "triage-review",
  "hypotheses": []
}
```

`triage-review` is not in the closed phase enumeration — unknown phase values are
always an error, never a guess. `hypotheses: []` on its own is legal (an early-phase
empty ledger); it is the phase value that is invalid here.
