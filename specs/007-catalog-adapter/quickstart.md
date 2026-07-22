# Quickstart & Validation: Catalog Adapter (slice 7)

How to run this slice's gates, what each one proves, and — stated plainly — what none of
them prove.

## Prerequisites

Python 3.12 with `pytest` (the contract layer's only dependency; this slice adds none).
No credentials, no network, no live git — every catalog read under test hits fixture files.

## Run

```bash
make verify                                        # THE gate: both hermetic layers
make test-contract                                 # this slice's layer alone
pytest tests/contract/test_catalog_model.py -q      # one module
pytest tests/contract/test_catalog_resolution.py -q
pytest tests/contract/test_catalog_degradation.py -q
pytest tests/contract/test_catalog_prose.py -q
```

Expected: green, with the new modules collected. `make verify` must be green before any
task is described as done (Constitution VIII).

## Validation scenarios

Each row is a spec acceptance scenario or success criterion, the artifact it asserts on, and
where it runs. Every assertion is on a **parsed artifact** — a model, an outcome record, a
warning list, a scan result — never on prose opinion.

### US1 — A firing alert finds its service (P1)

| Scenario | Asserted artifact | Module |
|---|---|---|
| AS-1: exact tag match wins | `Resolution.outcome == "exact"`, `stage == "exact"`, named service | `test_catalog_resolution.py` |
| AS-2: substring resolves when no exact hit | `outcome == "substring"`, named service | `test_catalog_resolution.py` |
| AS-3: miss reaches ask-once + fix-up | `outcome == "miss"`; `fixup_offer()` returns the `oncall-harness/alert-match` snippet with the responder's answer and a target source path | `test_catalog_resolution.py` |
| AS-4: multi-exact surfaces candidates | `outcome == "ambiguous"`, ≥2 source-path-sorted candidates, `service` absent | `test_catalog_resolution.py` |
| Multi-substring surfaces candidates | `outcome == "ambiguous"`, `["ledger-svc", "search-api"]` | `test_catalog_resolution.py` |
| Exact beats substring **globally** | `outcome == "exact"`, `stage == "exact"`, `candidates == []`, on an alert whose exact and substring candidates are **different services** (a stage-merging implementation returns `ambiguous`). Note: "the substring stage never runs" is not observable from `Resolution` — this is the assertable form | `test_catalog_resolution.py` |
| Candidates are source-path ordered | multi-exact returns `["checkout", "billing"]` **in order** — path order inverts name order for that pair, so a name-sorting implementation fails | `test_catalog_resolution.py` |
| Substring direction pinned | reverse-direction probe (`"ledger"`, a strict substring of `ledger-svc`) resolves `miss` | `test_catalog_resolution.py` |
| Edge: sparse alert | empty/absent fields → `miss`, no exception | `test_catalog_resolution.py` |
| Edge: duplicate `metadata.name` | lexicographically-first source path canonical; one `duplicate_name` warning naming both paths | `test_catalog_model.py` (a parse-time property) |
| **SC-003** | every `resolution-matrix.json` case classifies exactly as expected; zero cases return a service on an ambiguous outcome; `len(CASES) >= 9` | `test_catalog_resolution.py` |

### US2 — One service shape for the whole system (P1)

| Scenario | Asserted artifact | Module |
|---|---|---|
| AS-1: fully annotated service | every model field equals its `golden-models.json` value | `test_catalog_model.py` |
| AS-2: minimal subset sufficient | `kind`+`name`+`owner` only → valid model, empty lists for the four absent fields | `test_catalog_model.py` |
| AS-3: no raw catalog structure escapes | parsed `Service` keys are **exactly** the six model fields; linkage lives outside the model | `test_catalog_model.py` |
| Edge: non-service entities ignored | `kind: Documentation` → absent from `services`, present as an `ignored_entity` warning | `test_catalog_model.py` |
| Catalog-quality warnings surface | `zz-billing` yields a `dangling_dependency` warning naming `nonexistent-svc`; the `missing_owner` vocabulary exists and fires on nothing in this roster | `test_catalog_model.py` |
| **SC-002** | 100% of fixture services match their golden `model` sub-objects field-for-field, empty-list defaults included; the golden set is non-empty and its key set equals the parsed service set (non-vanishing guard) | `test_catalog_model.py` |

### US3 — Partial catalogs degrade, never error (P2)

| Scenario | Asserted artifact | Module |
|---|---|---|
| AS-1: no dashboards | `disabled_features` == `{pane_driving}` only; the rest of the model intact | `test_catalog_degradation.py` |
| AS-2: no alert-match | `alert_resolution` disabled; an alert for that service resolves `miss` (same path as a resolution miss) — the fixture alert must not spell the service's name, or the substring stage legitimately resolves it (data-model.md §5) | `test_catalog_degradation.py` |
| FR-004: no runbooks | `disabled_features` == `{runbook_fetch}` only; the absence is what the briefing notes | `test_catalog_degradation.py` |
| AS-3: one malformed file among many | exactly one `Failure` naming that source path; every other fixture service still parses | `test_catalog_degradation.py` |
| AS-4: `dependsOn` widens | `blast_radius()` returns the direct dependency; absent `dependsOn` returns `[]` | `test_catalog_degradation.py` |
| **FR-006 depth bound** | the two-hop fixture chain's second hop is **absent** from the result | `test_catalog_degradation.py` |
| FR-006 dangling entries | `blast_radius("billing")` returns `["nonexistent-svc"]` — kept and surfaced at load time, never filtered out of the blast radius | `test_catalog_degradation.py` |
| **SC-004** | every degradation fixture produces exactly its documented disabled feature and no other, asserted against **literal sets** rather than the hand-authored goldens (a golden compared to the encoding that shaped it is self-consistently green); the malformed file blocks nothing | `test_catalog_degradation.py` |

### US4 — Always fresh, never copied (P2)

| Scenario | Asserted artifact | Module |
|---|---|---|
| AS-1: read flow is session-start + capability-scoped, persisted nowhere | prose gate: the freshness statement is present; **SC-006** scan finds zero `append_record`/`update_record`/`put_file`/`append_entry` anywhere in `skills/catalog/**` | `test_catalog_prose.py` |
| AS-2: runbook reference is URL + commit SHA | prose gate: the `{url, commit}` pointer format is stated and the never-content rule with it | `test_catalog_prose.py` |
| Edge: catalog repo unreachable | prose gate: the statement that the fingerprint ladder's lower rungs carry the session and nothing blocks the open is present | `test_catalog_prose.py` |

### Cross-cutting gates

| Criterion | Asserted artifact | Module |
|---|---|---|
| **SC-005** | zero concrete MCP server/tool names in `skills/catalog/**` — `mcp__` on raw text; `DENY_PATTERNS` (imported from slice 3's module) on prose with canonical **whole** annotation keys masked | `test_catalog_prose.py` |
| SC-005 positive control | the canonical keys are actually present (the mask has something to mask) **and** all three vendor words do not survive masking — both halves pinned, mirroring slice 3's fenced-`datadog` test. Slice 3's `DENY_PATTERNS` has no `github` entry, so the scan adds one locally; without it the `github.com/project-slug` third of the control would be vacuous | `test_catalog_prose.py` |
| **FR-007** | the **literal** phrase `your code tool's file reads` is present (an unpinned "generic phrasing" gate would be a tautology), and none of `read_file` / `list_commits` / `search` is cited — enumerated, because slice 3's suffix heuristic would catch only the first. Backstop scoped to that token set: any of the three appearing must exist in `manifest/capabilities.json`'s `optional.code.ops` | `test_catalog_prose.py` |
| **FR-009** | `skills/catalog/` contains no `*.py` file, and `tests/helpers/catalog_reference.py` is named by no glob in the declared bundle — prose and tests only, mechanically | `test_catalog_prose.py` |
| Prose↔encoding agreement | the annotation table parsed out of `references/annotations.md` equals the reference encoding's canonical vocabulary — the slice-3 `fingerprint.md`↔`bb-fingerprint` relationship, applied here | `test_catalog_prose.py` |
| Doctor-fixture ratchet | `tests/fixtures/doctor/catalog-valid.json`'s annotation keys ⊆ the canonical set (research R4), **with a non-vanishing guard** — a bare subset assertion passes on the empty set, which is how a wrong key-path extractor would silently neuter the ratchet | `test_catalog_prose.py` |
| **SC-001** | every FR — FR-001 through FR-009, none excepted — maps to ≥1 passing test in the tables above; the suite is green on every commit via `make verify` | all four modules |

## What these gates do **not** prove

Stated deliberately, because the spec makes it a scope boundary rather than an omission:

- **They do not prove a live agent follows the prose.** CI gates the documented *rules'*
  coherence through a dev-only reference encoding. Whether a model reading `SKILL.md`
  actually resolves an alert the documented way is the design §10 **scenario harness's**
  job — the on-demand layer, not CI. The reference-encoding-vs-agent seam is exactly what
  that harness exists to catch.
- **They do not prove YAML syntax handling.** Fixtures are written in strict JSON syntax — a
  subset of YAML 1.2 flow style — so the reference encoding parses them with stdlib `json`
  (research R2). Block-style quirks (tabs, anchors, folded scalars, duplicate keys) and
  unquoted flow scalars are not exercised here.
- **They do not prove the prose-only rules.** Four documented rules have a *statement* gate
  but no behavior gate: the catalog-unreachable path, "no agent ever writes to the catalog",
  FR-001's no-raw-structure property as it binds the shipped prose (the key-set assertion runs
  against the dev encoding), and agent compliance generally. Named here rather than counted as
  enforcement.
- **They do not prove anything about a real catalog repo.** No live git, no network. The
  fixture is the contract's stand-in, and its fidelity is a plan-time claim (research R1/R2),
  not a tested one.
- **They do not exercise the consuming flows.** The ask-once *interaction* (slice 5), triage's
  catalog input (slice 6), and `/doctor`'s catalog check (slice 4) are their own slices; this
  slice defines the rule and the fix-up offer's content, and stops there.
