---
description: "Runs the same open flow as /page with incident weight — session_type: incident, deep investigation proposed after triage — and promotes an already-open page session in place instead of duplicating it."
---

# /incident

`/incident <incident-id>` opens a session exactly the way `/page` does — same
preflight decision table, same open-flow order, same join-or-separate choice
on a matching open row. See `commands/page.md` for that full step-by-step
walkthrough; it is not restated here. This document covers only the two
deltas that give an incident more weight than a page, and the promotion path
that exists because of them.

## When to run

- **At the incident.** `/incident <incident-id>` opens a `session_type:
  incident` session for that ID and briefs the responder immediately, same as
  `/page`.
- **Inside an already-open page session**, to promote it — see "Promotion"
  below — rather than opening a second session for the same alert.

## Preflight

Identical to `/page`'s preflight decision table — the same six ordered rows
(no config / malformed config / confirmed marker / crash residue / stale
stamp / proceed), evaluated in the same order, before any store read or
probe. See `commands/page.md` "Preflight" for the table itself; nothing about
it changes for `/incident`.

## Fresh open: incident weight

Everything in `/page`'s open-flow order applies unchanged — the marker
write, shell open, alert and catalog fetch, tier-0 retrieval, triage,
verdict validation, the row append carrying checkpoint zero, read-back, and
briefing. Two deltas apply on top of that same order:

- **`session_type: incident`** on the appended row, in place of `page`.
- **Deep investigation is proposed the moment the triage verdict validates**
  (the same validation-gate step `/page` runs) — never deferred to a later
  command, and never conditional on anything else about the alert. Whether
  it *launches* follows the rule below; proposing it is unconditional for
  every incident-type session.

## Deep-investigation launch

Proposing deep investigation is unconditional for a fresh incident open;
launching it is not:

| Condition | Launch? |
|---|---|
| Responder confirms the proposal | Launch |
| `battleBuddy.autoLaunchDeep` is `true` in the workspace config | Launch — no confirmation needed |
| Neither | Do not launch yet — the proposal stands, unconfirmed |
| Promotion (see below) | Launch unconditionally — no confirmation gate on this path |

`battleBuddy.autoLaunchDeep` is an additive workspace-config key (default
`false` when absent): setting it changes only whether an incident session's
own deep investigation launches automatically. No other config key's shape
or consumer changes because of it. Spawn mechanics and the investigation
ledger themselves belong to the investigation skill, not to this command —
this command's only responsibility is the proposal-and-launch decision.

## Promotion: /incident inside an open page session

When `/incident` is invoked while a page session is already open in this
workspace — the local session marker names it — it does not open a second
session. It promotes the existing one in place:

- **Exactly one row update** re-tags that session's `session_type` to
  `incident` — `storage.update_record`, never `storage.append_record`. No
  second row for the source ID exists before or after the promotion.
- **The session ID is unchanged.** Promotion re-tags the row the marker
  already names; it never recomputes a session ID and never rewrites the
  local marker — this is the same session, not a join.
- **Deep investigation launches immediately, unconditionally.** Promotion is
  itself the confirming act; the confirmation-vs-`autoLaunchDeep` gate above
  applies only to a *fresh* `/incident`, never to a promotion.
- **No context loss.** Every other row field, every checkpoint, and the
  whole local session state stay exactly as they were — the only observable
  change to the responder is the row's own `session_type`.

If the local marker names no open session at all, there is nothing to
promote: `/incident` falls through to the fresh-open path above instead
(preflight's own no-marker and crash-residue rows already cover that case —
see `commands/page.md`).

## Join or open separately

Identical to `/page`'s join-vs-separate choice: the retrieval read still
doubles as duplicate detection for a *different* source ID's open row, and
nothing is written before the responder chooses. See `commands/page.md`
"Join or open separately" — this is the same choice, not a second one
layered on top of promotion above (promotion is specifically the same
source ID's own already-open session, detected off the local marker rather
than the retrieval read).

## Fail-soft postures

Every fail-soft posture `/page` documents — alert-fetch failure, catalog
miss, a missing or failing shell adapter — applies unchanged to
`/incident`'s fresh-open path; see `commands/page.md` "Fail-soft postures".
Promotion touches none of those surfaces at all: it is a single row update
and nothing more, so there is nothing on that path to degrade.

## Session state

Same local-session-marker rules as `/page`: one open session at a time per
workspace, the marker created and confirmed on a fresh open exactly as
`/page` does it. Promotion is the one exception spelled out above — it
re-tags the row the marker already names and never rewrites the marker
itself, because it is not a new open.
