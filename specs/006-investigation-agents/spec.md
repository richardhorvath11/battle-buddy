# Feature Specification: Investigation Agents & Skill

**Feature Branch**: `006-investigation-agents`

**Created**: 2026-07-20

**Status**: Draft

**Input**: Slice 6 of the battle-buddy MVP (design `bb-technical-design.md` §3.3, §3.4, §3.5 layer 4, §5.4; decisions D-6, D-14, D-17, D-20; PRD FR-4e, FR-5–5f, SM-4; Constitution IV, V, VI, VII): the two-speed investigation core — the triage subagent, the deep investigator, the specialist fan-out, and the investigation skill that carries the methodology — expressed as agent and skill prose plus hermetic tests over the artifacts the prose commits to (schema documents, role registration, validator agreement). Agent *behavior* is scenario-harness territory (design §10 on-demand layer), deliberately outside CI scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recalled memory is a hypothesis, never a conclusion (Priority: P1)

Every agent that touches recalled sessions or triage candidates works under the investigation skill's top-priority instruction: recalled sessions and triage output are hypotheses. Every hypothesis carries a provenance tag (`triage` | `recall` | `fresh`), and every non-`fresh` hypothesis must be marked VALIDATED or INVALIDATED against evidence gathered from the *current* incident before being acted on. The anchoring guard holds: at least three live hypotheses before deep-diving any one, at least one of them `fresh`. These invariants are enforced by the slice-2 validator at every checkpoint write — the skill instructs, the validator verifies.

**Why this priority**: This is the product's headline behavior (Constitution VI, SM-4) — memory that compounds without anchoring the responder on a stale match. Everything else in the slice serves it. P1.

**Independent Test**: The skill's documented invariants and the validator's accepted rules are the same rules: every worked example in the schemas reference (valid ledgers, anchoring-guard states, provenance/validation combinations) is classified by the slice-2 validator exactly as the document says — documented-valid passes, documented-invalid fails with the documented rule named.

**Acceptance Scenarios**:

1. **Given** the investigation skill document, **When** its instruction order is inspected, **Then** the validation discipline is the top-priority instruction, ahead of all methodology — not a footnote. *(§3.3 "leads the skill"; FR-5d; SM-4)*
2. **Given** a documented ledger example with a non-`fresh` hypothesis lacking VALIDATED/INVALIDATED, **When** the validator runs, **Then** it fails naming the validation rule — matching the skill's stated invariant. *(§5.4; Constitution VI; slice-2 validator)*
3. **Given** a documented deep-dive-phase ledger with fewer than three live hypotheses or none `fresh`, **When** the validator runs, **Then** it fails on the anchoring guard — the skill's guard and the validator's rule agree. *(§3.4, FR-5e; §5.4)*
4. **Given** any evidence entry in any documented example, **When** inspected, **Then** it is a `{url, excerpt}` pair — prose-only evidence appears only in documented-invalid examples. *(FR-4e; Constitution IV)*

---

### User Story 2 - Triage answers four questions fast, and is honest when it can't (Priority: P1)

