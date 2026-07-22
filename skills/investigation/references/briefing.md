# Investigation Briefing Reference

Normative for the `investigation` skill (FR-005). This document covers the briefing
the orchestrator relays to the responder — at session open, and again whenever
triage or deep investigation produces a new verdict or ledger update worth surfacing.

## The testable property

**Every claim in a briefing carries a deep-linked `{url, excerpt}` evidence entry** —
the same evidence shape `references/schemas.md` pins for hypotheses and findings
(Constitution IV). A claim with no accompanying evidence entry is non-conforming,
whether the claim is "this matches a known issue," "a deploy touched this service 12
minutes before alert onset," or "the checkout-api dependency is unhealthy." If a
statement can't be backed by a `{url, excerpt}` pair, it isn't a claim the briefing
gets to make yet — it's a hypothesis still being validated, and belongs in the ledger,
not the briefing, until it is.

## Causal-field discipline (Constitution V, FR-8)

Root-cause and contributing-factor statements — in a briefing or in a ledger's own
synthesis — are **explicitly-labeled proposals**, never promoted to fact without a
human decision. Label them as such: "Proposed root cause," "Proposed contributing
factor," never a bare "Root cause:" stated as settled. This holds even when every
supporting hypothesis is `VALIDATED` and confidence is high — validation confirms a
hypothesis held up against current-incident evidence; it does not by itself make the
causal story official. Only a responder's decision does that, and that decision, not
the briefing, is what promotes a proposal to fact.

## Suggested shape (guidance, not mandate)

Section order and exact wording are presentation guidance — the spec pins only the
testable property above and the causal-field discipline. A briefing that satisfies both
in a different order or format is still conforming. One shape that has worked:

1. **Severity + verdict summary** — what triage (or the current ledger phase) found,
   in one or two lines.
2. **Known-issue match, with validation status** — if a recall-provenance candidate
   matched, state its validation mark (`VALIDATED` / `INVALIDATED`) plainly; an
   invalidated match is still worth surfacing as "checked and ruled out," not silently
   dropped.
3. **Candidates, each with its evidence link** — the live hypotheses worth the
   responder's attention, each carrying its `{url, excerpt}`.
4. **Next step** — what happens next (continue triage, launch deep investigation, wait
   on a specific check) and why.

A briefing may add, reorder, or compress these as the incident warrants; what it may
never do is state a claim without evidence or a causal statement without the
proposal label.
