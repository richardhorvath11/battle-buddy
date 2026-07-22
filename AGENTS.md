# AGENTS.md

_Last Verified: 2026-07-21_

Single source of truth for any coding agent in this repo. Read this end-to-end before
touching anything; it routes — it does not restate. Tool-specific overlays (`CLAUDE.md`)
only add narrow extras on top.

## What this is

**battle-buddy** — an open-source on-call agent harness: a Claude Code plugin that gives
responders agent-led incident investigation with compounding institutional memory.
**Status: slices 1–7 and 9 landed** (see Build order below). Shipped plugin surfaces so far:
`bin/` (`bb-fingerprint`, `bb-validate`, `bb-shell` + its interface docs), `hooks/` (guardrails), `commands/` (`/doctor`,
`/setup`, `/page`, `/incident`, `/close`), `agents/` (triage, deep investigator, three
specialists), `manifest/capabilities.json`, `skills/session-store`, `skills/investigation`,
`skills/catalog`, `templates/`. Dev-only,
never shipped: `tools/bb-mock-mcp`, `tests/`, `pyproject.toml`.

## Source documents (read in this order for context)

| Document | Role |
|---|---|
| `.specify/memory/constitution.md` | **The rules no slice may break.** Principles I–VIII, platform constraints, governance. Constitution supersedes everything, including this file |
| `bb-technical-design.md` | The system: architecture, components, data design, decisions D-1…D-21, testing strategy (§10) |
| `oncall-harness-requirements.md` | PRD v0.9 — what the product is and why |
| `bb-*.mermaid` | System/data, session sequence, agent dispatch diagrams (embedded in the design doc) |
| `specs/` | Per-slice specs — each vertical slice gets spec → plan → tasks → implement |

Traceability runs **PRD FR → design § → slice spec → code + tests**.

## Commands

```bash
make verify          # THE gate: hermetic unit + contract test layers (design §10)
make test-unit       # layer 1 only: hooks/helpers as pure functions
make test-contract   # layer 2 only: against bb-mock-mcp
pytest tests/contract/test_doctor_checks.py -q            # single file
pytest tests/unit/test_validate.py::test_name -q          # single test
```

CI (`.github/workflows/verify.yml`) invokes the same make targets — unit on py3.9
(shipped-code floor, design D-1) and py3.12, contract on py3.12 only. Shared test flow
helpers live in `tests/helpers/`; contract fixtures under `tests/fixtures/`.

Spec-kit drives feature flow: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` →
`/speckit-implement` (optional: `/speckit-clarify`, `/speckit-analyze`, `/speckit-checklist`).

## Pre-flight gate

**Before claiming a task done, before `git commit`, before `git push`: run `make verify`
and fix what it surfaces.** Constitution Principle VIII makes this non-negotiable; code
without its tests in the same change is incomplete. Bypasses require an inline,
grep-visible reason variable (a PreToolUse push-gate enforcing this mechanically is a
planned dev-workflow addition — deliberately separate from the deterministic-layer
slice's *runtime* guardrails, which block outright with no bypass; see slice-2 spec
Assumptions).

## Path tiers

| Tier | Paths | Notes |
|---|---|---|
| **Allowed** | plugin dirs (`commands/`, `skills/`, `hooks/`, `bin/`, `manifest/`, `templates/`, future `agents/`), `tests/`, `tools/`, docs, `specs/**` | Default. Still subject to the constitution |
| **Restricted** (call it out in the PR) | `.specify/memory/constitution.md` (semver bump + Sync Impact Report per Governance); `Makefile`; `.claude/settings.json`; `.specify/templates/*` | Governance and gate surface — change deliberately |
| **Upstream-managed** | `.specify/scripts/**`, `.specify/extensions/**`, `.claude/skills/speckit-*` | spec-kit vendored files; update via `specify` upgrades, don't hand-edit |

## Build order (design §1) and slice map

Spike 0 (Google roster conformance) → **slice 1** test scaffold + `bb-mock-mcp` (✅) →
**2** deterministic layer (hooks + `bb-fingerprint` + `bb-validate`) (✅) → **3**
session-store conventions (✅) → **4** `/doctor` + `/setup` (✅) → **5** lifecycle
commands (✅) → **6** agent model + investigation skill (✅) → **7** catalog adapter (✅) →
**8** diary adapter → **9** shell adapter (`bb-shell` + cmux) (✅). Slices 7–9 parallelize
once 1–2 exist. Each slice cites its design sections in its spec; landed slices live
under `specs/00N-*/`.

## Hard invariants

Live in the constitution — deliberately not restated here (one source of truth per rule).
The ones agents trip over most: evidence entries are `{url, excerpt}` pairs, never prose
alone (IV); causal fields are human-curated proposals (V); recalled memory is hypotheses
requiring VALIDATED/INVALIDATED (VI); skills reference capabilities/operations, never
concrete MCP tool names (VII); shipped code is Python 3 stdlib only (Platform Constraints).

## Forbidden ops

- Shipping storage code, a server, or a bespoke per-tool integration in tier 0
  (Constitution I) without a recorded scope decision.
- Hardcoding an MCP server or tool name in a skill/command (Constitution VII).
- Claiming a security guarantee that rests on a probabilistic layer (Constitution III).
- Committing component code without its tests in the same change (Constitution VIII).
- Editing upstream-managed spec-kit files by hand (see Path tiers).
- `git push --force`, pushing directly to `main` once PRs exist, `rm -rf` outside
  scratch — also denied mechanically in `.claude/settings.json`.

## Workflow notes

- **One flow driver per feature: spec-kit.** Where spec-kit owns the flow
  (specify → plan → tasks → implement), other process frameworks (e.g. superpowers
  brainstorming/writing-plans) stand down. Use them only for work outside the slice flow.
- Hard-to-reverse decisions amend the design doc's decision log (§11) in the same PR.
- Keep this file ≤200 lines; it routes, the linked documents rule.
