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

The diary's entire surface to the rest of the system is two operations:

```
read_recent(n) -> entries[]        # most recent first; n defaults to 5
write_entry(content) -> url        # the dual-write's first write
```

These are skill-level names. They realize onto operation contract v1's diary
capability as follows: `write_entry` is the contract's `append_entry`, and
`url` is the contract's `link`; `read_recent` keeps its own name and `n`
unchanged.

| Skill-level name | Diary capability operation |
|---|---|
| `read_recent(n)` | `read_recent(n) -> {entries}` |
| `write_entry(content)` | `append_entry(content) -> {link}` |

`read_recent` returns entries most recent first, and consumers use that
order as-is — they never re-sort it.

`Entry` is the diary capability's own shape — `{link, content, at}` — cited
here, not redefined; its authority is the diary capability's operation
contract, not this document.

**The op-set is closed: append and read, exactly two.** There is no create
operation in the diary capability, which is why "this skill never creates
diaries" is a pin derived from the contract rather than an aspiration this
skill merely states — a create path would have to exist in the contract
before this skill could ever reach for it.

**Error posture.** An operation failure surfaces the diary capability's
uniform error envelope to the close flow unchanged. This skill attempts the
operation and reports what happened, honestly — it does not retry, does not
paper over a failure, and does not substitute a fallback destination. Retry
policy belongs to the close flow, not to this interface.

## Write flow

The append targets the team's configured diary, through the diary
capability: append-only, no diary creation, no alternate destination. This
skill never invents a fallback location and never creates the diary itself
— a team with no diary configured has a setup-time gap this skill does not
paper over.

This is the dual-write's **first** write. The link `write_entry` returns is
the value the close flow carries into the session row's diary field — the
linkage that makes this entry findable from the store, for as long as the
row exists.

The ordering of the dual-write, and the failure path when this write does
not land — `diary_pending` as the retry queue — belong to
`skills/session-store/` and the close flow; this document does not restate
either.

Confluence, Notion, and git-markdown adapters are explicitly deferred.
Swapping diary stores changes bindings, never this skill: the destination
is a per-team, binding-time fact, and every team's diary is reached through
the same two operations above regardless of which store answers them
(FR-4a).

## Drafting handoff

Before any write happens, the close flow assembles a draft and hands its
content to this skill for format matching. What it supplies:

- **In-session evidence links** — the dashboards, searches, and PRs
  gathered during the session.
- **Services and severity** — factual.
- **Resolution** — factual.
- **Labeled causal proposals** — root cause, contributing factors, action
  items, carrying the close flow's own proposal labels.
- **Locally staged artifact content, pre-upload** — including the tool
  trace and the checkpoint history.

**Not an input: the close-time row update.** Drafting precedes the
dual-write, so the row state the close flow eventually writes does not yet
exist when the draft is assembled. This skill reads no session-row field
and writes none.

**On the timeline.** This skill never derives the structured timeline.
Where an entry carries a timeline section, it is rendered from the same
staged sources the row's `timeline` field derives from — the tool trace and
the checkpoint history.

**Output** is entry content in the resolved format. Causal proposal labels
pass through format matching **verbatim**: this skill never strips,
rewords, or promotes them.

## Non-goals

<!-- T019 (Phase 6) fills this: what this slice deliberately does not ship or
     own — adapter code, the close flow, causal labeling, diary_url /
     diary_pending, and the approval boundary this slice must not appear to
     weaken. -->