The triage agent definition pins: a fast/cheap model class (configurable), a ≤2-minute wall-clock target with a capped turn budget (default 15 — documented in the agent definition, *enforced* by the slice-2 hook; wall-clock is measured and reported in the verdict's budget field, never enforced), a read-only narrow toolset named by capability (alerting, catalog/code reads, session-store reads, observability reads), and the four fixed questions: Known? (fingerprint + keyword recall) Real? (flap history) What changed? (deploy window) Who's affected? (metrics + dependencies). Output is a structured verdict (`bb.verdict.v1`) where "no strong signal" is an honest, first-class answer — and a budget-truncated verdict automatically satisfies the no-strong-signal launch condition for deep investigation. On new alerts mid-session, triage re-invokes to classify related-to-current vs separate.

**Why this priority**: Triage is the NFR-1 path — every session starts here. Co-P1.

**Independent Test**: The agent definition document is inspected against its pinned properties (model class configurable, budget documented with enforcement attributed to the hook, toolset capability-named, four questions present, verdict schema named, no-strong-signal legitimized, re-invocation defined); the verdict examples it references validate under `bb.verdict.v1`.

**Acceptance Scenarios**:

1. **Given** the triage agent definition, **When** inspected, **Then** the turn cap documents the default (15), names its configuration key, and attributes enforcement to the deterministic layer — the definition never claims to self-enforce. *(§3.4 triage table, D-17; local-state protocol config keys)*
2. **Given** the toolset section, **When** inspected, **Then** every tool grant is expressed as a capability/operation, read-only, with no concrete server or tool names. *(§3.4; Constitution VII)*
3. **Given** the verdict contract, **When** a budget-truncated or no-signal verdict is produced, **Then** the definition marks it as satisfying FR-5f(a) — no separate signal invented; the verdict's own `no_strong_signal`/`budget_spent` fields carry it. *(§3.4, D-17; §5.4)*
4. **Given** a new alert mid-session, **When** triage re-invokes, **Then** its charter is classification — related-to-current vs separate — without disturbing a running deep investigation. *(FR-5a, §4 mid-session)*

---

### User Story 3 - Deep investigation owns the ledger; the orchestrator stays thin (Priority: P1)

The deep investigator definition pins: a frontier model class, open budget, wide toolset with every mutation approval-gated, ownership of the hypothesis ledger and synthesis. Specialist findings return to the ledger, never to the orchestrator; only ledger updates flow up. The ledger seeds from the triage verdict (provenance `triage`, unvalidated), must gain at least one `fresh` hypothesis before any deep dive, and is checkpointed to the session store on every update through the slice-3 conventions with the slice-2 validator gating every write.

**Why this priority**: The ledger is where validated memory becomes investigation (FR-5b–5e); the thin-orchestrator rule is what keeps long incidents from drowning the conversational context. P1.

**Independent Test**: The deep-investigator definition is inspected for its pinned properties (ledger ownership, checkpoint-on-every-update citing slice-3 conventions and the validator gate, seed-from-verdict with `triage` provenance, ≥1-`fresh`-before-deep-dive, ledger-updates-only reporting); its ledger examples validate under `bb.ledger.v1`, including the seeded-from-triage state.

**Acceptance Scenarios**:

1. **Given** the deep-investigator definition, **When** inspected, **Then** every checkpoint write cites the validation gate (one re-prompt, then persist flagged) and the slice-3 write conventions — never a direct unvalidated write. *(§3.4, §5.4, D-14; slice-3 FR-005/FR-006)*
2. **Given** the seeding rule, **When** the ledger initializes from a triage verdict, **Then** candidates enter with provenance `triage`, unvalidated, and the definition requires ≥1 `fresh` hypothesis before deep-diving any candidate. *(§3.4; FR-5e)*
3. **Given** the reporting rule, **When** specialists return findings, **Then** they merge into the ledger and only ledger updates reach the orchestrator — the definition forbids relaying raw findings upward. *(§3.4, FR-5b)*
4. **Given** the toolset, **When** inspected, **Then** mutations are marked approval-gated (the guardrail layers stay between the agent and any change) and reads are capability-named. *(§3.4, §3.5; Constitution VII)*

---

### User Story 4 - Specialists dig in parallel and report evidence, not vibes (Priority: P2)

Three specialist definitions — log-diver, deploy-analyst, dependency-checker — each pin: single purpose, read-only capability-named toolset, parallel dispatch by the deep investigator, and a findings-summary return contract where every finding carries `{url, excerpt}` evidence. Findings go to the deep investigator's ledger, never to the orchestrator or responder directly. Agent-teams mode is recorded as a future opt-in fan-out upgrade — no design work in this slice.

**Why this priority**: Specialists widen the evidence net but ride US3's machinery. P2.

**Independent Test**: Each specialist definition is inspected for the four pinned properties; their example findings entries are `{url, excerpt}`-shaped and validate wherever the ledger schema embeds them.

**Acceptance Scenarios**:

1. **Given** any specialist definition, **When** inspected, **Then** it is single-purpose, read-only, capability-named, and returns findings to the deep investigator only. *(§3.4; Constitution VII)*
2. **Given** a specialist findings contract, **When** inspected, **Then** every finding requires `{url, excerpt}` evidence — prose-only findings are non-conforming. *(§3.4, FR-4e; Constitution IV)*
3. **Given** the agent-teams note, **When** inspected, **Then** it is a future-work marker (opt-in, once stable) with no normative design content. *(§3.4)*

---

### User Story 5 - The right speed launches at the right time, and every agent is accountable (Priority: P2)

The skill pins the deep-investigation launch conditions (FR-5f): (a) triage returns no strong signal or recommends escalation; (b) the responder requests it — `/incident` promotion always launches it; (c) a triage-recommended fix fails verification. The orchestrator proposes, the responder confirms; the auto-launch configuration flag covers incident-severity sessions. And every spawn registers the agent's role: the spawn flow writes the actor-key → role entry (`triage` | `deep` | `specialist:<name>`) per the slice-2 local-state protocol — the skill provides role registration, the deterministic layer provides identity and enforcement; an unregistered actor gets no turn cap (fail open, the protocol's own rule).

