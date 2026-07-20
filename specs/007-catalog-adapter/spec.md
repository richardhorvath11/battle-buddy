# Feature Specification: Catalog Adapter

**Feature Branch**: `007-catalog-adapter`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 7 of the battle-buddy MVP (design `bb-technical-design.md` §6.1, §2 division of knowledge, §5.2 rung 1; PRD FR-2, FR-10–15; Constitution I, VII): the service-catalog surface — file-mode Backstage parsing into the internal service model, alert→service resolution, per-field graceful degradation, and the fetched-fresh/never-copied freshness rule — expressed as catalog skill prose plus hermetic tests over a fixture catalog repo this slice creates. The CI tests gate the documented *rules* via a dev-only reference encoding; agent compliance with the prose is scenario-harness territory (the slice-6 boundary).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A firing alert finds its service (Priority: P1)

An alert fires and the session-open flow asks the catalog: whose service is this? The catalog skill parses the team's `catalog-info.yaml` files (read through the code capability from the team's git repo) into the internal service model and matches the alert's fields against each service's alert matchers — exact tag/name matching first, then substring (the service's name appearing within an alert field — direction pinned, see Assumptions). A hit yields the service's full context: owner, runbooks, dashboards, dependencies. A miss feeds the slice-3 fingerprint resolution ladder: the responder is asked to name the service once, and the answer is offered back as a catalog fix-up so the next alert resolves without asking.

**Why this priority**: Alert→service resolution is the catalog's reason to exist — briefings, fingerprints, and blast radius all hang off it (FR-12, §5.2 rung 1). P1.

**Independent Test**: Run the documented resolution rules (via the test-side reference encoding) over the fixture catalog repo with fixture alerts: exact-tag hit, exact-name hit, substring hit, and a miss — asserting the resolved service, or the *miss classification*, for each (the ask-once interaction itself is slice-5 execution).

**Acceptance Scenarios**:

1. **Given** a fixture alert whose tag exactly matches a service's alert matcher, **When** resolution runs, **Then** that service is returned — exact matches win before any substring attempt. *(§6.1 resolution order)*
2. **Given** no exact match but an alert field containing a service's name as a substring, **When** resolution runs, **Then** the substring match resolves — second priority, never overriding an exact hit. *(§6.1)*
3. **Given** an alert matching no service, **When** resolution fails, **Then** the responder is asked to name the service once, the answer feeds the fingerprint ladder (rung 2), and the answer is offered as a catalog fix-up. *(§6.1, §5.2, D-19; slice-3 FR-003)*
4. **Given** an alert matching multiple services' matchers exactly, **When** resolution runs, **Then** the candidates are surfaced for an explicit choice — never a silent pick. *(spec-pinned default; design is silent — see Assumptions)*

---

### User Story 2 - One service shape for the whole system (Priority: P1)

Everything downstream — briefing, triage, deep investigation, pane driving — sees exactly one shape: `Service {name, owner, runbooks[], dashboards[], alert_matchers[], depends_on[]}`. The skill documents the annotation mapping that fills it: `kind`, `metadata.name`, and `spec.owner` (the minimal viable subset per PRD FR-13), `spec.dependsOn` for blast radius, `grafana/dashboard-selector`, the linkage annotations `pagerduty.com/service-id` and `github.com/project-slug`, and the harness's own `oncall-harness/runbooks` and `oncall-harness/alert-match`. The skill defines no output that exposes raw catalog structure — consumers get the model (consumer agents' own toolsets are their slices' scope).

**Why this priority**: FR-14's internal model is the seam that keeps every other slice catalog-agnostic; the mapping table is the integration contract with the team's repo. Co-P1.

**Independent Test**: Parse the fixture catalog repo and compare every parsed service against golden expected models — field by field, including empty lists where annotations are absent.

**Acceptance Scenarios**:

1. **Given** a fully annotated fixture service, **When** parsed, **Then** every internal-model field is populated from its documented source annotation. *(§6.1 annotation mapping; FR-11–15)*
2. **Given** a minimally annotated service (`kind` + `metadata.name` + `spec.owner` only), **When** parsed, **Then** a valid model results with empty lists for the absent fields — the minimal subset is sufficient. *(PRD FR-13's subset: kind, name, owner, annotations)*
3. **Given** any skill-defined output, **When** inspected, **Then** it is the internal model — the skill exposes no raw catalog file structure past the adapter. *(FR-14, §6)*

---

### User Story 3 - Partial catalogs degrade, never error (Priority: P2)

Real team catalogs are messy. Each missing annotation degrades exactly its own feature: no dashboards → no pane driving for that service (briefing still works); no alert-match → the ask-once + fix-up path; no runbooks → their absence is noted in the briefing (informed default extending FR-12's posture); no dependsOn → blast-radius widening simply doesn't widen. A malformed or unparseable catalog file degrades to "service unavailable from catalog" for that file only — other files still parse; nothing errors the session.

**Why this priority**: Tier 0's audience is exactly the messy-catalog team (D-19 rationale); degradation quality decides whether the tool survives first contact. P2.

**Independent Test**: Parse fixture services each missing one annotation class, plus one syntactically broken fixture file, and assert the documented per-field degradation and the file-scoped failure isolation.

**Acceptance Scenarios**:

1. **Given** a service without dashboard annotations, **When** consumed, **Then** pane driving is skipped for that service and everything else functions. *(§6.1, FR-12)*
2. **Given** a service without an alert-match annotation, **When** an alert for it fires, **Then** the ask-once + fix-up path runs — same as a resolution miss. *(§6.1, FR-12)*
3. **Given** one malformed catalog file among many, **When** the catalog is parsed, **Then** the failure is isolated to that file — surfaced, not fatal — and other services parse normally. *(informed default from FR-12's degradation posture — see Assumptions)*
4. **Given** a service with `spec.dependsOn`, **When** blast radius is assessed, **Then** the dependency list widens the assessment (FR-15); absent, assessment proceeds unwidened. *(§6.1, FR-15)*

---

### User Story 4 - The catalog is always fresh and never copied (Priority: P2)

Catalog data is human-curated in the team's git repo and fetched fresh at session start through the code capability — never cached across sessions, never copied into the session store. The session row records runbook *references* (URL + commit SHA where git-hosted), not runbook content.

**Why this priority**: The division of knowledge (§2) is a load-bearing product boundary: stale copies of human-curated data are worse than fetches that fail visibly. P2.

**Independent Test**: Inspect the skill's documented flow: every catalog read happens at session start from the capability surface; no instruction stores catalog content anywhere; the runbook-reference format carries URL + commit SHA.

**Acceptance Scenarios**:

1. **Given** the skill's documented read flow, **When** inspected, **Then** catalog data is fetched at session start via the code capability and no instruction persists catalog content to any store. *(§2 division of knowledge; Constitution I)*
2. **Given** a runbook reference destined for the session row, **When** formed, **Then** it is URL plus commit SHA (where git-hosted) — a pointer with version, never content. *(FR-20; slice-3 schema `runbook_refs`)*

---

### Edge Cases

- **Alert with empty/absent fields the matchers need**: resolution treats missing alert fields as non-matching, falls through to the miss path — never a crash on sparse alerts. *(informed default)*
- **Two services with the same `metadata.name`** (catalog authoring error): surfaced as a catalog-quality warning; the first in lexicographic file-path order wins for resolution (a deterministic tie-break), and the fix-up path is the correction vehicle. *(spec-pinned default — see Assumptions)*
- **Substring match that hits multiple services**: same explicit-choice rule as multi-exact (US1 AS-4) — never silent.
- **Catalog repo unreachable at session start**: the fingerprint ladder's lower rungs carry the session (responder-named, alert-tag, rule-based); the catalog gap is surfaced in the briefing (informed default); nothing blocks the open. *(§9 catalog rows; §5.2, D-19)*
- **dependsOn cycles or depth**: blast-radius widening is one hop in v1 — direct `dependsOn` entries only; deeper traversal is a future concern the skill does not promise. *(spec-pinned default; design says "blast-radius widening" without depth — see Assumptions)*
- **Non-service catalog entities** (`kind` values other than Component/Service): ignored with a note, never parsed into the model — classification reads the entity's `kind`, part of the minimal subset. *(informed default anchored on PRD FR-13's `kind` field)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The catalog skill MUST define the internal service model — `Service {name, owner, runbooks[], dashboards[], alert_matchers[], depends_on[]}` — as the only catalog shape any consumer sees; raw catalog file structure never crosses the adapter boundary. *(§6.1, FR-14)*
- **FR-002**: The skill MUST document the annotation mapping with the literal keys: `metadata.name` → name and `spec.owner` → owner, with `kind` read for entity classification (minimal viable subset, PRD FR-13); `spec.dependsOn` → depends_on (FR-15); `grafana/dashboard-selector` → dashboards (FR-11); `oncall-harness/runbooks` → runbooks (FR-12); `oncall-harness/alert-match` → alert_matchers (FR-12). The linkage annotations `pagerduty.com/service-id` (paging) and `github.com/project-slug` (repo, scoping deploy-window reads) parse into adapter-internal linkage metadata — deliberately not fields of the consumer-facing six-field model, resolving the design table's dangling rows (flagged for design reconciliation — see Assumptions). *(§6.1 annotation table; FR-11)*
- **FR-003**: Alert→service resolution MUST match the firing alert's fields against `alert_matchers` with exact tag/name matching first, then substring on service name; multi-match at either stage surfaces candidates for an explicit choice (spec-pinned); a miss triggers ask-once — the responder's answer feeds the slice-3 fingerprint ladder (rung 2) and is offered as a catalog fix-up, whose content the skill defines (the ready-to-commit annotation snippet keyed to the responder's answer). *(§6.1; §5.2, D-19; slice-3 FR-003)*
- **FR-004**: Degradation MUST be per-field and non-fatal: missing dashboards → no pane driving for that service; missing alert-match → ask-once + fix-up; missing runbooks → noted absence; missing dependsOn → no widening; a malformed file → file-scoped failure, surfaced, other files unaffected; no partial annotation ever errors a session. *(§6.1, FR-12; §9)*
- **FR-005**: Catalog data MUST be fetched fresh at session start through the code capability and never cached across sessions or copied into any store; runbook references persisted to the session row are URL + commit SHA (where git-hosted), never content. *(§2 division of knowledge; FR-20; slice-3 `runbook_refs`)*
- **FR-006**: Blast-radius widening MUST use direct `dependsOn` entries (one hop, v1) to widen affected-service assessment; the skill states the depth bound explicitly. *(FR-15; depth spec-pinned — see Assumptions)*
- **FR-007**: All skill prose MUST reference the code capability generically for reads ("your code tool's file reads") — no concrete MCP server or tool names, and no invented operation names either: contract v1 defines no code operations, and their shapes are slice 4's to pin or defer (see Assumptions). File-mode Backstage is the only v1 catalog source, API-mode explicitly deferred. *(Constitution VII; §7.1; PRD §8)*
- **FR-008**: Hermetic tests MUST encode the documented rules as a test-side reference encoding (dev-only tooling, permitted by the D-1 exemption like the mock itself) run over the fixture catalog repo this slice creates: golden-model parsing (fully annotated, minimal, per-field-missing services), the resolution matrix (exact tag, exact name, substring, multi-match, miss classification), degradation cases including malformed-file isolation, and one-hop dependsOn widening — no live git, no credentials, no network. These tests gate the *rules'* coherence and the fixture contract; whether a live agent follows the skill prose is scenario-harness territory (design §10 on-demand layer), out of CI scope — the slice-6 boundary, stated here deliberately since §10's hermetic layers predate this slice. *(design §10; Constitution VIII; see Assumptions)*
- **FR-009**: This slice ships skill prose and tests only — no parsing library, no shipped integration code; parsing at runtime is skill-guided reading over the code capability, and the test-side reference encoding is dev tooling, never shipped. *(Constitution I, D-1 exemption)*

### Key Entities

- **Internal service model**: The six-field `Service` shape — the adapter's entire public surface.
- **Annotation mapping**: The documented catalog-file → model field table; the integration contract with the team's repo.
- **Alert matcher**: Per-service match rules consumed by resolution; the alert-match annotation's parsed form.
- **Fixture catalog repo**: The fixture catalog *created by this slice* — the hermetic stand-in for a team's real catalog repo; design §10 sketched it under a scenarios layout the merged scaffold superseded (see Assumptions).
- **Reference encoding**: The dev-only, test-side executable form of the documented parsing/resolution rules — the CI instrument; never shipped.
- **Runbook reference**: URL + commit SHA pointer persisted to the session row; never content.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement maps to at least one passing hermetic test; the suite is green on every commit via the standard verify gate.
- **SC-002**: 100% of fixture services parse to their golden models field-for-field, including empty-list defaults for absent annotations.
- **SC-003**: The resolution matrix classifies 100% correctly: exact beats substring, multi-match surfaces choices, misses reach the ask-once path — zero silent picks across all fixture cases.
- **SC-004**: 100% of degradation fixtures produce their documented per-field behavior; the malformed-file fixture never prevents any other fixture service from parsing.
- **SC-005**: Zero concrete MCP server or tool names in the skill prose, verified mechanically with the documented annotation-key vocabulary allowlisted (annotation keys are catalog-file data, not tool names — the scan must not trip on `grafana/`, `pagerduty.com/`, `github.com/` inside FR-002's table).
- **SC-006**: The skill's catalog-flow prose contains zero occurrences of the storage/artifact/diary write operations (`append_record`, `update_record`, `put_file`, `append_entry`) applied to catalog content — a mechanical scan instrumenting the division-of-knowledge rule.

## Assumptions

- **Multi-match handling** (exact or substring stage): candidates surfaced for explicit choice — spec-pinned; §6.1 defines match order but not the ambiguous case.
- **Malformed-file isolation**: per-file failure scoping is an informed default extending FR-12's per-field degradation posture to the file level; the design addresses partial annotations, not broken files.
- **Duplicate service names**: the first in lexicographic file-path order wins, with a surfaced catalog-quality warning — spec-pinned (lexicographic order is what makes "first" deterministic); catalog uniqueness is Backstage's own norm and the fix-up path is the correction vehicle.
- **dependsOn depth**: one hop in v1 — spec-pinned; the design says "blast-radius widening" (FR-15) without depth, and unbounded traversal invites cycle handling the tier-0 scale doesn't need. Deeper traversal is a recorded future option.
- **Non-service entities ignored**: file-mode parsing considers service-shaped entities only — informed default from §6.1's Component/service framing.
- **Consumers are other slices**: the /page resolution step (slice 5), triage's catalog input (slice 6), and doctor's catalog-parseable check (slice 4) consume this surface; their flows are out of scope here. The ask-once *interaction* is executed by the consuming command (slice 5); this slice defines the rule and the fix-up offer's content.
- **Fixture catalog repo is created by this slice**: no catalog fixture exists in the merged scaffold today, and the scaffold's actual layout uses `tests/fixtures/` (design §10's `tests/scenarios/` sketch was superseded by the slice-1 implementation); the fixture's location follows the scaffold's real conventions, pinned at plan time.
- **CI-vs-scenario boundary and the reference encoding**: design §10's hermetic layers enumerate hooks/helpers and the mock — no catalog entry — and place the catalog fixture in the on-demand scenario harness. This spec's CI tests are therefore a *rules-coherence* gate via a dev-only reference encoding of the documented mapping and match order (D-1 exempts dev tooling); agent compliance with the prose stays in the scenario harness. The reference-encoding-vs-agent seam is exactly what that harness exists to catch. Fixture format note: shipped code has no YAML dependency, but the reference encoding is dev-only — a dev YAML dependency or JSON-mirrored fixtures is a plan-time choice.
- **Code-capability surface**: contract v1 defines no `code` operations (the optional half is slice 4's to pin or defer, per its manifest FR); skill prose therefore references the capability generically, and tests bind to fixture files directly — the same fixture-surface pattern slice 4 pinned for its own contract gaps.
- **Linkage annotations** (`pagerduty.com/service-id`, `github.com/project-slug`): the design's mapping table names them but the six-field model has no matching fields — pinned here as adapter-internal linkage metadata (not consumer-model fields), flagged for design reconciliation. Consumption route: the design's session sequence runs triage's deploy-window check *through* the catalog surface (§4 diagram, "deploy window check (service + dependsOn)"), so consumers receive answers, never the linkage metadata itself.
- **Substring direction**: "substring on service name" is pinned as the service's name appearing within an alert field (the reverse reading would match almost nothing); flagged as a pin on design silence.
