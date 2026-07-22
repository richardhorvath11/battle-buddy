# Data Model: Catalog Adapter (slice 7)

The shapes this slice pins. Every one of them exists in three places that must agree, and
the contract tests are what make them agree: the **skill prose** (normative, shipped), the
**reference encoding** (`tests/helpers/catalog_reference.py`, dev-only), and the **fixture
catalog** (`tests/fixtures/catalog/`).

---

## 1. `Service` — the internal service model (FR-001, design §6.1)

The adapter's entire public surface. Six fields, no more; raw catalog structure never
crosses this boundary.

| Field | Type | Source | Absent-annotation default |
|---|---|---|---|
| `name` | str, non-empty | `metadata.name` | — (required; an entity without it is not a service) |
| `owner` | str | `spec.owner` | `""` + a `missing_owner` warning |
| `runbooks` | list[str] | `oncall-harness/runbooks` | `[]` |
| `dashboards` | list[str] | `grafana/dashboard-selector` | `[]` |
| `alert_matchers` | list[str] | `oncall-harness/alert-match` | `[]` |
| `depends_on` | list[str] | `spec.dependsOn` | `[]` |

**Empty list, never null, never absent**: a consumer never branches on presence — it
branches on emptiness, which is what makes per-field degradation (FR-004) uniform.

**`owner` is part of PRD FR-13's minimal viable subset**, so its absence is a catalog-quality
problem rather than an ordinary degradation: the field defaults to `""` (parsing never fails)
*and* a `missing_owner` warning is emitted, so a service nobody owns can never parse clean and
silent. It is deliberately **not** in the `disabled_features` map (§6) — that map is the
per-field *feature* degradation FR-004 enumerates, and ownership disables no feature.

**Multi-valued annotation parsing**: `runbooks`, `dashboards`, and `alert_matchers` accept
either a single scalar string or a list; a scalar parses to a one-element list. Comma
separation inside a scalar is **not** split — a comma is a legal character in a matcher, and
silently splitting one would make the vocabulary ambiguous. `spec.dependsOn` is a list in
Backstage and parses as one (a scalar there parses to a one-element list too).

---

## 2. Linkage metadata — not a `Service` field (FR-002, D-22)

| Key | Internal name | Purpose |
|---|---|---|
| `pagerduty.com/service-id` | `paging_id` | paging linkage |
| `github.com/project-slug` | `repo_slug` | repo scoping for deploy-window reads |

These parse into a per-service `linkage` map exposed on the `Catalog` (§3), **beside** the
`Service` model and never inside it. That is the whole of the claim: linkage is not a field of
the six-field consumer model, which is what resolves the design's two dangling mapping-table
rows. The slices that need these values — deploy-window scoping, paging — read them off
`catalog["linkage"]`.

**Correction recorded** (converge round 1, review lens A finding 6): an earlier draft claimed
consumers "never receive the linkage values themselves," citing design §4's
`deploy window check (service + dependsOn)` arrow. That citation does not support the claim —
in `bb-session-sequence.mermaid` the arrow targets `CAT`, declared as the *code capability's
MCP* (the same participant serving catalog reads), not the catalog adapter surface. The claim
was also self-contradictory, since `catalog["linkage"]` is on the returned object. Both the
overclaim and the citation are dropped here and must not reappear in D-22's text.

---

## 3. `Catalog` — the parse result over a repo tree

```
Catalog {
  services:  {name -> Service}        # canonical, duplicate-resolved
  linkage:   {name -> {paging_id?, repo_slug?}}
  sources:   {name -> source_path}    # the winning entity's path (see relativity rule below)
  warnings:  [Warning]                # catalog-quality, non-fatal
  failures:  [Failure]                # per-file, non-fatal
}
```

`Warning {kind, service, detail, sources[]}` — `kind` ∈ `duplicate_name` | `ignored_entity` |
`missing_owner` | `dangling_dependency`.

`Failure {source_path, reason}` — one entry per file that could not be parsed.

**Nothing here is an error path.** A `Catalog` is always returned; FR-004's "no partial
annotation ever errors a session" and the malformed-file isolation rule are the same
property expressed at field and file scope.

### `source_path` relativity (pinned)

