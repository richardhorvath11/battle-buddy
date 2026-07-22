# Investigation Retrieval Reference (pointer)

Normative for the `investigation` skill (FR-005). This is a **pointer**, not a second
copy: `skills/session-store/references/retrieval.md` is the normative home of the
three-stage tier-0 retrieval flow (fingerprint exact-match → keyword overlap → capped
agent-ranked candidates, plus its exclusions and downgrade rule). Read it there — this
document restates none of it (one source of truth per rule).

## What an investigation agent consumes from it

The candidate session rows that retrieval surfaces enter an investigation as
**`recall`-provenance hypotheses** — never as conclusions. From there they are subject
to this skill's validation discipline exactly like any other non-`fresh` hypothesis:
each one must be marked `VALIDATED` or `INVALIDATED` against evidence gathered from the
current incident before it is acted on. Retrieval's own `classification`
(`"known_issue"` vs `"candidate"`) informs how strong a starting signal a row is —
it is not itself the validation mark.
