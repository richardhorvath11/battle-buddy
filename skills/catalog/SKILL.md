---
name: catalog
description: Use when reading or resolving the team's service catalog — alert→service resolution, the internal service model, the annotation mapping that populates it, per-field degradation, or catalog freshness. Documents the catalog conventions that stand in for shipped catalog-adapter code.
---

# Catalog

The team's service catalog is the source of truth for what services exist, how
they're owned, and how a firing alert maps onto one of them. This skill
documents the conventions an on-call agent follows when consulting the catalog
— never a parsing library or catalog-adapter code, which this slice
deliberately does not ship (Constitution I; FR-009). The catalog itself lives
in a file-based repository external to this harness; nothing here stores or
duplicates its content.

## Overview
<!-- filled by T017 -->

## Degradation

Each absent input degrades exactly its own feature, and nothing else. There are no
cross-effects — a service missing dashboards still briefs normally. Three of the four rows
below are annotations; `dependsOn` is a spec field (see `references/annotations.md` for
the full mapping), and the column names the model-facing input rather than the literal
key.

| Absent input | What stops working | What keeps working |
|---|---|---|
| dashboards | pane driving for that service | everything else — the briefing is unaffected |
| alert-match | matcher-based resolution for that service | the ask-once + fix-up path carries it, exactly as a resolution miss does |
| runbooks | runbook fetch | the absence is noted in the briefing rather than passed over silently |
| dependsOn | blast-radius widening | assessment proceeds unwidened |

For the alert-match row, the consequence worth stating plainly (also carried in
`references/resolution.md`): a matcher-less service cannot match at the exact stage at
all, but the substring stage may still resolve it when the alert happens to spell its
name in one of its fields. The rule above is about the matcher path specifically — it is
not a claim that every matcher-less service always misses.

### Malformed files

A file that cannot be parsed degrades to "this service is unavailable from the catalog"
**for that file only**: the failure is surfaced, never fatal, and every other file still
parses. Nothing about one broken file stops a session from opening.

### Catalog-quality warnings are not feature degradations

Distinguish these explicitly from the table above, because conflating them is the easy
mistake. The catalog surfaces at least these:

- **Missing owner** — a service with no owner parses fine and is surfaced. Ownership
  disables no feature; it is a quality signal, not a degradation.
- **Ignored entity** — an entry whose kind is not service-shaped is skipped with a note
  rather than parsed or errored (see `references/annotations.md`).
- **Dangling dependency** — a dependency naming a service the catalog does not contain is
  **kept** in the blast radius and surfaced. Silently shrinking a blast radius is worse
  than a wide one with a note.
- **Duplicate service name** — resolved deterministically (see
  `references/annotations.md`) and surfaced.

### No partial annotation ever errors a session

Every one of these paths degrades a feature and continues; none of them is an error
path.

## Freshness and runbook references
<!-- filled by T015 -->

## Non-goals
<!-- filled by T017 -->
