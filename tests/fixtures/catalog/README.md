# Fixture catalog repo

`repo/` is a hermetic stand-in for a team's real Backstage catalog repo (slice 7, catalog
adapter — `specs/007-catalog-adapter/`). It exists so the catalog skill's documented parsing
and resolution rules can be gated by hermetic tests via a dev-only reference encoding
(`tests/helpers/catalog_reference.py`), with no live git, no credentials, no network.

## Format decision (research R2)

> Files are named `catalog-info.yaml` and written in **strict JSON syntax** —
> double-quoted keys and string scalars, a space after every `:`, no comments, no trailing
> commas — which is simultaneously valid YAML 1.2 flow style AND directly parseable by
> stdlib `json`. That is what lets the dev-only reference encoding parse them with no YAML
> dependency and no CI change.
>
> Do NOT write "YAML flow style" as the instruction: it is strictly broader than JSON and
> admits `{kind: Component}` (unquoted), which `json.load` rejects. The space-after-colon
> rule is also deliberate — YAML 1.1 parsers (PyYAML) reject `{"a":1}`.
>
> Residual gap, stated honestly: YAML-syntax-specific failure modes (tab indentation,
> anchors/aliases, block-scalar folding, duplicate keys) are NOT exercised by these
> fixtures. That gap is scenario-harness territory, not CI.

In practice this means every `catalog-info.yaml` under `repo/services/**` is pretty-printed
JSON (`json.dumps(obj, indent=2)`) — parse them with `json.load`, never a YAML library.

## Layout

```
tests/fixtures/catalog/
  README.md                        # this file
  repo/
    services/<dir>/catalog-info.yaml  # 11 fixture entities, one per directory
```

`repo/` is the root passed to the catalog loader in tests (`fixture_path("catalog", "repo")`);
every `source_path` a parsed entity carries is relative to `repo/`, e.g.
`services/checkout/catalog-info.yaml`.

## Annotation keys

Only these five annotation keys appear anywhere in the fixtures — the literal vocabulary the
catalog skill's annotation mapping documents:

| Annotation key | Meaning | Value shape |
|---|---|---|
| `oncall-harness/alert-match` | alert matchers | JSON list of strings |
| `oncall-harness/runbooks` | runbooks | JSON list of URL strings |
| `grafana/dashboard-selector` | dashboards | JSON list of URL strings |
| `pagerduty.com/service-id` | paging linkage | string |
| `github.com/project-slug` | repo linkage | string |

## Fixture service roster — 11 entities, 8 parsed services

| dir | `metadata.name` | `spec.owner` | alert-match | dashboards | runbooks | dependsOn | linkage | what it's for |
|---|---|---|---|---|---|---|---|---|
| `checkout` | `checkout` | `team-checkout` | `["checkout-5xx", "shared-tag"]` | 1 url | 1 url | `["inventory"]` | pagerduty + github | fully annotated baseline; shares the `shared-tag` matcher with `zz-billing` |
| `payments-api` | `payments-api` | `team-payments` | ABSENT | ABSENT | ABSENT | ABSENT | ABSENT | minimal viable subset (`kind` + `metadata.name` + `spec.owner`) and nothing else — parses to four empty lists |
| `inventory` | `inventory` | `team-inventory` | `["inventory-lag"]` | **ABSENT** | 1 url | `["ledger-svc"]` | none | single-omission: no dashboards → no pane driving, one disabled feature |
| `notifier` | `notifier` | `team-notify` | **ABSENT** | 1 url | 1 url | `["checkout"]` | none | single-omission: no alert-match → ask-once + fix-up path |
| `ledger-svc` | `ledger-svc` | `team-ledger` | `["ledger-write-fail"]` | 1 url | **ABSENT** | `["payments-api"]` | none | single-omission: no runbooks → noted absence |
| `search-api` | `search-api` | `team-search` | `["search-latency"]` | 1 url | 1 url | **ABSENT** | none | single-omission: no dependsOn → no blast-radius widening |
| `zz-billing` | `billing` | `team-billing` | `["billing-lag", "shared-tag"]` | 1 url | 1 url | `["nonexistent-svc"]` | none | directory name and service name sort in opposite order vs. `checkout` (load-bearing for the multi-exact candidate-ordering test); depends on an uncatalogued service (dangling-dependency surfacing) |
| `orders-eu` | `orders` | `team-orders-eu` | `["orders-queue"]` | 1 url | 1 url | `["checkout"]` | none | duplicate-name pair — wins: first in lexicographic source-path order |
| `orders-us` | `orders` | `team-orders-us` | `["orders-queue-us"]` | 1 url | 1 url | `["checkout"]` | none | duplicate-name pair — loses; a `duplicate_name` warning names both source paths |
| `docs-site` | `docs-site` | `team-docs` | ABSENT | ABSENT | ABSENT | ABSENT | none | `kind: "Documentation"`, not `Component` — a non-service entity, ignored with a warning, never parsed into the model |
| `broken` | — | — | — | — | — | — | — | truncated flow mapping (`{"apiVersion": ..., "metadata": {` with no closing braces) — invalid as both JSON and YAML; exercises file-scoped failure isolation |

**Every other entity** (`checkout`, `inventory`, `notifier`, `ledger-svc`, `search-api`,
`zz-billing`, `orders-eu`, `orders-us`) has `kind: "Component"`.

**Counts**: 11 entities on disk → **8 parsed services** — `checkout`, `payments-api`,
`inventory`, `notifier`, `ledger-svc`, `search-api`, `billing` (from `zz-billing`), `orders`
(from `orders-eu`, the duplicate winner). `docs-site` is ignored (non-service `kind`),
`broken` fails to parse (file-scoped failure), and `orders-us` loses the duplicate-name
tie-break — three of the eleven entities that never make it into the parsed model.

Each single-omission fixture (`inventory`, `notifier`, `ledger-svc`, `search-api`) carries
**all three** of the other annotation classes plus a non-empty `dependsOn`, so it degrades
exactly one feature and no others.
