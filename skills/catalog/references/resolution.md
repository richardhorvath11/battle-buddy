# Alert-to-Service Resolution Reference

Normative for the `catalog` skill (FR-003, FR-006; design §6.1, §5.2, D-19). The match
order that turns a firing alert into a resolved service — or, on a miss, into an ask-once
exchange and a fix-up offer — plus the one-hop blast-radius rule. Follow the match order
in the stated sequence; nothing here is a menu of options to reorder.

## The match order (normative)

### 1. Exact stage — `alert_matchers` only

For every service, for every entry in its `alert_matchers`: a hit when the matcher string
equals — case-insensitively, whitespace-trimmed — any of the alert's tags or any of the
alert's field values.

**The service's own `name` is not an exact-stage input.** The name is the substring
stage's input, and only that. A service with an empty `alert_matchers` list therefore
cannot match at the exact stage at all — this is exactly the documented missing-alert-match
degradation, not a separate failure mode.

**An empty matcher never matches anything.** An `alert_matchers` entry that is the empty
string is skipped, not compared. Read literally, "equals any of the alert's field values"
would let an empty matcher match every alert with an empty field — and that is not
hypothetical: a catalog can acquire an empty matcher from a fix-up offer committed for a
sparse alert. A service with `alert_matchers: [""]` would then swallow every sparse alert
in the team's estate. The offer side refuses to produce that (see "The fix-up offer"
below); this rule is the read side of the same guard, and either alone is insufficient.

### 2. Substring stage — runs only if the exact stage matched nothing

For every service: a hit when the **service's name** occurs as a substring of any alert
tag or field value — case-insensitively and whitespace-trimmed, the same normalization
the exact stage applies.

**Direction is pinned**: name-inside-alert-field, never the reverse. An alert field is
never treated as a substring of a service name. The reverse reading would match almost
nothing — alert fields are free text (descriptions, hostnames, summaries) that rarely
appear verbatim inside a short service name, while a service name is far more likely to
turn up as a fragment of a longer alert field.

### 3. Exactness beats substring globally

This is a global rule, not a per-service one: one exact hit **anywhere** in the service
set prevents the substring stage from running at all, even for services whose own
`alert_matchers` didn't produce that hit.

### 4. Ambiguity at either stage

More than one service matching at whichever stage produced a hit surfaces every matching
candidate for an explicit choice — **never a silent pick**. Candidates are ordered by
source path, which is what makes the presentation deterministic across repeated runs of
the same catalog and alert.

### 5. Miss

Nothing matched at either stage → the ask-once path (below).

### Consequence worth stating plainly

A matcher-less service is unresolvable at the exact stage, but the substring stage may
still resolve it when the alert happens to spell the service's name in one of its fields.
The "no alert-match ⇒ ask-once" degradation is a claim about the *matcher* path
specifically — it is not a claim that every matcher-less service always misses.

## The miss path

On a miss, the responder is asked to name the service **once**. The answer feeds the
session-store slice's fingerprint resolution ladder at rung 2, and the session record
carries `catalog_resolved: false`, which downgrades match confidence downstream.
`skills/session-store/` is the normative home of both the ladder and that flag — this
document consumes them and does not restate their behavior.

The ask-once **interaction** itself — prompting the responder and capturing the answer —
is executed by slice 5's lifecycle command. This document defines the rule
that a miss triggers exactly one ask, and the content of the fix-up offer that
accompanies it; it does not define the prompt's UI or wording.

## The fix-up offer

The miss path's answer is also turned into a ready-to-commit annotation snippet:

- **key** is always `oncall-harness/alert-match`.
- **value** is the alert's discriminating field, resolved by a pinned order: the alert's
  `name` field if non-empty, else its `service_hint` field if non-empty, else the first
  entry of its tags, else empty.
- **target** is the named service's existing catalog file when the service is already in
  the catalog, or — when the service is absent from the catalog entirely — the
  conventional path `services/<service-name>/catalog-info.yaml`.
- **snippet** is the paste-ready annotation block containing that key and value, ready to
  drop into the target file as-is — rendered in the same strict-JSON style the catalog
  files themselves use:

  ```
  "oncall-harness/alert-match": [
    "checkout-5xx"
  ]
  ```

**An offer with an empty value is not commit-ready, and carries no snippet.** When the
alert offers nothing discriminating — no `name`, no `service_hint`, no tags — the pinned
order bottoms out at the empty string, and there is nothing worth committing. Do not
render a snippet in that case and do not invite the responder to commit one: an empty
matcher in a real catalog would match every sparse alert (see "Exact stage" above). Ask
the responder for a discriminating value instead, or leave the catalog untouched.

**The responder commits it. No agent ever writes to the catalog.** This is not carried by
instruction alone: the harness's credentials are read-only by default (Constitution
Platform Constraints), so the boundary rests on a deterministic layer rather than on an
agent choosing to honor a sentence. The catalog is
human-curated, PR-reviewed data, and that boundary is the whole point of reading it fresh
through your code tool's file reads each session rather than owning a copy of it.

## Duplicate names and blast radius

The duplicate-`name` tie-break (which entity wins when two service-shaped entities share
a name) is `references/annotations.md`'s rule — this document does not restate it.

**Blast radius (FR-006)**: widening an affected-service assessment uses a service's
**direct `dependsOn` entries — one hop, v1**. Traversal stops there; it does not follow
a dependency's own dependencies. Deeper, multi-hop traversal is a recorded future option,
not a promise this surface makes today.

An entry naming a service the catalog does not contain is **kept** in the widened set and
surfaced as a catalog-quality note — never silently filtered. Silently shrinking a blast
radius on the assumption that an unknown name must be invalid is worse than surfacing a
wide one with a note attached: the responder can discount a noted entry, but cannot
recover one that was dropped without a trace.
