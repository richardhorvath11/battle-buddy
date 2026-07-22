# Tasks: Catalog Adapter

**Input**: Design documents from `/specs/007-catalog-adapter/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R12), data-model.md, quickstart.md

**Tests**: REQUIRED — Constitution VIII (code without its tests in the same change is
incomplete) and FR-008 (the documented rules gated hermetically). Prose and test tasks are
paired inside each story; a story's checkpoint is `make verify` green, and the phase — not
the individual task — is the commit seam.

**Organization**: By user story. **US2 runs before US1** despite both being P1 and the spec
listing US1 first: resolution consumes the parsed model, so the model phase is US1's blocking
prerequisite as well as its own story. The P1 MVP seam is US2 + US1 together; US3/US4 are P2.

**Converge round 1 applied** (2 lenses, 31 findings — 27 fixed, 2 defended, 2 duplicates).
The fixes that changed this file's shape: fixture annotation *values* are now pinned (not just
presence); every single-omission fixture carries all other annotation classes so the
set-equality assertions are satisfiable; a `zz-billing` entity was added so the candidate
source-path ordering pin is observable; setup owns the existence of both `SKILL.md` and
`test_catalog_prose.py`; and several vacuous-green assertions were given discriminating
fixtures.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 per spec.md

---

## Phase 1: Setup

**Purpose**: the two files whose *existence* no story may own (so a scope cut can never
orphan a later task), the fixture catalog repo, and confirmation that the shipped-bundle
boundary needs no change.

- [x] T001 Create the two surface skeletons that setup owns:
      (a) `skills/catalog/SKILL.md` — frontmatter with `name: catalog` and a when-to-use
      description, a one-paragraph overview, and empty section stubs for *overview /
      degradation / freshness & runbook references / non-goals*. US3 (T013) and US4 (T015)
      each fill their own section and T017 completes it. The `skills/catalog/references/`
      directory is **not** created here and needs no `.gitkeep` — git carries no empty
      directory, so it materializes when T005 writes the first reference doc into it.
      (b) `tests/contract/test_catalog_prose.py` — module skeleton with the doc-set
      discovery (`rglob("*.md")` over `skills/catalog/`) and its non-vanishing guard.
      The guard's **target** set is `{SKILL.md, references/annotations.md,
      references/resolution.md}`, but it ships from T001 asserting only `SKILL.md`, since
      the two reference docs do not exist yet — marked inline with the task that widens it.
      T005 and T009 each widen it by their own doc (see those tasks); T016/T018/T019/T020
      extend the module with gates. **Neither file is created inside a story**, so dropping
      US3 or US4 per the scope-cut rule cannot orphan a Phase-6 task
- [x] T002 Create the fixture catalog repo under `tests/fixtures/catalog/`, exactly per
      data-model.md §10's roster table — **11 entities yielding 8 parsed services**.
      `README.md` records research R2's format decision, stated as an *instruction* rather
      than a category: files are named `catalog-info.yaml` and written in **strict JSON
      syntax** — double-quoted keys and string scalars, a space after every `:`, no comments,
      no trailing commas — which is simultaneously valid YAML 1.2 flow style *and* directly
      parseable by stdlib `json`, so no YAML dependency and no CI edit; plus the
      honestly-stated residual gap that block-style YAML syntax quirks are scenario-harness
      territory. ("YAML flow style" alone is broader than JSON and would admit
      `{kind: Component}`, which `json.load` rejects — do not use that phrasing as the
      instruction.) Then write `repo/services/<svc>/catalog-info.yaml` for every roster row
      with **the exact matcher/dashboard/runbook/dependsOn values pinned in the table** — the
      resolution matrix (T010) indexes into those values, so inventing different ones forces
      a back-edit through a committed green seam. Key points the table encodes and the
      implementer must not "tidy": every single-omission fixture carries all *other*
      annotation classes **and** a non-empty `spec.dependsOn` (so its `disabled_features` is a
      singleton); `payments-api` carries the minimal subset and nothing else — no annotations,
      no `dependsOn`; `checkout` and `zz-billing` share the `shared-tag` matcher and sort in
      opposite order by path vs name; `zz-billing` depends on `nonexistent-svc`; `broken` is a
      truncated flow mapping, invalid as both YAML and JSON. Use only the canonical annotation
      keys from research R4
- [x] T003 [P] Verify — no edit expected (research R10) — that
      `tests/fixtures/packaging/intended-bundle.json`'s existing `skills/**` glob already
      names `skills/catalog/`, that `tests/**` stays outside the declared bundle so the
      fixtures and the reference encoding are never named for shipping, and that
      `tests/unit/test_packaging.py` and `tests/unit/test_stdlib_boundary.py` stay green.
      Note in the task record that `test_packaging.py` lints glob *strings* and never expands
      them against the filesystem — it is a ratchet on the declared bundle, not filesystem
      proof (converge finding). Only edit if a real gap appears

**Checkpoint**: `make verify` green; the skeletons and fixture tree exist, nothing else moved.

---

## Phase 2: User Story 2 — One service shape for the whole system (P1) 🎯 ALSO FOUNDATIONAL

**Goal**: the six-field `Service` model as the only shape crossing the adapter boundary, the
literal annotation mapping that fills it, and the parse behaviors every other story builds on
— entity classification, duplicate-name tie-break, per-file failure isolation, dangling-
dependency and missing-owner surfacing, and linkage metadata kept *outside* the model
(FR-001, FR-002; D-22).

**Independent Test**: parse the fixture catalog repo and compare every parsed service against
its golden model field-for-field, empty-list defaults included.

**⚠️ Blocking**: US1 and US3 both consume `load_catalog`; no story work past this phase until
its checkpoint is green.

- [x] T004 Create `tests/helpers/catalog_reference.py` — the dev-only reference encoding
      (research R3), stdlib only (`json`, `pathlib`, `re`), plain functions over plain dicts,
      module docstring stating what it is (the CI instrument for the documented rules; never
      shipped; at runtime the "parser" is an agent reading files through the code capability)
      and what it is not (proof that an agent follows the prose — scenario-harness territory).
      This task delivers: `CANONICAL_ANNOTATIONS` / `LINKAGE_ANNOTATIONS` / `SERVICE_KINDS`
      vocabularies per research R4; `parse_entity(document, source_path)` implementing
      data-model.md §1 (six fields, empty-list-never-null defaults, scalar-or-list
      multi-valued parsing with **no** comma splitting, `missing_owner` surfaced) and §2
      (linkage split out of the model); and `load_catalog(repo_root)` implementing §3 —
      called with the **repo root itself** (`fixture_path("catalog", "repo")`), every
      `source_path` relative to it (`services/<dir>/catalog-info.yaml`); walk
      `catalog-info.yaml` files; classify by `kind` ∈ `SERVICE_KINDS` **and** non-empty
      `metadata.name`, others → `ignored_entity` warning; group by name and keep the
      lexicographically-first source path, loser dropped with a `duplicate_name` warning
      naming all paths; `depends_on` entries naming absent services are **kept** and surfaced
      as `dangling_dependency` warnings, never filtered out; a file that fails to parse yields
      one `Failure` and never raises
- [x] T005 [P] [US2] Write `skills/catalog/references/annotations.md` — the normative
      annotation mapping (FR-002): the literal-key table from data-model.md §1, the
      multi-valued parsing rule, entity classification, the duplicate-name tie-break, the
      `RunbookRef {url, commit?}` pointer format (research R11), the catalog-quality warnings
      (`missing_owner`, `dangling_dependency` — surfaced, never fatal, never silently
      dropped), and the linkage-annotation section pinning `pagerduty.com/service-id` /
      `github.com/project-slug` as **metadata exposed beside the model, never fields of the
      six-field consumer model**. Do **not** claim consumers never receive linkage values —
      they read them off the catalog; the claim is about the model's field set only (converge
      finding). Reference the code capability with the literal phrase **"your code tool's
      file reads"** (FR-007's own wording — T018 asserts this exact string) and cite no code
      operation name. **Also widen T001's non-vanishing guard** in
      `tests/contract/test_catalog_prose.py` to include `references/annotations.md` — the
      weakened guard is owned by the tasks that create the missing docs, not by a later gate
      task, so it cannot survive to merge in its shipped-from-T001 form
- [x] T006 [P] [US2] Write `tests/fixtures/catalog/golden-models.json` in **exactly**
      data-model.md §10's pinned skeleton — top-level keyed by canonical service name, each
      value an object with sibling keys `model` (the six fields and nothing else), `linkage`,
      `disabled_features` (a JSON **list**), and `source_path` — for each of the **eight**
      services the fixture repo yields (11 entities minus `docs-site`, ignored; `broken`,
      failed; and `orders-us`, the duplicate loser)
- [x] T007 [US2] Write `tests/contract/test_catalog_model.py`: every golden's `model`
      sub-object matches `load_catalog`'s parsed `Service` field-for-field including
      empty-list defaults (SC-002); the minimal service parses to a valid model with four
      empty lists (AS-2); a parsed `Service`'s keys are **exactly** the six model fields,
      with linkage present in `catalog["linkage"]` and absent from every model (AS-3);
      `docs-site` is absent from `services` and present as an `ignored_entity` warning; the
      duplicate pair yields one canonical `orders` from `services/orders-eu/…` plus one
      `duplicate_name` warning naming both paths; `payments-api` carries a `missing_owner`
      warning if and only if its fixture omits `spec.owner` (it does not — assert the warning
      list contains no `missing_owner` for the roster as written, so the vocabulary is
      exercised without a false positive); `zz-billing` carries a `dangling_dependency`
      warning naming `nonexistent-svc`; plus non-vanishing guards (the golden set is non-empty
      and its key set equals the parsed service set — a broken fixture glob must fail here,
      not silently pass)

**Checkpoint**: `make verify` green — US2 independently testable and delivered; the model is
the only shape crossing the boundary (SC-002).

---

## Phase 3: User Story 1 — A firing alert finds its service (P1) 🎯

**Goal**: alert→service resolution — exact-then-substring with the direction pinned, explicit
choice on ambiguity at either stage, and the miss path's ask-once handoff plus fix-up snippet
(FR-003).

**Independent Test**: run the documented resolution rules over the fixture catalog with
fixture alerts and assert the resolved service, or the miss classification, for every case.

- [x] T008 [US1] Extend `tests/helpers/catalog_reference.py` with `resolve(alert, catalog)`
      and `fixup_offer(alert, service_name, catalog)` per data-model.md §5 and §7. `resolve`:
      stage 1 exact over **`alert_matchers` only** (matcher equals — case-insensitively,
      whitespace-trimmed — any alert tag or field **value**; the service's own `name` is
      deliberately *not* an exact-stage input, which is FR-003's "exact tag/name" read as the
      *alert's* tag/name field); stage 2 substring **only if stage 1 matched nothing** (the
      *service's name* inside an alert tag or field value — direction pinned, never the
      reverse); >1 hit at whichever stage matched → `ambiguous` with all candidates sorted by
      **source path** and **no** `service`; nothing at either stage → `miss`; missing/empty
      alert fields are non-matching, never an exception. `service` and every `candidates`
      element is a **service-name string**, never a nested object. `fixup_offer` returns
      `{source_path, annotation_key, annotation_value, snippet}` with `annotation_key` always
      `oncall-harness/alert-match`, `annotation_value` resolved by §7's pinned order
      (`fields["name"]` → `fields["service_hint"]` → first tag → `""`), and `source_path`
      either `catalog["sources"][service_name]` or, for a service absent from the catalog, the
      pinned convention `services/<service_name>/catalog-info.yaml`
- [x] T009 [P] [US1] Write `skills/catalog/references/resolution.md` — the normative match
      order (FR-003): exact-then-substring with exactness beating substring **globally**, the
      exact stage reading `alert_matchers` only (and the service name being a substring-stage
      input exclusively), the pinned substring direction, ambiguity at either stage surfacing
      candidates for an explicit choice (never a silent pick), the miss path (ask-once → the
      answer feeds slice 3's fingerprint ladder rung 2 and `catalog_resolved: false` → the
      fix-up offer, whose snippet content this doc defines), an explicit statement that the
      responder commits the fix-up and **no agent ever writes to the catalog**, and the
      one-hop blast-radius rule with its depth bound stated outright plus the dangling-entry
      rule (kept and surfaced, never filtered) (FR-006). Cite the ask-once *interaction* as
      slice 5's execution; use the literal phrase **"your code tool's file reads"** and cite
      no code operation name. **Also widen T001's non-vanishing guard** to include
      `references/resolution.md`, completing the target set T001 recorded
- [x] T010 [P] [US1] Write `tests/fixtures/catalog/resolution-matrix.json` — the **nine**
      cases of data-model.md §10's matrix table, each `{id, alert, expected: {outcome,
      service?, candidates?, stage}}`, using the alert payloads pinned there. **`stage` is
      mandatory on every non-`miss` case**, not optional: the `exact-name hit` payload
      (`{name: "inventory-lag"}`) also contains `inventory` as a substring, so without an
      asserted `stage == "exact"` a stage-1-broken implementation still returns the right
      service by the wrong route and the case passes (converge/review finding). The four cases
      that only discriminate with the right payload, and must be written exactly as pinned:
      **exact-beats-substring** (tag matching `checkout`'s matcher **plus** a field containing
      `search-api` — two *different* services, so a stage-merging implementation returns
      `ambiguous` and fails); **multi-exact** (tag `shared-tag`, expected candidates
      `["checkout", "billing"]` in source-path order, which inverts name order and so fails a
      name-sorting implementation); **reverse-direction probe** (field value `ledger`, a
      strict substring of `ledger-svc`, so a reversed implementation resolves it instead of
      missing); **sparse alert** (empty tags and an empty field value)
- [x] T011 [US1] Write `tests/contract/test_catalog_resolution.py`: every matrix case
      classifies exactly as expected (SC-003) via parametrize, with `assert len(CASES) >= 9`
      as the non-vanishing guard; a cross-cutting assertion that **no** `ambiguous` outcome
      anywhere in the matrix carries a `service` (zero silent picks, counted); the multi-exact
      case's `candidates` list is asserted in **order**, not as a set (that is what makes the
      source-path pin observable); the sparse-alert case completes without raising; the
      reverse-direction probe resolves `miss`; the miss case's `fixup_offer` returns all four
      documented fields with the canonical annotation key, the `annotation_value` §7's pinned
      order selects, and the conventional `services/<name>/catalog-info.yaml` path for a
      service absent from the catalog

**Checkpoint**: `make verify` green — the P1 MVP seam (US2 + US1) is complete and
independently testable.

---

## Phase 4: User Story 3 — Partial catalogs degrade, never error (P2)

**Goal**: per-field degradation that disables exactly its own feature, file-scoped failure
isolation, and one-hop `dependsOn` widening (FR-004, FR-006).

**Independent Test**: parse fixture services each missing one annotation class, plus the
broken file, and assert the documented per-field behavior and the failure isolation.

- [x] T012 [US3] Extend `tests/helpers/catalog_reference.py` with `disabled_features(service)`
      (data-model.md §6: empty `dashboards` → `pane_driving`, empty `alert_matchers` →
      `alert_resolution`, empty `runbooks` → `runbook_fetch`, empty `depends_on` →
      `blast_radius_widening` — derived purely from emptiness, nothing else; `missing_owner`
      is a warning, not a disabled feature) and `blast_radius(name, catalog)` (data-model.md
      §9: the service's own `depends_on` entries, **one hop, no recursion**, sorted, and
      **unfiltered** — dangling entries are returned, having been surfaced at load time)
- [x] T013 [US3] Fill the degradation section of `skills/catalog/SKILL.md` (FR-004): the
      per-field table naming exactly which feature each absent annotation disables and
      confirming everything else keeps working (including missing `runbooks` → the absence is
      noted in the briefing), the malformed-file rule (surfaced, scoped to that file, never
      fatal, other services parse normally), the catalog-quality warnings that are *not*
      feature degradations (`missing_owner`, `dangling_dependency`), and the explicit
      statement that no partial annotation ever errors a session
- [x] T014 [US3] Write `tests/contract/test_catalog_degradation.py`: the four per-field
      fixtures each yield **exactly** their documented feature, asserted against **literal
      hardcoded sets** — `inventory` → `{"pane_driving"}`, `notifier` →
      `{"alert_resolution"}`, `ledger-svc` → `{"runbook_fetch"}`, `search-api` →
      `{"blast_radius_widening"}` — **not** against `golden-models.json` (asserting a
      hand-authored golden against the encoding that produced the same author's expectations
      is self-consistently green; SC-004 needs the literal); `payments-api` yields all four;
      `checkout` yields none; the non-vanishing guard that the union of the four asserted sets
      equals all four feature names. Plus: the no-alert-match service's alert resolves `miss`
      — the same path as a resolution miss (AS-2) — using an alert that **does not contain the
      string `notifier`**, since the substring stage would otherwise legitimately resolve it
      and the assertion would silently invert (data-model.md §5's stated consequence);
      `load_catalog` over the fixture repo yields exactly one `Failure` naming `broken`'s
      source path while all **eight** expected services still parse (AS-3);
      `blast_radius("checkout", …)` returns `["inventory"]` and — the depth bound — **does
      not** contain `ledger-svc`, the second hop; `blast_radius("billing", …)` returns
      `["nonexistent-svc"]`, proving dangling entries are kept; `search-api` (no `dependsOn`)
      returns `[]`

**Checkpoint**: `make verify` green — US3 independently testable and delivered (SC-004).

---

## Phase 5: User Story 4 — The catalog is always fresh and never copied (P2)

**Goal**: the division-of-knowledge rule as documented flow plus its mechanical instrument
(FR-005).

**Independent Test**: inspect the documented flow — every catalog read happens at session
start from the capability surface, no instruction stores catalog content anywhere, and the
runbook-reference format carries URL + commit SHA.

- [x] T015 [US4] Fill the freshness section of `skills/catalog/SKILL.md` (FR-005): catalog
      data is read fresh at session start through the code capability (the literal phrase
      "your code tool's file reads"), never cached across sessions and never copied into any
      store; only pointer-shaped runbook references (`{url, commit?}` — SHA present where
      git-hosted) reach the session row, restating slice 3's `runbook_refs` column as the
      destination without redefining it; and the catalog-unreachable path (the fingerprint
      ladder's lower rungs carry the session, the gap is surfaced in the briefing, nothing
      blocks the open). **Phrase the never-copied rule without naming any storage operation**
      — e.g. "catalog content is never written to any store" rather than naming the write op
      — because T016's SC-006 scan is unconditional (see its docstring note)
- [x] T016 [US4] Extend `tests/contract/test_catalog_prose.py` (created in T001) with the US4
      gates: the **SC-006** scan — zero occurrences of `append_record`, `update_record`,
      `put_file`, `append_entry` anywhere under `skills/catalog/**/*.md` — plus prose gates
      for the freshness statement, the runbook-pointer format, and the catalog-unreachable
      path. Record two things in the module docstring: (a) `read_records` is deliberately
      **not** scanned — reading the session store is not a catalog write, and SC-006 names
      only the four write ops; (b) this scan is **unconditional** where spec SC-006 says
      "applied to catalog content" — a deliberate widening, because scoping a scan to
      "catalog-flow sections" is fuzzy and gameable, with the cost that prose must state the
      never-copied rule without naming a write op (T015 does)

**Checkpoint**: `make verify` green — US4 independently testable and delivered.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: the naming/discipline gates that span the whole prose surface, the two cross-slice
reconciliations, and the final traceability pass.

- [x] T017 Complete `skills/catalog/SKILL.md`: finalize the frontmatter description, write the
      overview stating the six-field model is the only shape consumers see and that this slice
      ships prose and tests only — no parsing library, no shipped integration code (FR-001,
      FR-009) — add a routing table to `references/annotations.md` / `references/resolution.md`,
      and write the non-goals section (file-mode Backstage is v1's only source, API-mode
      deferred; the harness never writes to the catalog; consuming flows belong to slices
      4/5/6). Use the literal phrase "your code tool's file reads" where the read path is
      described
- [x] T018 Extend `tests/contract/test_catalog_prose.py` with the **SC-005** naming scan and
      the **FR-007** gates.
      SC-005: the `mcp__` hard fail on raw text; the deny-list scan importing `DENY_PATTERNS`
      from `tests/contract/test_skill_capability_naming.py`, **extended locally with a
      `github` pattern** (slice 3's set has none, so masking `github.com/project-slug` would
      otherwise be a no-op and that third of the positive control vacuous — converge finding),
      run over prose with the canonical **whole** annotation keys masked first (research R5 —
      whole keys only, so `grafana`, `pagerduty`, or `github` written as a product name still
      fails); and the two-halved positive control mirroring slice 3's fenced-`datadog` test
      (the canonical keys are present, so the mask has something to mask; and all three vendor
      words do not survive masking).
      FR-007: assert the **literal string** `your code tool's file reads` appears in the prose
      (not "some generic phrasing" — an unpinned phrase makes the gate a tautology against
      whatever the author wrote); and assert the prose cites none of the explicitly-enumerated
      code-operation tokens `{read_file, list_commits, search}` — the enumeration is required
      because slice 3's suffix heuristic would detect only `read_file`. The manifest-fidelity
      backstop is scoped to **that token set only** (so `read_records`, deliberately exempt
      from T016's scan, cannot trip it): any of those three appearing must exist in
      `manifest/capabilities.json`'s `optional.code.ops`. Record in the docstring that slice 4
      *did* pin those shapes in the manifest while contract v1 still has no `code` half
      (research R6)
- [x] T019 Extend `tests/contract/test_catalog_prose.py` with the prose↔encoding agreement
      test: parse the annotation mapping table out of `skills/catalog/references/annotations.md`
      and assert set-equality both ways against `catalog_reference.CANONICAL_ANNOTATIONS` and
      `LINKAGE_ANNOTATIONS` — the slice-3 `fingerprint.md`↔`bb-fingerprint` relationship
      applied here, so a doc whose table silently diverges from the encoding fails
- [x] T020 Reconcile slice 4's fixture (research R4): retag
      `tests/fixtures/doctor/catalog-valid.json`'s `battle-buddy/alert-match` →
      `oncall-harness/alert-match` and `battle-buddy/dashboard` →
      `grafana/dashboard-selector`, confirm `tests/contract/test_doctor_checks.py` and
      `test_doctor_report.py` stay green (the doctor check asserts parseability only, never
      annotation keys), and add the ratchet test to `tests/contract/test_catalog_prose.py`
      asserting that fixture's annotation keys are a subset of the canonical vocabulary —
      **with a non-vanishing guard** that the extracted key set is non-empty and contains both
      `oncall-harness/alert-match` and `grafana/dashboard-selector` (a bare subset assertion
      passes on the empty set, which is exactly how a wrong key-path extractor would silently
      neuter the ratchet — converge finding)
- [x] T021 [P] Amend `bb-technical-design.md` (research R9): a §6.1 clarification noting the
      `paging linkage` / `repo` mapping-table rows are metadata exposed beside the six-field
      model rather than fields of it, and a new decision-log row **D-22** recording this
      slice's **six** pins — (1) linkage metadata is not a consumer-model field, (2) explicit
      choice on multi-match at either stage, (3) one-hop `dependsOn` in v1 with dangling
      entries kept and surfaced, (4) substring direction (service name inside alert field),
      (5) lexicographic duplicate-name tie-break, (6) **the exact stage reads `alert_matchers`
      only — the service's own name is a substring-stage input exclusively** (the pin both
      converge lenses flagged as the one most likely to surprise a later implementer, since
      FR-003's own text says "tag/name"). Each with its rationale. Do **not** carry over the
      dropped claim that consumers never receive linkage values, nor its §4 citation — the
      design's §4 arrow targets the code capability's MCP participant, not the catalog adapter
      surface (converge finding)
- [x] T022 Final pass: run `make verify`; confirm every FR maps to ≥1 passing test against
      `quickstart.md`'s scenario table (SC-001) — **including FR-009**, whose gate is an
      assertion in `test_catalog_prose.py` that `skills/catalog/` contains no `*.py` file and
      that `tests/helpers/catalog_reference.py` is named by no glob in
      `tests/fixtures/packaging/intended-bundle.json`'s bundle (add it here if T018–T020 have
      not); confirm the four new contract modules are all collected; confirm no new dependency
      reached `.github/workflows/verify.yml` and no shipped Python was added (FR-009)

