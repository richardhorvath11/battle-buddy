# Session-Store Fingerprint Reference

Normative for the `session-store` skill (FR-003; design §5.2, D-4, D-19). This is the
documented statement of the `bb.fp.v1` fingerprint rules — the shared retrieval key that
carries the load embeddings would otherwise carry (`references/retrieval.md`, §5.5). The
**normative implementation** is `bin/bb-fingerprint` / `bin/bb_fingerprint.py`; this
document restates its rules in the same order so the two can never diverge silently, and
`tests/fixtures/fingerprint/golden.json` is their **executable form**. A contract test
ties all three together (research R6) — see "Roles" and "Worked examples" below.

## Version

**`bb.fp.v1`** — this document's version tag MUST equal `bb_fingerprint.VERSION` and the
golden corpus's `version` field (`tests/contract/test_fingerprint_reference.py` enforces
this). **Any change to a normalization rule, the resolution ladder, or the construction
formula REQUIRES a version bump plus a documented re-fingerprint pass** over every stored
session row — a silent rule change would collide or split fingerprints without warning,
breaking stage-1 exact-match recall (`references/retrieval.md`) with nothing surfacing
the drift.

## Construction

```
fingerprint = hex(sha256(normalize(service) + "|" + normalize(alert_type)))[:16]
```

16 lowercase hex characters. `normalize()` applies a different rule set depending on which
side of the formula it normalizes — `service` gets rule 1 only; `alert_type` gets rules 1
and 2 — in this exact order (matches `bin/bb_fingerprint.py`'s rule order):

1. **Both inputs** — lowercase; trim; collapse internal whitespace to single spaces.
2. **`alert_type` only**, in this order (earlier rules win — a span already replaced by an
   earlier rule is never reconsidered by a later one):
   1. UUIDs → `<id>`
   2. ISO timestamps (date-time or bare date) → `<ts>`
   3. IPv4 addresses → `<host>`
   4. Dotted hostnames (≥3 labels) → `<host>`
   5. Hex strings ≥8 characters containing ≥1 letter → `<id>`
   6. Integers ≥3 digits → `<n>`
3. **`service` only** — the catalog `metadata.name` is already canonical; only rule 1
   applies. Digits in a service name are identity, never volatile — `payments-v2` never
   collapses to `payments-<n>`.

Empty or all-volatile inputs still produce a deterministic 16-hex output — **never an
exception** — flagged (`empty_service`, `empty_alert_type`, `all_volatile_alert_type`) so
callers can apply the resolution ladder below rather than trusting a degenerate match.

## Service-resolution ladder

The fingerprint always uses the **best available service name — never a shared
sentinel**. A shared placeholder like `unknown` would collide every unresolved service
into one bucket, which is worse than missing the match entirely: it manufactures false
"known issue" hits across genuinely distinct services.

| Rung | Source | `catalog_resolved` |
|---|---|---|
| 1 | Catalog match (`metadata.name`) | `true` |
| 2 | Responder-provided name (asked once when catalog resolution fails; normalized like any service name) | `false` |
| 3 | The alert's own service/team tag from the alerting tool | `false` |
| 4 | Nothing names a service at all | `false` |

Rungs 2–4 set `catalog_resolved: false` on the row. Retrieval (`references/retrieval.md`,
stage 1) downgrades an exact-fingerprint match from "near-certain known issue" to
"candidate" whenever **either row in the match** — the incoming session (whose own
`catalog_resolved` was set by whichever rung resolved *its* service name, before the row
is even appended) or the matched stored row — carries `catalog_resolved: false`. The flag
travels with the row precisely so a later match can honor it; checking only the stored
side would miss the incoming session's own unresolved-catalog case.

**Rung 4** — when nothing names a service at all, the fingerprint's `service` side is
`normalize(alert_source + rule_name)`: the alerting tool's source identifier concatenated
directly with its rule name (no separator), then run through rule 1 only — the same
normalization any other service string gets. This gives per-alert-rule granularity that
stays collision-free across services even with no service name at all.

## Roles

- **`bin/bb-fingerprint` / `bin/bb_fingerprint.py`** — the one shared implementation
  (design D-4). Triage, close, and any future tier-1 ingestion call this same code so
  fingerprints are byte-identical everywhere; this document's normative claim is only as
  good as its agreement with the code, which is why the consistency check below exists.
  `fingerprint(service, alert_type)` returns
  `{version, fingerprint, service_normalized, alert_type_normalized, flags}`; the CLI
  (`bb-fingerprint SERVICE ALERT_TYPE`) prints the same record as JSON.
- **`tests/fixtures/fingerprint/golden.json`** — the executable form of the rules above:
  every documented normalization behavior (case/whitespace collapse, each volatile-token
  substitution, rule precedence, empty/degenerate inputs, identical/distinct pairs) as a
  concrete input/output case, run against the real helper by `tests/unit/test_fingerprint.py`.

## Worked examples

One catalog-resolved case (rung 1) and one rung-4 case (no service resolved at all — the
`service` side is `alert_source + rule_name`). Machine-readable line format:

```
service=<service side> | alert_type=<alert_type side> -> <16 lowercase hex chars>
```

```
# catalog-resolved (rung 1) — service name came straight from the catalog
service=checkout-api | alert_type=High latency on pod-7f9c2 at 2026-07-20T03:14:15Z -> 6c2786b4a671cdc3

# rung 4 — no service resolved at all; service side = normalize(alert_source + rule_name)
# alert_source="datadog", rule_name="high-cpu-utilization" concatenated, no separator
service=datadoghigh-cpu-utilization | alert_type=CPU pinned at 97 percent -> 180554279c7a4afb
```

`tests/contract/test_fingerprint_reference.py` parses every `service=... | alert_type=...
-> ...` line above and recomputes it through `bb_fingerprint.fingerprint(service,
alert_type)`; a doc example that doesn't match the real helper's output fails the gate
(research R6).
