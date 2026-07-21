---
description: Idempotent, mode-aware onboarding wizard — the only intended first touch for a new team or a new responder. Derives its mode from artifact state (never a stored flag), resolves bindings, creates or validates the session store, scaffolds the workspace repo, and finishes with /doctor plus an end-to-end smoke test.
---

# /setup

`/setup` is how a team goes from an empty directory to a working battle-buddy workspace,
and how a responder on a freshly cloned workspace goes from "cloned" to "ready to page."
It is always safe to run: it inspects what already exists and does only what is missing.

## When to run

- **Once, in an empty directory**, to stand up a new team's workspace.
- **Once per responder, per machine**, right after cloning the team's workspace repo.
- **Any time**, to confirm the workspace is still green — a run against an already-green
  workspace validates and reports, touching nothing.
- **Automatically**, in responder mode, whenever `/page`'s preflight finds the local green
  stamp missing or stale (the trigger itself ships with `/page`; this command defines what
  runs when it fires).

## Mode derivation

State lives in two scopes, and `/setup` reads both by inspection — it never writes or
checks a stored "done" flag:

- **Team scope** — the config block, the store header, the artifact root, the binding
  map. Committed with the workspace repo; cloning inherits it.
- **Responder scope** — this responder's tokens, their probe results, the local green
  stamp. Per person, per machine, never committed.

| Observed state | Mode |
|---|---|
| No config block | **team** — full sequence below |
| Config block present (well-formed) but the store header missing | **team-partial** — create only what is missing, through the already-committed binding map; validate the rest with zero writes |
| Config block present; this responder's probes fail, or the local stamp is missing/stale | **responder** — provision and verify this responder only |
| Everything green | **already-set-up** — validate and report, zero writes |
| Config block present but malformed | **repair** — surfaced explicitly, never treated as absent |

A malformed config block is always a repair case, never "no config." Team mode
re-creating resources over what might be a typo would destroy a working setup — an
onboarding wizard's first job is to not make things worse.

## Team mode

Runs the following sequence, in order, stopping and reporting the instant something
can't proceed:

1. **Resolve bindings.** Same resolution protocol `/doctor` runs on its own: match every
   required operation to a connected tool by schema, fail loudly naming the operation on
   zero candidates, surface every candidate name on a multi-match and wait for an explicit
   choice, then write the resolved `capability.operation` → tool-name entry. See
   `/doctor`'s Resolution protocol for the full step-by-step.

2. **Store: create or validate.**
   - **Empty store** → *create*: write the header row **through the just-resolved
     `storage.append_record` binding** — this is what guarantees the header's columns
     match what the binding actually writes, not a hope that they'll agree. Columns are
     the session-store skill's schema reference, in its documented order, followed
     immediately by one more cell holding the schema-version sentinel.
   - **Existing store, header and sentinel match** → *validate*: zero writes.
   - **Existing store, mismatch** → report the exact mismatch (missing, extra, or
     misordered columns; a wrong sentinel value) with zero writes. Nothing is silently
     re-created, and the run stops here — no config write, no scaffold, no doctor call,
     no smoke test.

   (`templates/session-sheet.md` documents this same header shape for anyone setting up
   or inspecting a store by hand — it is reference documentation only, never the path
   this command follows.)

3. **Artifact root.** Record the configured root (default `battle-buddy/`) for the config
   write below. There is no folder-creation operation of its own — establishing the root
   reduces to recording its location; writability is exercised end-to-end by the smoke
   test.

4. **Diary and catalog prompts.** Ask for the diary location and the catalog repo, and
   accept what's given as-is. Deeper reachability and parseability checks are `/doctor`'s
   job, not this step's.

5. **Write the config block.** The full `battleBuddy` block, including its version field:
   `configVersion`, `pluginPin` (the installed plugin version), `store` (`{url,
   schemaVersion}`), `diary` (`{url}`), `catalog` (`{repo}`), `artifactRoot`, `bindings`
   (the map just resolved), `budgets.triageTurnCap`, and `shell` (`{adapter}`) when a
   shell adapter is configured.

6. **Scaffold the workspace repo.** Exactly four files, zero upstream content — nothing
   from the plugin itself is ever copied in:
   - `.claude/settings.json` — the config block above, plus the plugin pin.
   - `.mcp.json` — the team's connected servers, with every credential written as an
     `${ENV_VAR}` reference. Secrets never enter this file or the repo it lives in. If the
     team hasn't already connected tools of their own, the recommended roster template
     (`templates/mcp.recommended.json`) is the documented starting point covering all
     four required capabilities out of the box.
   - `README.md` — what the repo is, and how to push it.
   - `.gitignore` — excludes the local runtime droppings (session markers, the local
     doctor stamp, local trace files).

   `git init` runs locally as part of this step. Pushing is the team's own next act:
   create a private repository in your org and push there — this repo is team state, not
   battle-buddy's, and it should never be public.

7. **Finish with `/doctor`.** Run the full resolution-plus-verification pass and produce
   the structured report — same report shape a standalone `/doctor` run produces. A
   non-green report here is reported, not unwound; the config and scaffold already
   written stay as they are.

8. **Run the smoke test.** Described next. A doctor report that isn't green skips this
   step entirely.

## Smoke test

A synthetic session that proves every write and read path actually works, end to end,
through the bindings just resolved — not merely schema-matched:

- `session_type: test`, `status: closed` — closed at append, so this row is inert from
  the moment it exists; it can never be mistaken for a live session to join.
- Session ID `test-bb-setup-<ISO date>`.
- **Record append** (`storage.append_record`) — the row lands.
- **Artifact write** (`artifacts.put_file`), under `<artifactRoot><session_id>/` — its
  returned link is then recorded back onto the row (`storage.update_record`), confirming
  the write actually produced something reachable.
- **Diary append** (`diary.append_entry`).
- **Record read-back** (`storage.read_records`) — confirms the appended, now-linked row
  is readable through the same binding that wrote it.

This row is permanently excluded from retrieval by the session-store conventions —
running `/setup` repeatedly leaves harmless extra rows behind, never a candidate in any
real investigation. A smoke-test failure is loud and specific: it names exactly which of
the four paths failed and why, never a generic "setup failed."

## Responder mode

Runs when team scope already exists (cloned with the workspace repo) but this
responder's own scope doesn't yet, or has gone stale:

- Provision this responder's own tokens.
- Verify every required probe under *this responder's* credentials — the same benign,
  read-shaped probes `/doctor` runs.
- Write the local green stamp on success.

Responder mode **creates no team resources** — no store, no config, no scaffold. Team
scope isn't this responder's to create; it already exists, and cloning is what handed it
to them. This is also exactly the mode `/page`'s preflight auto-runs the first time a
responder pages in from a new machine — seconds of work, and only ever once per machine.

## Idempotence

Running `/setup` again is always safe, by design:

- **Already green** → validate every team-scope resource and report already-set-up. Zero
  mutating operations.
- **Partial state** (e.g. config present, store header missing) → only the missing piece
  is created; everything already present is validated, never re-created.
- **Malformed config** → the repair case above, surfaced explicitly, never papered over
  by a fresh team-mode run.

## Endings

Every run ends one of two ways:

- **`green: run /page on your next alert`** — the workspace is fully resolved, verified,
  and (in team mode) smoke-tested.
- **One specific failure** — the exact operation that failed to resolve, the exact
  ambiguity awaiting a choice, the exact store mismatch, the exact migration needed, or
  the exact smoke-test path that broke. Never a generic "setup failed."
