# Tasks: Investigation Agents & Skill

**Input**: Design documents from `/specs/006-investigation-agents/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R12), data-model.md, quickstart.md

**Tests**: REQUIRED — Constitution VIII (code without its tests in the same change is
incomplete) and FR-012 (every documented property exercised hermetically). Prose and
test tasks are paired inside each story; a story's checkpoint is `make verify` green.

**Organization**: By user story, in spec priority order. US1/US2/US3 are P1 (the MVP
seam), US4/US5 P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US5 per spec.md

## Phase 1: Setup

**Purpose**: The two new shipped surfaces every story writes into, registered with the
packaging boundary.

- [x] T001 Create `skills/investigation/SKILL.md` skeleton (frontmatter with name +
      when-to-use description; overview stating the skill is loaded by the orchestrator
      and both investigation agents — one skill, different budgets/toolsets per role,
      FR-001; routing table to `references/schemas.md` / `briefing.md` /
      `retrieval.md`; empty section stubs for validation discipline / anchoring guard /
      evidence rules / untrusted data / launch conditions / spawn & role registration)
      and the `skills/investigation/references/` directory
- [x] T002 [P] Verify (no edit — research R11, converge finding) that
      `tests/fixtures/packaging/intended-bundle.json`'s existing `agents/**` and
      `skills/**` globs cover both new shipped dirs and
      `tests/unit/test_packaging.py` stays green

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The normative schemas reference and its consistency gate — every story's
examples, contracts, and guard statements cite these schemas; the doc↔validator
agreement test must exist before prose and validator can co-evolve safely (FR-011,
SC-002).

**⚠️ CRITICAL**: No user story work until this phase is complete.

- [x] T003 Write `skills/investigation/references/schemas.md`: normative
      `bb.verdict.v1` + `bb.ledger.v1` statements per data-model.md's field tables
      (required/optional, types, per-field v1 validation); provenance/validation
      vocabularies; the phase model with invariant-phase scoping (early phases permit
      sparse ledgers — the immediate-escalation rationale); the evidence
      `{url, excerpt}` shape; the recorded v1 scope note (research R9 — `known_issue`
      sub-fields carried-but-unvalidated, any-string `status` with only `"live"`
      counting, fails-loud rationale); the validator/fixture-corpus relationship
      (slice-3 FR-003 precedent: `bb-validate` is the implementation, its fixtures the
      executable form, the consistency test ties them); one fenced machine-readable
      vocabulary block in R4's pinned line format (`phases: …`, `invariant-phases: …`,
      `provenance: …`, `validation: …`, `min-live: 3`, `schemas: …` — the
      set-equality parse target, converge finding); and marker-tagged worked
      examples per research R4's format (`<!-- bb-example: <id> expect=valid -->` /
      `expect=invalid rule=<rule>` before each fenced JSON block) — at minimum: valid
      verdict (incl. honest no-signal + budget-truncated), valid seeded-from-triage
      early-phase ledger, valid invariant-phase ledger, invalid unvalidated-non-fresh,
      invalid prose-only evidence, invalid anchoring-guard breaches (both rules),
      invalid unknown-phase — every documented-invalid naming its rule from
      data-model.md's rule list
- [x] T004 Write `tests/contract/test_schemas_reference.py` (research R4): parse every
      marker+fence pair from schemas.md; `expect=valid` ⇒ `bb_validate.validate()`
      returns zero violations; `expect=invalid` ⇒ every named rule appears among the
      violation rules (membership, never exact-set — multi-rule states are legitimate,
      converge finding); non-vanishing guards (minimum example count; ≥1 valid + ≥1
      invalid per schema); vocabulary agreement by parsing the doc's fenced vocabulary
      block (T003) and asserting exact set-equality both ways against imported
      validator constants (`PHASES`, `INVARIANT_PHASES`, `PROVENANCE_VALUES`,
      `VALIDATION_VALUES`, `MIN_LIVE_HYPOTHESES`,
      `VERDICT_SCHEMA`/`LEDGER_SCHEMA`)

**Checkpoint**: `make verify` green — schemas reference and validator mechanically
converged (SC-002).

---

## Phase 3: User Story 1 — Recalled memory is a hypothesis, never a conclusion (P1) 🎯

**Goal**: The skill's core discipline — validation-first ordering, the phase-scoped
anchoring guard, the evidence rule, the untrusted-data rule, and the briefing/retrieval
reference surface (FR-001–FR-005) — with the guard's full state matrix proven against
the real validator (SC-004).

**Independent Test**: The documented invariants and the validator's accepted rules are
the same rules — `test_schemas_reference.py` (Phase 2) plus the matrix and ordering
gates below, all hermetic.

- [x] T005 [US1] Fill `skills/investigation/SKILL.md` core sections: **validation
      discipline as the first section after the overview** (recalled sessions and
      triage candidates are hypotheses; provenance `triage`|`recall`|`fresh`; every
      non-`fresh` hypothesis VALIDATED/INVALIDATED against current-incident evidence
      before being acted on — FR-001); the anchoring guard with the validator's exact
      phase scoping and enforcement attribution ("the slice-2 validator at
      checkpoint-write time" — the skill instructs, the validator verifies; FR-002);
      the evidence rule (`{url, excerpt}` for hypotheses, verdicts, findings, and
      briefings alike; prose-only invalid by schema — FR-003); the capability-scoped
      untrusted-data rule (v1 set `{alerting, observability}` matching slice-2's
      tripwire pin, `<untrusted-telemetry>` delimiter-wrapping where the agent controls
      text — checkpoints, briefings, diary drafts, subagent prompts; stated as
      probabilistic mitigation, guarantees only in deterministic layers 1–3, tripwire
      advisory per D-20; ticket-shaped-tools deferral with slice-2 FR-010's rationale —
      FR-004, research R10); and the reference routing (briefing format per
      `references/briefing.md`; retrieval per `references/retrieval.md`'s pointer —
      FR-005)
- [x] T006 [P] [US1] Write `skills/investigation/references/briefing.md`: briefing
      format guidance — every claim deep-linked with `{url, excerpt}` evidence (the
      testable property; section order/wording is presentation guidance per spec
      Assumptions); the causal-field discipline (root-cause and contributing-factor
      statements in briefings and ledger syntheses are explicitly-labeled proposals,
      never promoted to fact without a human decision — FR-005, Constitution V)
- [x] T007 [P] [US1] Write `skills/investigation/references/retrieval.md` as the
      pointer document (research R1): names
      `skills/session-store/references/retrieval.md` as the normative home of the
      three-stage retrieval flow, states what an investigation agent consumes from it
      (candidate rows enter as `recall`-provenance hypotheses), restates nothing
      normatively
- [x] T008 [US1] Write `tests/unit/test_anchoring_matrix.py` (research R5 — unit
      layer: pure validator behavior, runs on the py3.9 floor beside
      `test_validate.py`; converge finding): both invariant phases × {2 live ⇒
      `ledger.min_live_hypotheses` present; 3 live none fresh ⇒
      `ledger.fresh_required` present; 3 live with fresh ⇒ no anchoring-rule
      violations; 3 live non-fresh + dead fresh ⇒ `ledger.fresh_required` present}
      via an in-test ledger builder — rule-presence assertions, never exact-set
      (multi-rule cells are legitimate); early phases (`triage-seeded`,
      `hypothesis-generation`) accept sparse and empty ledgers (empty =
      `hypotheses: []`, the required field present); `resolution` non-invariant
      (SC-004, FR-002)
- [x] T009 [US1] Write `tests/contract/test_investigation_prose.py` (research R12)
      initial module: the SC-005 naming scan over `skills/investigation/**/*.md` and
      `agents/*.md` via rglob (import the public merged `DENY_PATTERNS` from
      `test_command_capability_naming.py` and `FENCE_RE` from
      `test_skill_capability_naming.py` — never the private extensions dict, converge
      finding; `mcp__` raw-scan fenced-or-not; deny-list fence-stripped);
      discipline-first ordering gate (first `##` section after overview is the
      validation discipline — US1-AS1); anchoring-guard section names both invariant
      phases + both early phases + validator attribution; the evidence-rule anchor
      (`{url, excerpt}`, prose-only invalid — FR-003) and the one-skill-loaded-by-all
      anchor (orchestrator + both investigation agents, different budgets/toolsets per
      role — FR-001's loading clause) present; untrusted-data section names
      the v1 set, the delimiter, and the probabilistic framing; briefing.md carries the
      causal-proposal anchor

**Checkpoint**: `make verify` green — skill core + matrix + ordering gates proven.

---

## Phase 4: User Story 2 — Triage answers four questions fast, honest when it can't (P1) 🎯

**Goal**: The triage agent definition with every FR-006 pin, its toolset mechanically
cross-checked against the manifest (SC-006 instrument lands here).

**Independent Test**: `test_agent_toolsets.py` parses the definition's pinned
properties; verdict examples it references already validate via Phase 2.

- [x] T010 [US2] Write `agents/triage.md` (research R2 format): frontmatter
      (name + description only); model class fast/cheap with budget-vs-depth rationale,
      configurable via workspace `battleBuddy` config, no key minted (research R3);
      budget section — ≤2-minute wall-clock *target* measured and reported in
      `budget_spent`, never enforced; turn cap default 15, key
      `budgets.triageTurnCap`, enforcement attributed to the slice-2 hook (the
      definition never claims to self-enforce), and the cap-reached instruction —
      past the cap the hook denies further tool calls; emit the verdict from evidence
      in hand (a truncated verdict with `budget_spent` filled is valid and honest —
      spec edge case); toolset table (Capability /
      Operations / Access) — read-only rows for `alerting`, `code` (catalog and
      runbook reads), `storage` (session-store reads), `observability`; the four fixed
      questions (Known? Real? What changed? Who's affected?) each tied to its
      capability; input contract (alert context, flap history, catalog entry +
      runbooks, candidate session rows — supplied by the slice-5 spawn step); output
      contract `bb.verdict.v1` citing `references/schemas.md`, honest no-strong-signal
      as a first-class answer, budget-truncated verdict satisfying FR-5f(a) via its own
      `no_strong_signal`/`budget_spent` fields — no separate signal invented;
      mid-session re-invocation charter (classify related-to-current vs separate,
      without disturbing a running deep investigation)
- [x] T011 [US2] Write `tests/contract/test_agent_toolsets.py` (research R7): toolset
      table parser over `agents/*.md`; every Capability token ∈
      `manifest/capabilities.json` required ∪ optional (loaded dynamically — SC-006);
      triage's capability set exactly `{alerting, code, storage, observability}` and
      every triage row marked read-only; non-vanishing guard (every parsed agent doc
      yields ≥1 capability row)
- [x] T012 [US2] Extend `tests/contract/test_investigation_prose.py` with the triage
      pinned-property gates: turn-cap section states default 15 + names
      `budgets.triageTurnCap` + attributes enforcement to the deterministic layer
      (US2-AS1); four-question anchors present; truncation-satisfies-FR-5f(a) statement
      present without a separate invented signal (US2-AS3); re-invocation charter
      anchors (US2-AS4)

**Checkpoint**: `make verify` green — triage definition proven against manifest and
schema gates.

---

## Phase 5: User Story 3 — Deep investigation owns the ledger; orchestrator stays thin (P1) 🎯

**Goal**: The deep-investigator definition with every FR-007 pin — ledger ownership,
gated checkpoints, seeding, fresh-before-deep-dive, ledger-updates-only reporting.

**Independent Test**: Pinned-property inspection via the two test modules; its ledger
examples (seeded-from-triage included) already validate via Phase 2.

- [ ] T013 [US3] Write `agents/deep-investigator.md` (research R2 format): frontier
      model class (configurable, research R3), open budget; wide toolset table —
      capability-named reads, every mutating row marked approval-gated (the guardrail
      layers stay between the agent and any change — FR-007, Constitution III); ledger
      ownership + synthesis (specialist findings merge into the ledger; only ledger
      updates flow to the orchestrator — relaying raw findings upward forbidden,
      FR-5b); checkpoint rule — every ledger update checkpoints to the session store
      through slice-3's conventions (`skills/session-store/` checkpoints section) with
      the slice-2 validator gating every write (one re-prompt, then persist flagged —
      never a direct unvalidated write; US3-AS1); seeding rule — ledger initializes
      from the triage verdict with provenance `triage`, unvalidated, and ≥1 `fresh`
      hypothesis required before deep-diving any candidate (US3-AS2); specialist
      dispatch section (parallel, read-only; findings return contract) carrying the
      agent-teams future mode as an explicitly non-normative note (opt-in once stable,
      no design content — FR-008's note lands here with the dispatch machinery);
      null-result handling (empty findings summary is legitimate; recorded against the
      hypothesis, no blind re-dispatch — spec edge case); all-recalled-INVALIDATED
      continuation (invalidation is a success of the discipline — spec edge case)
- [ ] T014 [US3] Extend `tests/contract/test_agent_toolsets.py` (deep investigator:
      capabilities ⊆ manifest; mutating rows marked approval-gated; read rows
      capability-named) and `tests/contract/test_investigation_prose.py` (checkpoint
      section cites the validation gate + slice-3 conventions — US3-AS1; seeding
      anchors `triage`-provenance-unvalidated + ≥1-fresh-before-deep-dive — US3-AS2;
      ledger-updates-only + raw-findings-forbidden anchors — US3-AS3)

**Checkpoint**: `make verify` green — all three P1 stories complete (MVP seam).

---

## Phase 6: User Story 4 — Specialists dig in parallel, report evidence not vibes (P2)

**Goal**: Three specialist definitions, each pinning the four FR-008 properties.

**Independent Test**: Pinned-property inspection per definition; findings-shape gate.

**Ratchet note** (converge finding): the merged deny-list carries code/observability
vendor names (source-host and metrics products) and the SC-005 scan covers these
docs — specialist prose must stay capability-only ("the deploy-history tool", never a
vendor), with any illustrative URLs inside fences (the deny scan strips fences; the
`mcp__` scan does not, so no literal tool-call strings anywhere, fenced or not).

- [ ] T015 [P] [US4] Write `agents/log-diver.md` (research R2 format): single purpose
      (log excavation for the dispatched hypothesis); read-only toolset table
      (`observability` — log search); parallel dispatch by the deep investigator;
      findings-summary return to the deep investigator only — never the orchestrator or
      responder — every finding a `{url, excerpt}` evidence entry (prose-only findings
      non-conforming); empty findings summary legitimate
- [ ] T016 [P] [US4] Write `agents/deploy-analyst.md`: same format — single purpose
      (deploy-window correlation for service + dependsOn); read-only toolset
      (`code` — commit/deploy history reads); same dispatch, return, evidence, and
      empty-result pins
- [ ] T017 [P] [US4] Write `agents/dependency-checker.md`: same format — single purpose
      (dependency health along the catalog's dependsOn edges); read-only toolset
      (`code` — catalog reads; `observability` — dependency metrics); same dispatch,
      return, evidence, and empty-result pins
- [ ] T018 [US4] Extend `tests/contract/test_agent_toolsets.py` (each specialist:
      capabilities ⊆ manifest, all rows read-only) and
      `tests/contract/test_investigation_prose.py` (each specialist: single-purpose
      anchor, findings-to-deep-investigator-only anchor, `{url, excerpt}` findings
      contract anchor — US4-AS1/AS2; the agent-teams note in deep-investigator.md is
      marked future/non-normative — US4-AS3)

**Checkpoint**: `make verify` green.

---

## Phase 7: User Story 5 — Right speed at the right time, every agent accountable (P2)

**Goal**: The skill's launch conditions (FR-009) and spawn-time role registration with
the mechanism/policy split (FR-010), the registration write proven
protocol-conforming (SC-003).

**Independent Test**: Launch-condition inspection + simulated registration write
validated against the protocol's `agents.json` shape.

- [ ] T019 [US5] Fill `skills/investigation/SKILL.md` launch + spawn sections: exactly
      the three FR-5f launch conditions — (a) triage returns no strong signal or
      recommends escalation (a budget-truncated verdict satisfies this via its own
      fields), (b) responder request with `/incident` promotion always launching, (c) a
      triage-recommended fix fails verification — with orchestrator-proposes /
      responder-confirms and the `autoLaunchDeep` flag for incident severity; the
      orchestrator ingests ledger updates only, never raw findings (FR-009); the spawn
      flow — every spawn (triage, deep, each specialist, registered regardless of cap
      status) writes the actor-key → role entry (`triage` | `deep` |
      `specialist:<name>`) into the protocol's `agents.json` `roles` map per
      data-model.md's shape; the mechanism/policy split stated (identity and
      enforcement are the deterministic layer's; role registration is the skill's;
      unregistered actors are uncapped by protocol rule — fail open; the skill does not
      re-claim enforcement); v1 note — only the triage role carries a budget key, so
      specialist registration buys trace attribution and future per-role budgets (spec
      edge case)
- [ ] T020 [US5] Write `tests/contract/test_role_registration.py` (research R6):
      simulate the documented spawn write against a temp state dir (merge into `roles`,
      never rewrite other entries); shape check — protocol tag `bb.local.v1`, `roles`
      a string→string map with non-empty string actor keys (no key grammar asserted —
      key derivation is the deterministic layer's unowned surface, analyze U2), every
      role matching `^(triage|deep|specialist:[a-z0-9-]+)$`;
      role values under test derived from the shipped agent docs — `triage`/`deep`
      from their definition files' existence, `specialist:<stem>` from the specialist
      doc filenames — never test literals (converge finding, FR-012
      assert-on-artifacts); a seeded non-conforming role (e.g. `admin`) is rejected
      (SC-003); reuse/extend `tests/unit/test_local_state_protocol.py`'s existing
      agents.json coverage rather than duplicating it
- [ ] T021 [US5] Extend `tests/contract/test_investigation_prose.py`: exactly three
      launch-condition anchors + confirm rule + `autoLaunchDeep` named (US5-AS1);
      registration section carries the mechanism/policy-split and fail-open anchors
      without re-claiming enforcement (US5-AS3)

**Checkpoint**: `make verify` green — all five stories independently proven.

---

## Phase 8: Polish & Cross-Cutting

**Purpose**: Full-surface gates that need every file to exist, and the design-doc
reconciliation the spec flags.

- [ ] T022 Finalize the SC-005 naming scan in
      `tests/contract/test_investigation_prose.py` (serial — last link of the module
      chain, converge finding): non-vanishing expected-file set (all nine files —
      five agent docs + SKILL.md + three references); confirm the imported merged
      `DENY_PATTERNS` covers the code/observability vendor names; `mcp__` raw scan
      over the full set (FR-013)
- [ ] T023 [P] Reconcile `bb-technical-design.md` §5.4's example ledger (research R8):
      replace with a validator-passing example (≥3 live, ≥1 fresh, non-fresh
      validated); version bump with change note per that doc's convention; PR body
      calls the edit out
- [ ] T024 [P] Update `specs/006-investigation-agents/quickstart.md` scenario table if
      any module names/paths drifted during implementation; confirm the FR-001–FR-014 →
      test mapping is complete (SC-001) and record it
- [ ] T025 Run full `make verify`; confirm packaging boundary (new dirs covered by the
      existing bundle globs, no dev paths shipped — T002's verification), hermeticity
      (no credentials/network in new tests), and walk quickstart.md's scenario table
      end-to-end

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: T001 before T003 (SKILL.md routes to schemas.md); T002
  parallel with everything after T001.
- **Phase 2 blocks all stories**: T003 → T004 (doc → consistency gate).
- **US1 (Phase 3)**: T005 after T001+T003 (cites schemas); T006/T007 parallel with
  T005; T008 after T003; T009 after T005+T006 (asserts their anchors).
- **US2 (Phase 4)**: T010 after T003 (cites schemas); T011 after T010; T012 after
  T010 and T009 (extends the module).
- **US3 (Phase 5)**: T013 after T003; T014 after T013, T011, T012 (extends both
  modules).
- **US4 (Phase 6)**: T015/T016/T017 parallel after T003; T018 after all three + T014.
- **US5 (Phase 7)**: T019 after T005 (same file, sequential); T020 after T019
  (simulates its documented write); T021 after T019 + T018.
- **Polish**: T022 after T021 (module chain) + all docs; T023/T024 parallel anytime
  after Phase 7; T025 last.

**Serialization note**: T001 → T005 → T019 edit `SKILL.md`;
T009 → T012 → T014 → T018 → T021 → T022 edit `test_investigation_prose.py`;
T011 → T014 → T018 edit `test_agent_toolsets.py` — each chain is always sequential,
never parallel-dispatched.

## Parallel Example: User Story 4

```text
After Phase 2 (and US3's checkpoint for the dispatch-section anchors):
  T015 log-diver.md  |  T016 deploy-analyst.md  |  T017 dependency-checker.md   (3 files, no deps)
then T018 extends both test modules serially.
```

## Implementation Strategy

**MVP = US1 + US2 + US3** (all P1): Phases 1–5, verify green, then US4/US5 land as
independent increments with their own green seams. Commit at every checkpoint;
tasks.md ticks are the orchestrator's acceptance record (verify gate + adjudicated
review), not the implementer's self-report.