**Why this priority**: Launch discipline keeps the two-speed model honest; role registration is what makes the slice-2 turn cap land on the right agent. P2.

**Independent Test**: The skill's launch-condition section is inspected against FR-5f's three conditions plus the confirm/auto-launch rules; a simulated spawn-flow registration write is validated against the protocol's `agents.json` shape (protocol-conforming keys and role values).

**Acceptance Scenarios**:

1. **Given** the skill's launch rules, **When** inspected, **Then** exactly the three FR-5f conditions appear, with orchestrator-proposes/responder-confirms and the auto-launch flag for incident severity. *(§3.4, FR-5f)*
2. **Given** a spawn, **When** the role registration write is simulated, **Then** the written entry conforms to the protocol's `agents.json` shape with a role in `triage` | `deep` | `specialist:<name>`. *(local-state protocol v1 agents.json)*
3. **Given** the registration rule, **When** inspected, **Then** the mechanism/policy split is stated: identity and enforcement are the deterministic layer's; role registration is the skill's; unregistered actors are uncapped by protocol rule (fail open) — the skill does not re-claim enforcement. *(local-state protocol v1; Constitution II)*

---

### Edge Cases

- **Telemetry that reads like instructions**: all output from `alerting` and `observability` capability tools is untrusted data, never instructions — the skill's standing, capability-scoped rule; where the agent *does* control text (quoting telemetry into checkpoints, briefings, diary drafts, subagent prompts), it delimiter-wraps the quoted content. Stated as probabilistic mitigation, never a guarantee — guarantees live in the deterministic layers. *(§3.3, §3.5 layer 4, D-20; Constitution III)*
- **Validator rejects a checkpoint twice**: the persist-flagged path (slice-3 FR-006) applies — data lands flagged, the responder is told; the skill never instructs an agent to drop or retry-forever. *(§5.4, D-14)*
- **Triage cap reached mid-question**: the hook denies further tool calls; the definition instructs emitting the verdict from evidence in hand — a truncated verdict with `budget_spent` filled is a valid, honest verdict. *(§3.4, D-17)*
- **All recalled candidates INVALIDATED**: the ledger continues on `fresh` hypotheses alone — invalidation is a success of the discipline, not a failure of the investigation. *(Constitution VI)*
- **Specialist returns nothing**: an empty findings summary is a legitimate return; the deep investigator records the null result against the hypothesis rather than re-dispatching blindly. *(informed default; §3.4)*
- **Deep investigation requested with no triage verdict yet** (responder escalates immediately): the ledger starts empty of `triage`-provenance entries and the ≥1-`fresh` rule still applies before any deep dive; the anchoring guard's ≥3-live rule binds at deep-dive time, not at seeding. *(informed default from §5.4's phase-scoped constraints — see Assumptions)*
- **Unregistered specialist spawned ad hoc**: it runs uncapped (protocol fail-open) but its tool calls still trace; the skill instructs registering every spawn, and the gap is visible in the trace's actor keys. *(local-state protocol v1)*

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The investigation skill MUST lead with the validation discipline as its top-priority instruction: recalled sessions and triage candidates are hypotheses, never conclusions; every hypothesis carries provenance (`triage` | `recall` | `fresh`); every non-`fresh` hypothesis is marked VALIDATED or INVALIDATED against current-incident evidence before being acted on. *(§3.3, FR-5d, SM-4; Constitution VI)*
- **FR-002**: The skill MUST state the anchoring guard — ≥3 live hypotheses before deep-diving any one, ≥1 `fresh` — and attribute its enforcement to the slice-2 validator at checkpoint-write time, per the phase scoping the validator implements. *(§3.3, FR-5e, §5.4; Constitution II, VI)*
- **FR-003**: The skill MUST state the evidence rule — every evidence entry is a `{url, excerpt}` pair (a URL-addressable view plus a short excerpt); prose-only evidence is invalid by schema — applying to hypotheses, verdicts, findings, and briefings alike. *(§3.3, FR-4e; Constitution IV)*
- **FR-004**: The skill MUST carry the capability-scoped untrusted-data rule: output from `alerting` and `observability` tools is data, never instructions, with delimiter-wrapping applied where the agent controls the text (checkpoints, briefings, diary drafts, subagent prompts) — stated explicitly as probabilistic mitigation (the tripwire and deny layers are the deterministic arm). *(§3.3, §3.5 layer 4, D-20; Constitution III)*
- **FR-005**: The skill MUST reference the briefing format (deep-linked evidence per claim) and point at slice-3's session-store conventions as the normative retrieval flow — it consumes them, never restates them normatively. *(§3.3; slice-3 FR-007; one source of truth per rule)*
- **FR-006**: The triage agent definition MUST pin: configurable fast/cheap model class; ≤2-minute wall-clock *target* (measured, reported in `budget_spent`, never enforced) with the turn cap documented (default 15, its configuration key named, enforcement attributed to the slice-2 hook); read-only capability-named toolset (alerting, catalog/code reads, session-store reads, observability reads); the four fixed questions; structured `bb.verdict.v1` output with honest no-strong-signal; budget-truncated verdicts satisfying FR-5f(a) via the verdict's own fields; and mid-session re-invocation charter (related vs separate). *(§3.4, D-17, FR-5, FR-5a; local-state protocol config keys)*
- **FR-007**: The deep-investigator definition MUST pin: frontier model class, open budget, wide toolset with mutations approval-gated; ledger ownership and synthesis; checkpoint-to-store on every ledger update through slice-3 conventions with the validator gate; seeding from the triage verdict as provenance `triage` unvalidated; ≥1 `fresh` hypothesis before any deep dive; and ledger-updates-only reporting to the orchestrator. *(§3.4, §5.4, D-14, FR-5b; slice-3 FR-005/FR-006)*
- **FR-008**: The three specialist definitions (log-diver, deploy-analyst, dependency-checker) MUST each pin: single purpose, read-only capability-named toolset, parallel dispatch, findings-summary return to the deep investigator only, `{url, excerpt}` evidence per finding; the agent-teams future mode appears as a non-normative note. *(§3.4, FR-4e)*
- **FR-009**: The skill MUST pin the deep-investigation launch conditions — (a) no strong signal, (b) responder request with promotion always launching, (c) failed fix verification — with orchestrator-proposes/responder-confirms and the auto-launch configuration flag for incident severity; the orchestrator ingests ledger updates only, never raw findings. *(§3.4, FR-5f, FR-5b)*
- **FR-010**: The skill's spawn flow MUST register every agent's role — actor-key → `triage` | `deep` | `specialist:<name>` — in the protocol's registration file at spawn time, stating the mechanism/policy split: the deterministic layer owns identity and enforcement (unregistered = uncapped, fail open, the protocol's rule); the skill owns registration. *(local-state protocol v1 agents.json; Constitution II)*
- **FR-011**: The schemas reference MUST document `bb.verdict.v1` and `bb.ledger.v1` as the normative schema statement — field sets, provenance/validation vocabularies, phase-scoped invariants, evidence shape — in the same normative-doc-to-tool relationship slice 3 pinned for the fingerprint: the slice-2 validator is the implementation, its fixture corpus the executable form, and a consistency check ties them. *(§5.4, D-6; slice-3 FR-003 precedent)*
- **FR-012**: Hermetic tests MUST cover: every documented schema example classified by the slice-2 validator exactly as documented (valid passes; each documented-invalid fails naming the documented rule); role-registration writes conforming to the protocol's `agents.json` shape; and the anchoring-guard states (deep-dive phase with 2 live / 3 live no fresh / 3 live with fresh) classified correctly — asserting on artifacts, never prose, no credentials, no network. Agent behavior itself (does triage actually answer in 2 minutes, does the ledger actually validate recalled candidates) is scenario-harness territory (design §10 on-demand layer), explicitly out of CI scope. *(design §10; Constitution VIII)*
- **FR-013**: All agent and skill prose MUST reference capabilities and operations only — no concrete MCP server or tool names anywhere in the deliverables. *(Constitution VII)*
- **FR-014**: This slice ships prose and tests only — no code beyond tests; the validator, hooks, and store conventions it consumes are slices 2 and 3. *(Constitution I)*

