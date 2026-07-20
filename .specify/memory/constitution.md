<!--
Sync Impact Report
- Version change: 1.0.0 → 1.0.1 (PATCH: corrected slice-spec location from `.specify/` to
  `specs/` — spec-kit's actual scaffold layout; PR #1 review finding)
- Previous: (template) → 1.0.0 (initial ratification)
- Modified principles: n/a (initial adoption)
- Added sections: Core Principles (I–VIII), Platform Constraints, Development Workflow, Governance
- Removed sections: none
- Templates requiring updates:
  ✅ .specify/templates/plan-template.md — generic "Constitution Check" gate; compatible, gates derive from this file
  ✅ .specify/templates/spec-template.md — no constitution-specific slots; compatible
  ✅ .specify/templates/tasks-template.md — test-first task ordering aligns with Principle VIII
- Follow-up TODOs: none
- Source documents: oncall-harness-requirements.md (PRD v0.9), bb-technical-design.md (design v1.2)
-->

# battle-buddy Constitution

battle-buddy is an open-source on-call agent harness: a Claude Code plugin that gives
responders agent-led investigation with compounding institutional memory. These principles
bind every spec, plan, and implementation in this repository. The PRD
(`oncall-harness-requirements.md`) defines what the product is; the technical design
(`bb-technical-design.md`) defines the system; this constitution defines the rules no
slice may break.

## Core Principles

### I. One Custom Component

The only shipped software is the Claude Code plugin: commands, agents, skills, hooks, and
small helper scripts. Tier 0 ships **no server, no database, and no bespoke per-tool
integration code** — storage is documented conventions over the team's own Google
workspace, accessed through MCPs the team brings. Adding shipped infrastructure (e.g. the
vendored-MCP contingency of design D-21, or the tier-1 server) requires an explicit,
recorded scope decision — never an implementation convenience.

### II. Conventions With Deterministic Backstops

Model-followed conventions carry the behavior; **every must-not-fail invariant gets a
deterministic backstop** — a hook, validator, or read-back check that verifies the work
landed (design D-11, D-12, D-14, D-17). Trust the model to do the work; verify the work
landed with code. The session record write is the canonical case: convention-driven, but
its absence MUST be detected mechanically, never merely hoped against. A skill instruction
alone is not enforcement.

### III. Safety Through Layered Guardrails (NON-NEGOTIABLE)

Five layers, honestly weighted (design §3.5, §8): (1) deterministic PreToolUse deny layer;
(2) read-only credential defaults; (3) human approval gates on every mutating action;
(4) injection mitigation — explicitly probabilistic, never claimed as a guarantee;
(5) transcript as audit log. Security *guarantees* may rest only on the deterministic
layers (1–3). Untrusted telemetry is data, not instructions. Guardrail hooks fail open
(a broken gate must never brick a session) and over-match toward catching real events.
Documented real-world agentic misbehaviors are regression tests.

### IV. Evidence Is Links Plus Excerpts

Every factual claim, hypothesis evidence entry, and verdict citation stores a
URL-addressable reference (dashboard + time window, search query URL, commit/PR, alert)
**plus a short excerpt** — never prose summary alone (FR-4e). This is what makes session
reports regenerable from persisted data at any later time and evidence deep-linking
possible after the fact. Prose-only evidence is invalid by schema.

### V. Causal Fields Are Human-Curated

Auto-drafts fill factual fields only (timeline, links, metrics, who/what/when). Causal
fields — root cause, contributing factors, action items — are always explicitly-labeled
proposals requiring human curation (FR-8), in diary entries, comms, reports, and the
session record alike. Hallucination concentrates in causal analysis; no feature may
promote a causal proposal to fact without a human decision.

### VI. Validated Memory (headline product behavior)

Recalled sessions and triage output are **hypotheses, never conclusions**. Every ledger
hypothesis carries a provenance tag (`triage` | `recall` | `fresh`); every non-`fresh`
hypothesis MUST be marked VALIDATED or INVALIDATED against fresh evidence from the current
incident before being acted on (FR-5d). The anchoring guard holds: ≥3 live hypotheses
before deep-diving any one, at least one `fresh` (FR-5e). These invariants are enforced by
`bb-validate`, not by convention (Principle II applies).

### VII. Capability Contracts Over Tool Names

Skills and commands reference **capabilities and operations** ("your storage tool's
append_record"), never concrete MCP server or tool names (FR-25a, design §7). The
operation contract is the published integration spec; `/doctor` is its conformance test;
the binding map is the integration artifact. The recommended roster is a default binding
with zero architectural privilege. Any conforming MCP — including a team's in-house
wrapper — slots in with no battle-buddy changes.

### VIII. Test-First, Agent-Led (NON-NEGOTIABLE)

The test scaffold precedes component code, and the two hermetic layers gate every commit:
unit tests over hooks/helpers as pure `(stdin, state) → (exit code, output)` functions,
and contract tests against `bb-mock-mcp` (design §10). Agent-behavior checks assert on
**artifacts, never prose** — validated checkpoints, correct fingerprints, write ordering.
In agent-led development the test suite is the standing guardrail that keeps agent-written
changes honest; code without its tests in the same change is incomplete.

## Platform Constraints

- **Shipped code is Python 3 stdlib only** (hooks, `bb-*` helpers) — no runtime install
  step on a responder's machine (design D-1; NFR-4). Dev-only tooling (pytest, mock MCP)
  is exempt.
- **Per-responder credentials, read-only by default.** Google access via each responder's
  own OAuth; agent MCP tokens default to viewer roles; the harness never touches the
  responder's SSO sessions (FR-24). No service accounts in tier 0.
- **Data ownership**: all incident data lives in the adopter's own workspace and git; the
  project ships no hosted dependency (NFR-5).
- **Deployment model**: plugin (upstream, marketplace-updated) vs. team workspace repo
  (private, scaffolded by `/setup`, never a fork; zero upstream content) — the seam is
  versioned and policed by `/doctor` (design §2.1, D-16).
- **Degraded mode is a first-class path**: every feature works in a plain terminal with
  links printed (FR-26); the shell adapter is an enhancement, never a requirement.

## Development Workflow

- **The design doc is upstream; specs correlate to code.** `bb-technical-design.md` is the
  architectural reference. Each vertical slice gets its own spec under `specs/`
  (spec → plan → tasks → implement), citing the design sections it implements and carrying
  its own acceptance criteria. Traceability runs PRD FR → design § → slice spec → code +
  tests.
- **Verify before claiming done.** A single verify command (unit + contract layers) MUST
  pass before any commit is described as complete and before any push. Bypasses require an
  inline, grep-visible reason variable — auditable in the transcript.
- **Decisions are recorded.** Hard-to-reverse choices amend the design doc's decision log
  (§11) or an ADR in the same change; scope-vs-correctness tradeoffs are surfaced
  explicitly, never silently shipped.
- **Small, reviewable changes.** One slice → one spec → small stacked PRs; each stands on
  its own with tests green.

## Governance

This constitution supersedes all other practices in this repository. The plan-phase
"Constitution Check" gates every slice against the principles above; violations must be
justified in the plan's Complexity Tracking section or the plan is rejected.

Amendments are made by PR editing this file: MAJOR for principle removals or
redefinitions, MINOR for new principles or materially expanded guidance, PATCH for
clarifications. Every amendment updates the Sync Impact Report comment and re-validates
the dependent templates. Compliance is reviewed at spec review and PR review; the
guardrail and validator test suites are the mechanical arm of that review.

Runtime agent guidance lives in `CLAUDE.md` (and `AGENTS.md` once adopted); those files
route — this file rules.

**Version**: 1.0.1 | **Ratified**: 2026-07-19 | **Last Amended**: 2026-07-19
