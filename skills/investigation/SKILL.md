---
name: investigation
description: Use when conducting any incident investigation — triage, deep investigation, or specialist dispatch. Documents the investigation methodology: validation discipline, the phase-scoped anchoring guard, evidence rules, untrusted-telemetry handling, launch conditions for deep investigation, and spawn-time role registration.
---

# Investigation

## Overview

This skill is the methodology core of every incident investigation. It is loaded by
the orchestrator and by both investigation agents (triage, deep investigator) —
**one skill, different budgets and toolsets per role** (FR-001, FR-5c). Nothing in
this skill's prose is role-specific; a role's budget, model class, and capability
toolset live in its own agent definition and constrain how much of this methodology
that role exercises, never what the methodology says.

## References

| Reference | Covers |
|---|---|
| `references/schemas.md` | The normative `bb.verdict.v1` (triage) and `bb.ledger.v1` (deep-investigation) schemas — field sets, provenance/validation vocabularies, phase-scoped invariants, evidence shape, worked examples |
| `references/briefing.md` | The briefing format — deep-linked evidence per claim — and the causal-field discipline (root-cause and contributing-factor statements are proposals, never fact, without a human decision) |
| `references/retrieval.md` | Pointer to the session-store skill's normative retrieval flow — this skill consumes it, never restates it |

## Validation discipline

*(filled by a later task in this slice)*

## Anchoring guard

*(filled by a later task in this slice)*

## Evidence rules

*(filled by a later task in this slice)*

## Untrusted telemetry

*(filled by a later task in this slice)*

## Launch conditions for deep investigation

*(filled by a later task in this slice)*

## Spawn flow and role registration

*(filled by a later task in this slice)*
