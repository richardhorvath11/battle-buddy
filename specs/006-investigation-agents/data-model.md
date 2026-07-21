# Data Model — Investigation Agents & Skill

The entities this slice documents normatively. Authority note (FR-011, research R9):
the merged slice-2 validator (`bin/bb_validate.py`) is the implementation of record;
these tables state what it enforces in v1. `schemas.md` is the shipped normative doc;
this file is the plan-time extract the tasks build from.

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
| `confidence` | number | no | within [0, 1] |
| `evidence_for` | list | no | each entry per Evidence below |
| `evidence_against` | list | no | each entry per Evidence below |

## Evidence entry (Constitution IV — everywhere evidence appears)

| Field | Type | Required |
|---|---|---|
| `url` | str, non-empty after strip | yes |
| `excerpt` | str, non-empty after strip | yes |

Prose-only evidence (a bare string, or a dict missing/blanking either key) is invalid
by schema — rule `evidence.not_url_excerpt_pair`.

## Phase model and anchoring guard (FR-002)

```
triage-seeded → hypothesis-generation → evidence-gathering → deep-dive → resolution
```

- **Invariant phases** (`evidence-gathering`, `deep-dive`): ≥3 `live` hypotheses
  (`ledger.min_live_hypotheses`) and ≥1 *live* `fresh` (`ledger.fresh_required` —
  a dead fresh hypothesis does not satisfy).
- **Early phases** (`triage-seeded`, `hypothesis-generation`): sparse or empty ledgers
  legal — what makes immediate escalation with no triage verdict lawful.
- **`resolution`**: non-invariant.
- Enforcement: the slice-2 validator at every checkpoint write (Constitution II/VI);
  the skill instructs, the validator verifies.

## Vocabularies (validator constants — the consistency test imports them)

| Vocabulary | Values |
|---|---|
| Provenance | `triage`, `recall`, `fresh` |
| Validation | `VALIDATED`, `INVALIDATED` |
| Phases | `triage-seeded`, `hypothesis-generation`, `evidence-gathering`, `deep-dive`, `resolution` |
| Invariant phases | `evidence-gathering`, `deep-dive` |
| Min live hypotheses | 3 |
| Version tags | `bb.verdict.v1`, `bb.ledger.v1` |

## Violation rules (the names documented-invalid examples cite)

`schema.not_object`, `schema.unknown_version`, `schema.missing_field`,
`schema.wrong_type`, `provenance.unknown`, `validation.unknown_value`,
`memory.unvalidated_non_fresh`, `confidence.out_of_range`,
`evidence.not_url_excerpt_pair`, `ledger.unknown_phase`,
`ledger.min_live_hypotheses`, `ledger.fresh_required`.

## Role registration entry (FR-010; local-state protocol v1 `agents.json`)

```json
{"protocol": "bb.local.v1", "roles": {"<actor-key>": "<role>"}}
```

- `<actor-key>`: the deterministic layer's derived actor identity (hash-suffix of the
  hook payload's transcript path) — the skill never computes it, the spawn flow reads
  it from the layer's own convention.
- `<role>` ∈ `triage` | `deep` | `specialist:<name>` where `<name>` matches
  `[a-z0-9-]+` (the shipped specialists: `log-diver`, `deploy-analyst`,
  `dependency-checker`).
- Write: merge into the existing `roles` map at spawn time; never rewrite other
  entries.
- Mechanism/policy split (Constitution II): identity + enforcement are the
  deterministic layer's; registration is the skill's; unregistered ⇒ uncapped (fail
  open, the protocol's own rule). In v1 only the triage role carries a budget key
  (`budgets.triageTurnCap`, default 15).

## Agent definitions (five prose contracts — pinned properties)

| Definition | Model class | Budget | Toolset (capabilities) | Output |
|---|---|---|---|---|
| `agents/triage.md` | fast/cheap, configurable (D-10 workspace config; no key minted — R3) | ≤2-min wall-clock *target* (measured into `budget_spent`, never enforced); turn cap default 15, key `budgets.triageTurnCap`, enforced by the slice-2 hook | read-only: `alerting`, `code` (catalog + runbook reads), `storage` (session-store reads), `observability` | `bb.verdict.v1`; truncated/no-signal verdict satisfies FR-5f(a) via its own fields |
| `agents/deep-investigator.md` | frontier, configurable | open | wide; every mutation approval-gated; reads capability-named | ledger updates only, to the orchestrator; `bb.ledger.v1` checkpoints via slice-3 conventions + validator gate |
| `agents/log-diver.md` | (inherits dispatch) | bounded by dispatch | read-only, single-purpose | findings summary to deep investigator only; `{url, excerpt}` per finding |
| `agents/deploy-analyst.md` | 〃 | 〃 | 〃 | 〃 |
| `agents/dependency-checker.md` | 〃 | 〃 | 〃 | 〃 |

Findings summaries are working input, not a persisted schema in v1 (spec assumption) —
they become ledger evidence entries on merge.