### Key Entities

- **Investigation skill**: The methodology document — validation discipline first, anchoring guard, evidence rules, untrusted-data rule, launch conditions, spawn/role registration.
- **Agent definitions**: Five prose documents (triage, deep investigator, three specialists) pinning model class, budget, toolset-by-capability, and contracts.
- **Hypothesis ledger**: The deep investigator's working state (`bb.ledger.v1`) — provenance-tagged, validation-marked, checkpointed via slice-3 conventions.
- **Structured verdict**: Triage output (`bb.verdict.v1`) — candidates, confidence, severity, validation marks, budget fields, honest no-signal.
- **Schemas reference**: The normative documentation of both schemas; the slice-2 validator is its implementation, the validator's fixtures its executable form.
- **Role registration entry**: The spawn-time actor-key → role write into the protocol's registration file; the deterministic layer's mapping from actor to budget policy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every functional requirement maps to at least one passing hermetic test (document-property inspection, validator classification, or protocol-shape conformance); the suite is green on every commit via the standard verify gate.
- **SC-002**: 100% of the schemas reference's documented-valid examples pass the slice-2 validator unmodified; 100% of documented-invalid examples fail naming the documented rule — zero disagreements between the normative doc and the validator.
- **SC-003**: 100% of simulated spawn registrations produce protocol-conforming `agents.json` entries; a seeded non-conforming role value is rejected by the shape check.
- **SC-004**: The anchoring-guard state matrix (deep-dive phase × {2 live, 3 live no fresh, 3 live with fresh, dead fresh}) classifies 100% correctly under the validator — the skill's stated guard and the enforced guard are the same guard.
- **SC-005**: Zero concrete MCP server or tool names across all seven prose deliverables, verified mechanically (the same scan discipline as the constitution's forbidden-ops list).
- **SC-006**: Every capability named in any agent toolset appears in the capability manifest's required or optional set — no toolset references a capability the system doesn't declare.

## Assumptions

- **Slice dependencies**: slice 2 (validator, hooks, protocol) is merged; slice 3 (store conventions) is merged; slices 4 and 5 are authored on open PRs (#9, #10) — this spec cites their pins where relevant and declares the dependency status. The orchestration steps that *invoke* these agents (spawn points, verdict persistence) are slice 5's; this slice defines the agents and methodology being invoked.
- **Anchoring-guard timing** (immediate-escalation edge case): the ≥3-live/≥1-fresh rules bind at deep-dive time via the ledger's phase field — the validator's phase-scoped implementation (slice 2) — so an empty-seeded ledger is legal in evidence-gathering phase. Informed default consistent with the validator's existing fixture corpus; the design states the guard without the empty-seed case.
- **Turn-cap configuration key** is the local-state protocol's documented budget key with its documented default (15); the agent definition names it, never redefines it.
- **Specialist findings embedding**: findings summaries returned to the deep investigator are working input, not a persisted schema of their own in v1 — they become ledger evidence entries (`{url, excerpt}`) on merge; a dedicated findings schema is future work if the scenario harness shows drift.
- **Model-class configuration**: "fast/cheap" and "frontier" are configurable class defaults, not pinned model IDs — teams override via workspace configuration; the definitions state the class rationale (budget vs depth).
- **SC-006's manifest cross-check** binds against slice-4's capability manifest (PR #9, unmerged): the test lands with whichever of the two slices merges second — the cross-slice sequencing is a plan-time task-ordering concern, declared here.
- **Briefing format details** (section order, wording) live in the skill's briefing reference and are presentation guidance; the spec pins only the testable property — every claim deep-linked with `{url, excerpt}` evidence.
