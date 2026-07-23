# Specification Quality Checklist: Deterministic Layer

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-07-20
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- "Python 3 stdlib, 3.9+" appears in FR-001/SC-003/SC-006 deliberately: it is a
  constitutional Platform Constraint on shipped code (design D-1), i.e. a requirement of
  the product, not an implementation choice made here. Same justification pattern as
  slice 1's naming of `bb-mock-mcp`.
- The five components are named as the objects under specification (they are the feature);
  hook-event field names, heuristic regexes, and file formats are deferred to the plan.
- The no-bypass decision for the deny hook (Assumptions) is recorded explicitly because
  the family-meals-derived push-gate pattern uses inline bypasses — spelling out that
  runtime deny classes differ prevents a plan-time wrong turn.
- Validation run 1 (2026-07-20): all items marked pass. Independent review (PR #3)
  falsified two: "testable and unambiguous" (FR-011 "confirmed" ambiguity, benign
  near-miss contradiction, sourceless auth-error context, undefined untrusted-capability
  classification) and "dependencies identified" (binding-map dependency for FR-008/FR-010
  missing). Also: AGENTS.md push-gate scheduling conflict, undefined deep-dive/
  truncated-verdict markers, FR-002↔FR-012 contradiction, missing §2.1 config warning,
  wrong citation authorities, unpinned "newest Python", missing US5 Independent Test.
- Validation run 2 (2026-07-20, post-review fixes): marker trigger pinned to "present and
  not cleared" with the skipped-close scenario added (US5 AS-2); benign corpus given a
  membership rule and made the decided over-match boundary; trace lines gained `outcome`
  (incl. `auth_error`) making the credential-scanning class detectable; tripwire's
  binding-map dependency named with graceful degradation; AGENTS.md amended in-PR on
  push-gate scheduling; FR-006 keys off ledger `phase` (plan pins enumeration); FR-002
  allows payload-named paths; FR-013 cites D-6 and gained acceptance; FR-015 added for
  the §2.1 config warning; SC-003 pinned to the 3.9/3.12 matrix; US5 Independent Test
  added. Claimed FR-009 was fixed — round-2 review caught that the FR-009 edit was NOT
  actually applied (only US4 AS-2 was), leaving an FR↔scenario contradiction; that run's
  "all items pass" was therefore false on one item.
- Validation run 3 (2026-07-20, round-2 fixes): FR-009 actually rewritten (deny +
  trace-log budget exhaustion, no marker, verdict fields carry FR-5f(a) semantics, PRD
  citation labeled); US2 prose aligned to phase-based invariant; FR-010 degraded mode
  given an Independent Test fixture; FR-002 read sources extended to the workspace config
  block (fixture in tests); untrusted set v1 narrowed to alerting+observability with the
  ticket-shaped deferral made an explicit plan obligation. All items pass. Ready for
  round-3 verification, then `/speckit-plan`.
- Validation run 4 (2026-07-20, T026 quickstart walkthrough at slice completion — phases
  6–8 on branch `002-deterministic-layer-us4us5`): all 10 quickstart scenarios validated.
  `make verify` green (432 unit + 97 contract tests); unit layer additionally green on
  Python 3.9.6 (the D-1 floor) and 3.13.5 locally, with the 3.9+3.12 CI matrix as the
  SC-003 authority. Per scenario: (1) misbehavior gate — two-corpus suite green in
  `test_guardrail_deny` (136 tests), and a deliberately-uncovered probe fixture added
  during the walkthrough failed the suite in both gate tests until removed (regression
  direction proven live); (2) fail-open — the 9-fixture fault corpus passes through the
  shared runner against all three hooks (SC-007); (3) fingerprint stability — golden
  corpus green on 3.9.6/3.13.5 incl. the seeded rule-change tripwire demo
  (`test_fingerprint`, 64); (4) validator corpus — per-rule violations, one-pass
  multi-violation reporting, byte-identity (`test_validate`, 67); (5) trace + budget —
  SC-005 hundred-call session yields exactly 100 ordered gap-free lines, cap N denies
  call N+1 as `denied:turn_cap` with the emit-your-verdict message (`test_tool_trace`,
  51); (6) tripwire — one advisory + one tripwire event per trip, no-binding-map
  degraded mode with one disabled notice per session; (7) session-guard states —
  warnings on exactly the two present marker states, staging per scenario, FR-015
  config-absent warning (`test_session_guard`, 27); (8) protocol conformance —
  `test_local_state_protocol` (36) plus consumer-side protocol tests in the hook suites
  (FR-013); (9) stdlib boundary — zero third-party imports across `hooks/` + `bin/`
  (`test_stdlib_boundary`, SC-006); (10) latency — R8 p95 < 100ms per hook entry over
  100 invocations (`test_hook_latency`, SC-002). Slice 2 complete.
- Validation run 5 (2026-07-20, post-convergence re-validation): two converge review
  rounds (line-level, silent-failure, test-coverage, whole-system-vs-governing-docs
  reviewers; fix-or-defend per finding) landed as the two `converge round` commits.
  All round-1 🔴/🟠 findings fixed and re-verified against file text by round 2; round
  2 surfaced one regression (blocking staging probe — fixed with a non-blocking
  fd-based probe) and the SessionEnd `systemMessage` rendering ambiguity — mitigated
  by mirroring the stale-marker warning at SessionStart (`resume` exempt), recorded in
  the protocol doc. `make verify` green after each round; suite grew from 432 to the
  current unit-layer count with the convergence tests; unit layer re-run green on
  Python 3.9.6 (D-1 floor).
