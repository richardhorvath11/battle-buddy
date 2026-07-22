---
name: diary
description: Use when appending a close-time entry to the team's diary or resolving what format that entry should take — the two-operation adapter interface, the template-vs-matched-recent-structure format resolution, the write flow that lands the dual-write's first write, and the drafting handoff that supplies an entry's content. Documents the diary adapter conventions that stand in for shipped diary-adapter code.
---

# Diary

The team's diary is its own readable record of what happened during an incident —
the close flow's dual write lands a machine-readable session row and a diary entry
side by side, and this skill documents the diary half of that pair: the adapter
interface the close flow drives, the format-resolution rules that let a close-time
entry read like the team already writes its diary, the write flow that produces the
row's diary link, and the drafting handoff that supplies an entry's content. This
slice ships prose and tests only — no diary-adapter code (Constitution I; FR-008).
At runtime the "adapter" is an agent reading and appending through the diary
capability's operations, guided by this document and its reference, never a named
product or MCP server (Constitution VII).

## Interface

<!-- T012 (US2) fills this: the two-operation skill-level contract
     (read_recent(n) -> entries[], write_entry(content) -> url), its
     realization onto operation contract v1, the Entry shape, and the error
     posture. -->

## Write flow

<!-- T013 (US2) fills this: the append targets the team's configured diary
     through the diary capability, append-only, no diary creation, and the
     returned link's linkage into the session row. -->

## Drafting handoff

<!-- T014 (US2) fills this: the close-time inputs drafting consumes and what
     is deliberately not an input (the close-time row update), per
     data-model.md §7. -->

## Non-goals

<!-- T019 (Phase 6) fills this: what this slice deliberately does not ship or
     own — adapter code, the close flow, causal labeling, diary_url /
     diary_pending, and the approval boundary this slice must not appear to
     weaken. -->