`load_catalog(repo_root)` is called with the **repo root itself** — in tests,
`fixture_path("catalog", "repo")`. Every `source_path` is relative to that root, so the
canonical `orders` entity's path is `services/orders-eu/catalog-info.yaml`, never
`repo/services/…` and never absolute. Lexicographic ordering (below) is applied to exactly
this string.

### Entity classification (edge case: non-service entities)

An entity is service-shaped when `kind` ∈ {`Component`, `Service`} **and** `metadata.name`
is a non-empty string. Anything else is skipped with an `ignored_entity` warning — never
parsed into the model, never a failure.

### Duplicate `metadata.name` (spec-pinned)

All service-shaped entities are collected, then grouped by `name`. When a group has more
than one member, the entity whose **repo-relative source path sorts first lexicographically**
becomes canonical; every other member is dropped and one `duplicate_name` warning is emitted
naming all source paths. Deterministic by construction — no dependence on directory-walk
order.

### Warning provenance across duplicate resolution (pinned)

Warnings are collected per *file*, before duplicate resolution runs, so a
`duplicate_name` loser's own warnings (e.g. a `missing_owner` on `orders-us`) stay in the
catalog's `warnings` list even though its entity was dropped. That is deliberate: the
warning stream is a record of catalog *quality*, and a quality problem in a file that lost a
tie-break is still a problem in the team's repo — the fix-up path is the correction vehicle
for both. Consumers reading the stream must therefore treat `warning["service"]` as "the
name the offending entity declared", not "a key into `catalog["services"]`".

### Dangling `dependsOn` (surfaced, never dropped)

A `depends_on` entry naming a service absent from the catalog is **kept** — FR-006 authorizes
no filtering, and on the messy-catalog team this slice targets (D-19) a dependency on an
uncatalogued service is the normal case, not an anomaly. It is surfaced with one
`dangling_dependency` warning per (service, missing name). Silently shrinking a blast radius
would be the opposite of this slice's stated posture: quality problems are surfaced, not
fatal, and never invisible.

---

## 4. `Alert` — the resolution input

```
Alert { alert_id, tags: [str], fields: {str -> str} }
```