**Checkpoint**: `make verify` green — slice complete.

---

## Dependencies

```text
Phase 1 (T001–T003)  →  Phase 2 / US2 (T004–T007)  →  Phase 3 / US1 (T008–T011)
                                     ↓                            ↓
                              Phase 4 / US3 (T012–T014)           │
                                     ↓                            │
                              Phase 5 / US4 (T015–T016)  ←────────┘
                                     ↓
                              Phase 6 (T017–T022)
```

- **T004 blocks everything downstream** — `load_catalog` is what US1, US3 and the golden
  suite all consume.
- **T008, T012 extend the same file as T004** (`catalog_reference.py`) — serial with it and
  with each other.
- **T013, T015, T017 all write `skills/catalog/SKILL.md`** — serial, each filling a section
  T001's skeleton reserved. Setup created the file, so no story blocks another.
- **T016, T018, T019, T020, T022 all write `test_catalog_prose.py`** — strictly serial in that
  order; T020's fixture retag is the only part touching a disjoint file. Setup created the
  module, so a dropped US4 leaves the Phase-6 tasks with something to extend.
- **US3 depends on US2 only** (parsed models), not on US1 — it can follow US2 directly if US1
  slips.

## Parallel opportunities

- **Phase 1**: T003 runs alongside T001/T002 (verification only, disjoint files).
- **Phase 2**: T005 (annotations prose) and T006 (goldens) run alongside T004 (encoding) —
  three disjoint files, and the interfaces they share (`source_path` relativity, the golden
  skeleton, the annotation vocabulary) are all pinned in data-model.md so parallel workers
  cannot guess differently; T007 joins them and is where any disagreement surfaces.
- **Phase 3**: T009 (resolution prose) and T010 (matrix fixture) run alongside T008 — again
  with the shared interfaces (`candidates` element type, matcher values, fix-up field order)
  pinned in data-model.md rather than left to whoever runs first.
- **Phase 6**: T021 (design-doc amendment) is disjoint from everything else in the phase.
- Everything else is serial — the shared-file constraint above dominates.

## Implementation strategy

**MVP scope**: Phase 1 + Phase 2 (US2) + Phase 3 (US1) — the two P1 stories. That delivers
the internal model, the annotation mapping, and alert→service resolution with the full
determinism matrix: the catalog's reason to exist (§5.2 rung 1).

**Incremental delivery**: every phase ends at a `make verify` green seam and is committed
there. US3 and US4 each add one behavior class on top of a green MVP; Phase 6's gates and
reconciliations are additive and touch no story behavior.

**If scope must be cut**: drop whole stories from the tail (US4, then US3) — code and tests
together, never prose without its gate — and record the deferral here and in the PR body.
Phase 6's T020/T021 reconciliations travel with whatever ships, since they resolve
inconsistencies this slice introduces or exposes; T001's skeletons are what make a tail cut
safe.
