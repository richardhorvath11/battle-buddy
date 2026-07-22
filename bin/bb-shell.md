# `bb-shell` — the shell adapter interface

The contract every shell backend implements, and the only shell surface the rest of
battle-buddy touches. Commands, skills, and agents invoke `bb-shell`; nothing in the core
knows — or may know — which shell answers (design §6.3, §11 D-2, FR-22).

This document is **backend-independent by construction**. It names no shell product. A
future shell (a different multiplexer, an IDE, a web dashboard) integrates by implementing
the semantics below behind the shim, with zero changes to any command or skill.

## The four verbs

```
bb-shell open-pane <url|command> [--workspace <session-id>]
bb-shell navigate-pane <pane> <url>
bb-shell notify <message> [--level <info|warn|approval>]
bb-shell close-workspace <session-id>
```

### `open-pane <url|command> [--workspace <session-id>]`

Opens a pane showing `<url>`, or running `<command>`. A target with a URL scheme
(`http://`, `https://`, `file://`) opens a **browser** pane; anything else is treated as a
command and opens a **terminal** pane — that is how the agent's own terminal pane is
opened, so the command form is half the verb, not an edge case.

With `--workspace`, the pane belongs to the workspace named for that session ID.
Composition is **caller-driven**: the first call for a session ID creates the
session-named workspace, and later calls add panes to it. If a workspace with that name
already exists — a restart, a rejoin, a handoff — the backend **reattaches** to it rather
than duplicating. Workspace existence is therefore resolved from the backend on every
invocation; the shim remembers nothing between calls.

*Degraded*: prints the target it would have opened, plus the workspace when given.

### `navigate-pane <pane> <url>`

Drives an already-open pane to `<url>`. This is the evidence deep-linking primitive
(FR-9): the agent cites a dashboard, a search, or a commit, and the adjacent pane goes
there. `<pane>` is an opaque handle produced by the backend; the shim never interprets it.

*Degraded*: prints the URL, so the responder can click it.

### `notify <message> [--level <info|warn|approval>]`

Raises the responder's attention. `--level` is **optional and defaults to `info`**; the
level set is closed (`info`, `warn`, `approval`) and an unrecognized value is a usage
error. `approval` is the level used when the agent is blocked waiting on a human decision.

*Degraded*: prints the message with its level.

### `close-workspace <session-id>`

Closes the workspace named for that session at the end of the session lifecycle
(design §4's close flow, step 33). Session state remains restorable — closing a workspace
is not destroying a session.

*Degraded*: prints that it would have closed the workspace.

## Backend selection

From workspace configuration, `.claude/settings.json` → `battleBuddy.shell`:

| Value | Behavior |
|---|---|
| absent | degraded mode, **silently** — the documented normal state for teams with no shell adapter |
| `none` | degraded mode |
| a recognized backend name | that backend |
| anything else | degraded mode, **with a diagnostic notice** — a probable typo must be visible |

Degraded mode is a **first-class path, never an error state**: every feature works in a
plain terminal with links printed (FR-26). It is also the path for any platform a backend
does not support.

## Failure behavior

**Every backend failure fails soft.** If the backend is absent, refuses the connection,
times out, dies mid-call, rejects the request, or answers with something unparseable, the
shim produces that verb's degraded output, notes the fallback in diagnostics, and **exits
successfully**. A shell failure must never surface as a session error, and must never
brick an investigation.

There is deliberately **no exit code for backend failure**. That absence is the contract.

The shim keeps no memory of backend health: repeated failures each fall back
independently, with no lockout and no retry storm, so recovery is automatic — the next
call after the backend returns simply uses it.

## Exit codes and output channels

| Code | Meaning |
|---|---|
| `0` | the verb succeeded — through the backend **or** through degraded fallback, which are indistinguishable by design |
| `2` | **usage error**: unknown verb, missing or extra arguments, unrecognized `--level` |

Usage errors are the one loud path. Fail-soft covers backend *availability*; a caller
passing malformed arguments is a bug in the caller and must hear about it.

- **stdout** — the responder-facing link or message (degraded mode's output).
- **stderr** — diagnostic notices and usage text.

A caller capturing stdout gets exactly the user-facing artifact; a caller ignoring stderr
still exits successfully.

## What this interface deliberately cannot do

The verb set and argument shapes admit **no credential, cookie, session-state, or
page-content operation**. Third-party tools render in browser panes using the responder's
own SSO sessions, and the harness never reads, injects, or manages them (FR-24). The two
credential paths — responder SSO in panes, agent tokens in MCP servers — never cross.

This is a structural property, not a runtime check: there is no argument through which a
credential operation could be expressed. A backend implementing this interface inherits
the boundary, and a backend that exposes more must not expose it *here*.

## Implementing a new backend

Implement the four verbs' semantics above, including:

1. the degraded rendering for each verb, as the fallback when your backend is unavailable;
2. fail-soft on every failure mode, with exit success;
3. caller-driven workspace composition with reattach-by-name;
4. no state held between invocations.

Then add your backend's name to the config value's recognized set. No command, skill, or
agent changes — that is what this interface is for.