`fields` is the flat field map the alerting capability yields (`name`, `service_hint`,
`description`, … — design §7.1's `get_alert` output). Missing or empty fields are
non-matching, never a crash (edge case: sparse alerts). This slice does not define the
alerting capability's shape; it consumes it.

---

## 5. `Resolution` — the resolution output (FR-003)

```
Resolution { outcome, service?, candidates[], stage? }
```

| `outcome` | Meaning | `service` | `candidates` |
|---|---|---|---|
| `exact` | one service matched at the exact stage | the service name | `[]` |
| `substring` | no exact match; one service matched at the substring stage | the service name | `[]` |
| `ambiguous` | >1 service matched at whichever stage matched first | absent | ≥2, source-path sorted |
| `miss` | nothing matched at either stage | absent | `[]` |

`stage` records which stage produced the outcome (`exact` \| `substring`), present on
`exact`, `substring`, and `ambiguous`. **`service` and every `candidates` element is a
service-name string**, never a nested object — consumers index `catalog["services"]` and
`catalog["sources"]` with it.

### Match order (FR-003, design §6.1)

1. **Exact stage — `alert_matchers` only.** For every service, for every entry in
   `alert_matchers`: a hit when the matcher string equals — case-insensitively,
   whitespace-trimmed — any of the alert's tags or any of the alert's field *values*.
   FR-003's "exact **tag/name** matching" is exactly this: the *alert's* tag or the *alert's*
   name-bearing field, compared to a matcher. The **service's own `name` is not an
   exact-stage input** — the design's "then substring on service name" makes the service name
   the substring stage's input, and only that. A service with empty `alert_matchers`
   therefore cannot match at the exact stage at all, which is FR-004's missing-alert-match
   degradation.

   *Consequence worth stating, because a test can silently invert on it*: a matcher-less
   service is unresolvable at the exact stage, but the substring stage may still resolve it
   when the alert happens to spell its name. US3 AS-2's "no alert-match ⇒ ask-once path"
   claim is therefore about the *matcher* path; an alert that names the service in a field
   legitimately resolves by substring. The AS-2 fixture alert must not contain the service's
   name, or it asserts the opposite of what it reads.

2. **Substring stage — only if the exact stage matched nothing.** For every service: a hit
   when the **service's `name`** occurs as a substring of any alert tag or field value
   (case-insensitive). **Direction is pinned** (spec Assumptions): name-inside-alert-field,
   never alert-field-inside-name.

3. **Multi-match at whichever stage matched** → `ambiguous`, all candidates surfaced. Never
   a silent pick, at either stage.

4. **Nothing at either stage** → `miss` → ask-once (slice 5 executes) → fingerprint ladder
   rung 2 → fix-up offer (§7 below).

Exactness beats substring **globally**, not per-service: a single exact hit anywhere
prevents the substring stage from running at all.

---

## 6. Degradation map (FR-004, US3)

Derived per service, purely from empty-vs-populated fields — the mechanical form of
"each missing annotation degrades exactly its own feature."

| Empty field | Disabled feature | Everything else |
|---|---|---|
| `dashboards` | `pane_driving` | unaffected — briefing still works |
| `alert_matchers` | `alert_resolution` | routes to ask-once + fix-up, same as a miss |
| `runbooks` | `runbook_fetch` | absence is noted in the briefing |
| `depends_on` | `blast_radius_widening` | assessment proceeds unwidened |

A malformed file disables **nothing globally**: it contributes a `Failure` entry, the
service it would have defined is simply absent, and every other file parses normally.

---

## 7. Fix-up offer (FR-003, R12)

The content the skill defines for the miss path — a ready-to-commit annotation snippet, not
an action. Signature is pinned so the test can assert literals:

```
fixup_offer(alert, service_name, catalog)
  -> Fixup { source_path, annotation_key, annotation_value, snippet }
```

- `annotation_key` is always `oncall-harness/alert-match`.
- `annotation_value` is the alert's **discriminating field**, resolved by a pinned order:
  `alert["fields"]["name"]` if non-empty, else `alert["fields"]["service_hint"]` if non-empty,
  else the first entry of `alert["tags"]`, else `""`. Deterministic, not a judgment call.
- `source_path` is `catalog["sources"][service_name]` when the responder-named service is
  already in the catalog; when it is absent entirely, the **conventional path for a new
  entity**, pinned as `services/<service_name>/catalog-info.yaml` (relative to the repo root,
  §3's relativity rule).
- `snippet` is the paste-ready annotation block containing the key and value.

The responder commits it. **No agent writes to the catalog** — it is human-curated,
PR-reviewed data (design §2 division of knowledge, Constitution I).

---

## 8. Runbook reference (FR-005, R11)

```
RunbookRef { url, commit? }
```

Destined for slice 3's `runbook_refs` session-row column. `commit` is the SHA the runbook
was read at, present where git-hosted, absent otherwise. **Never content** — the row carries
a pointer with a version, and the catalog itself is never copied into any store.

---

## 9. Blast radius (FR-006)

```
blast_radius(name, catalog) -> [service names]
```

The service's own `depends_on` entries, **one hop, no recursion**, sorted — and
**unfiltered**: entries naming services absent from the catalog are returned too, having
already been surfaced as `dangling_dependency` warnings at load time (§3). An absent or
empty `depends_on` yields `[]` — the assessment proceeds unwidened. Depth is stated
explicitly in the prose and pinned by a two-hop fixture chain whose second hop must be
absent from the result.

---

## 10. Fixture catalog surfaces (`tests/fixtures/catalog/`)

| Path | Role |
|---|---|
| `README.md` | records the R2 format decision (strict JSON syntax = valid YAML 1.2 flow style) |
| `repo/services/<svc>/catalog-info.yaml` | the fixture team catalog repo |
| `golden-models.json` | expected `Service` model + linkage + degradation per service (US2, SC-002) |
| `resolution-matrix.json` | fixture alerts with expected `Resolution` per case (US1, SC-003) |

### Fixture service roster — 11 entities, 8 parsed services

Every single-omission fixture carries **all three** other annotation classes plus a non-empty
`spec.dependsOn`, so its `disabled_features` set is a singleton. Values are pinned here
because the resolution matrix indexes into them.

| Service dir | `metadata.name` | matchers | dashboards | runbooks | dependsOn | Shape exercised |
|---|---|---|---|---|---|---|
| `checkout` | `checkout` | `checkout-5xx`, `shared-tag` | ✓ | ✓ | `["inventory"]` | fully annotated + both linkage keys |
| `payments-api` | `payments-api` | — | — | — | — | minimal subset (`kind`+`name`+`owner`) and nothing else |
| `inventory` | `inventory` | `inventory-lag` | **—** | ✓ | `["ledger-svc"]` | no dashboards |
| `notifier` | `notifier` | **—** | ✓ | ✓ | `["checkout"]` | no alert-match |
| `ledger-svc` | `ledger-svc` | `ledger-write-fail` | ✓ | **—** | `["payments-api"]` | no runbooks |
| `search-api` | `search-api` | `search-latency` | ✓ | ✓ | **—** | no dependsOn |
| `zz-billing` | `billing` | `billing-lag`, `shared-tag` | ✓ | ✓ | `["nonexistent-svc"]` | **sort inversion** + dangling dependency |
| `orders-eu` | `orders` | `orders-queue` | ✓ | ✓ | `["checkout"]` | duplicate pair — lexicographically first, wins |
| `orders-us` | `orders` | `orders-queue-us` | ✓ | ✓ | `["checkout"]` | duplicate pair — loses, warning emitted |
| `docs-site` | `docs-site` | — | — | — | — | `kind: Documentation` — non-service, ignored |
| `broken` | — | — | — | — | — | truncated flow mapping — unparseable, file-scoped `Failure` |

**Parsed service count is eight**: 11 entities − `docs-site` (ignored) − `broken` (failed) −
`orders-us` (duplicate loser).

**Two-hop chain**: `checkout` → `inventory` → `ledger-svc`. It deliberately does **not** run
through `payments-api`, which must stay at the minimal subset so US2 AS-2's four-empty-lists
assertion means what it says.

**Why `zz-billing` exists**: it is the only pair in the roster whose directory name and
service name sort in *opposite* order against another candidate — path `services/checkout` <
`services/zz-billing`, but name `billing` < `checkout`. Both carry the `shared-tag` matcher,
so the multi-exact case's expected candidate order (`["checkout", "billing"]`) is achievable
only by an implementation that really sorts by source path. Without it, a name-sorting
implementation would pass every case and §5's ordering pin would be untested.

### Resolution matrix cases

Nine cases minimum; each `{id, alert, expected}`.

| Case | Alert (abbrev.) | Expectation |
|---|---|---|
| exact-tag hit | tags `["checkout-5xx"]` | `exact` / `checkout` |
| exact-name hit | fields `{name: "inventory-lag"}` | `exact` / `inventory` — the alert's name field equals a matcher |
| substring hit | fields `{name: "elevated latency on search-api requests"}` | `substring` / `search-api` |
| exact beats substring | tags `["checkout-5xx"]` + fields `{description: "impacting search-api"}` | `exact` / `checkout`, `candidates == []` — **two different services**, so a stage-merging implementation would return `ambiguous` and fail |
| multi-exact | tags `["shared-tag"]` | `ambiguous`, candidates `["checkout", "billing"]` — source-path order, which inverts name order |
| multi-substring | fields `{description: "ledger-svc talking to search-api timed out"}` | `ambiguous`, candidates `["ledger-svc", "search-api"]` |
| miss | tags `["disk-pressure"]`, fields `{name: "node-9 disk pressure"}` | `miss` |
| sparse alert | tags `[]`, fields `{name: ""}` | `miss`, no exception |
| reverse-direction probe | fields `{name: "ledger"}` | `miss` — `ledger` is a strict substring of `ledger-svc`, so a reversed implementation resolves it and fails here |

### `golden-models.json` structure (pinned — T006 and T007 are parallel)

```json
{
  "checkout": {
    "model":             { "name": "...", "owner": "...", "runbooks": [], "dashboards": [],
                           "alert_matchers": [], "depends_on": [] },
    "linkage":           { "paging_id": "...", "repo_slug": "..." },
    "disabled_features": [],
    "source_path":       "services/checkout/catalog-info.yaml"
  }
}
```

Only the `model` sub-object is compared field-for-field against a parsed `Service` (whose key
set must be exactly the six model fields). `disabled_features` is a JSON **list**; every
set-equality assertion coerces it with `set(...)`.
