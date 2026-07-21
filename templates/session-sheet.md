# Session Store — Manual Setup Reference

**This is reference documentation, not the setup path.** `/setup` creates and validates
the session store for you — including writing the header row through the just-resolved
storage binding, which is what guarantees column fidelity (design §7.3). Read this file
only if you are setting up or inspecting a store by hand outside `/setup` (e.g. standing
up a fresh spreadsheet before a team's first `/setup` run, or eyeballing an existing one).

## Shape

One row per session. Row 1 is the header: one cell per documented column, in the exact
order below, followed immediately by one more cell holding the schema-version sentinel.
Every session thereafter is a single appended row; `/doctor` validates this header (and
the sentinel) as part of confirming the store is reachable and correctly shaped.

## Header row — column names, in order

The authority for what each column means, its type, and when it may change after append
is `skills/session-store/references/schema.md`'s column table — this file only restates
the **names**, in the order `/doctor` checks them against. If the two ever disagree,
`schema.md` wins.

| # | Column name |
|---|---|
| 1 | `session_id` |
| 2 | `session_type` |
| 3 | `status` |
| 4 | `fingerprint` |
| 5 | `catalog_resolved` |
| 6 | `alert_signature` |
| 7 | `services` |
| 8 | `severity` |
| 9 | `responder` |
| 10 | `started_at` |
| 11 | `closed_at` |
| 12 | `triage_verdict` |
| 13 | `latest_checkpoint` |
| 14 | `timeline` |
| 15 | `root_cause` |
| 16 | `resolution` |
| 17 | `links` |
| 18 | `runbook_refs` |
| 19 | `diary_url` |
| 20 | `diary_pending` |
| 21 | `report_url` |
| 22 | `artifacts_folder_url` |

## Version-sentinel cell

One column to the right of the last schema column above (column 23) holds a single
literal string in row 1 only: **`bb.schema.v1`**. It is not a data column — no session
row carries a value there, and the schema column set stays exactly the 22 columns above.
`/doctor` reads this cell to confirm the store's schema version matches what the
installed plugin expects, and reports the exact migration string if it does not.

## Authority

`skills/session-store/references/schema.md` is the authority for column meanings, types,
mutation classes, and the version-sentinel rule this file only summarizes by name. Consult
it — not this file — for anything beyond "what are the column names and where does the
sentinel go."
