---
description: Capability verification and binding resolution — resolves the team's connected tools into the workspace binding map, verifies store/diary/catalog/version/shell health, and reports green or a named gap. Run outside incidents.
---

# /doctor

`/doctor` is the conformance test and linker between the capabilities battle-buddy needs
and whatever tools the team actually connected. It never touches session rows — its only
writes are the binding map, the local stamp, and (indirectly) the workspace config it
validates. Every run produces one structured report; a run is either green or it names,
specifically, what is wrong.

## When to run

- **Outside incidents.** Doctor is a health check, not an investigation step — run it
  between pages, never mid-session.
- **After any change to the connected MCP roster** — a tool added, removed, or
  reconfigured.
- **After a plugin update.** The version seam below exists precisely to catch a plugin
  that now expects something the workspace hasn't caught up to.
- **Automatically**, in responder mode, whenever the local green stamp is missing or
  stale (see "Green-run stamp").

## Resolution protocol

The plugin's capability manifest (`manifest/capabilities.json`) declares every operation
tier 0 needs, grouped by capability — `storage`, `artifacts`, `diary`, `alerting` are
required; `code`, `observability` are optional. Names never matter; shapes do. For every
required operation, in this order:

1. **Match.** Inspect the schema of every connected tool and collect every one whose
   schema can express the operation's input/output shape — this is semantic matching,
   performed by you, never a keyword or name match.
2. **Zero candidates.** Fail loudly, naming the unresolved operation by its
   `capability.operation` name (e.g. `storage.append_record`). The run is not green.
3. **More than one candidate.** Surface every candidate tool by name and stop there for
   that operation — require an explicit choice. **Never silently pick one**, even when
   one candidate looks like the obvious fit. An ambiguity left unresolved leaves the run
   non-green, same as a zero-candidate failure.
4. **One candidate, or an explicit choice was made.** Confirm it:
   - Read-shaped operations are confirmed with the benign probe below.
   - Mutating operations (`storage.append_record`, `storage.update_record`,
     `artifacts.put_file`, `diary.append_entry`) are confirmed by schema match alone at
     doctor time — end-to-end exercise of a mutating operation is `/setup`'s smoke
     test's job, not doctor's.
5. **Write** the binding entry (below).

## Benign-probe table

Every probe call below uses exactly the payload shown. A call that succeeds passes —
including when it returns an empty result; these probes assert reachability and shape,
never that any particular data already exists.

| Capability.operation | Payload | Passes when |
|---|---|---|
| `storage.read_records` | `{"filter": {"session_id": "bb-doctor-probe"}}` | call succeeds; empty result is a pass |
| `diary.read_recent` | `{"n": 1}` | call succeeds; shape matches |
| `alerting.list_alert_history` | `{"filter": {"alert_id": "bb-doctor-probe"}}` | call succeeds; empty result is a pass |
| `artifacts` | *(no read-shaped operation exists)* | recorded schema-match-only, never probed |

## Binding map

Write one entry per resolved required operation into the workspace config's
`battleBuddy.bindings` map, keyed exactly `<capability>.<operation>` and valued with the
tool name resolved to it:

```
"storage.append_record": "<tool-name>"
```

This map is committed with the workspace repo — bindings are a property of the team's
roster, not of any one responder's machine. An optional capability's entries appear only
when the roster happens to resolve them.

**Drift re-validation.** On every run against an already-committed binding map, re-check
each entry against the roster currently connected: an entry whose tool name is no longer
connected, or is still connected but no longer shape-compatible with the operation it was
bound to, is flagged **stale by name**. A stale entry is never silently rewritten — it is
surfaced, and that operation is treated as unresolved until the next run re-resolves it
(an explicit choice is needed only if more than one tool then matches).

## Verification checks

Beyond resolving bindings, every run verifies:

- **Store.** Reachable, with its header row matching the documented column set exactly,
  plus the schema-version sentinel cell one column past the last documented column (the
  session-store skill's schema reference is the authority for both). Any mismatch —
  missing, extra, or misordered columns, or a wrong sentinel value — is reported in full
  detail, never as a generic failure.
- **Diary.** Readable, with its append operation schema-matched (writability itself is
  exercised end-to-end only by `/setup`'s smoke test, not by doctor).
- **Catalog.** The configured repo parses.
- **Config block.** Well-formed. A malformed config block is reported as an explicit
  repair case, never silently treated as absent — team-mode setup must never re-create
  resources over what might be a typo.
- **Version seam.** The config block's version and the store's schema-version sentinel
  must exactly match what the installed plugin expects. Any mismatch is reported as the
  exact migration string: `"<artifact> <found-version> → <expected-version>: <remedy>"` —
  never a generic "out of date" failure.
- **Shell notify round-trip.** When a shell adapter is configured, round-trip a notify
  call through it. When none is configured, this check is **skipped**, and reported as
  skipped — never as failed.

## Report semantics

Every run produces one structured report — one machine-readable outcome per resolved
operation and per verification check above. Read the report, not doctor's prose, to
decide whether the run is green.

- **Any required capability unsatisfied, or any ambiguity left unresolved** → the run is
  **not green**; the report names the specific gap — the exact operation, the exact
  mismatch, the exact migration. Always specific, never generic.
- **An optional capability missing** → the run **stays green**; the report's
  reduced-features list names exactly the features that capability's absence disables,
  taken from that capability's `enables` list in the manifest — for example, no `code`
  disables exactly deploy correlation, catalog, and runbook fetch; no `observability`
  disables exactly metric reads and evidence deep-links. Never a vague "some features
  degraded."
- Every feature that depends on a missing optional capability degrades gracefully at
  runtime — it never errors.

## Green-run stamp

On a green outcome, write the local stamp to `.bb-doctor-stamp.json` at the workspace
root. This file is never committed — it's gitignored, a local runtime dropping, separate
from anything session-scoped.

Its shape: schema `bb.stamp.v1`, a timestamp, the installed plugin version, and a roster
hash — the first 16 hex characters of a SHA-256 over the canonical JSON serialization of
the connected roster's server entries, with any environment-variable reference kept as
its literal string, never a resolved secret.

**Staleness** has exactly two triggers: the plugin version no longer matches the
installed plugin, or the roster hash no longer matches the current roster file. A missing
or unparseable stamp is stale. The timestamp is diagnostic only — it is reported, but
never used to expire the stamp on its own; there is no time-based staleness here, by
design (a time window would just reintroduce probes at 3am).

## Failure endings

A non-green run always ends by naming the specific gap: the exact operation that failed
to resolve, the exact ambiguity awaiting a choice, the exact store/diary/catalog
mismatch, or the exact migration needed. Never a generic "doctor failed" — a specific,
actionable ending outside the pressure of an incident is the entire reason to run
`/doctor` at all.
