# `bb-shell` — the cmux backend

How the `bb-shell` interface (see `bb-shell.md`, the backend-independent contract) maps
onto cmux's socket API. **This is the only shipped file that names a concrete shell
product**; the contract document and every command, skill, and agent stay backend-agnostic
(FR-22, and Constitution VII's spirit applied to shells).

Selected by `.claude/settings.json` → `battleBuddy.shell: "cmux"`. cmux is macOS-only
(risk R-1), which is exactly why degraded mode is the default rather than a fallback.

Protocol details below were pinned empirically against a running cmux on 2026-07-22
(slice-9 `research.md`, R1–R3). cmux is an *adopted* application, not a dependency: nothing
in the plugin imports it, and its absence is a normal, silent, fully-functional state.

## Socket discovery

1. `$CMUX_SOCKET_PATH` — the canonical override.
2. Otherwise the documented default, `~/.local/state/cmux/cmux.sock`.

`$CMUX_SOCKET` is a **deprecated alias**. cmux's own CLI fails when both are set and
disagree; `bb-shell` instead degrades with a diagnostic notice, because a mistyped
environment variable is not a caller bug in the usage-error sense and bricking a session
over one would invert the fail-soft rule.

**Password-protected sockets are not supported in v1.** cmux can require a socket password
(`--password`, `$CMUX_SOCKET_PASSWORD`, or one saved in its settings), but its
authentication handshake is undocumented and was not exercised here — the development
socket reported `access_mode: cmuxOnly` and accepted unauthenticated connections. Rather
than guess at a handshake, `bb-shell` connects without one: on a socket that demands
authentication the connection is rejected, and that is simply another backend failure, so
the verb degrades to printed output and exits successfully.

The shim therefore never reads `$CMUX_SOCKET_PASSWORD` at all, and no credential can reach
a request frame, a log line, or a diagnostic. Adding authentication later is a change to
this backend only; the interface contract is unaffected.

**Known gap, stated rather than papered over**: cmux also auto-discovers tagged and debug
sockets (observed in the wild as `cmux-<uid>.sock`), by an algorithm its docs do not
publish. `bb-shell` does not reimplement it — coupling to an unpublished detail would
break silently when cmux changes it. Teams whose socket is tagged set `CMUX_SOCKET_PATH`,
which is cmux's own supported override; anyone who does neither gets degraded mode, which
works.

## Wire protocol

`AF_UNIX` / `SOCK_STREAM`, **newline-delimited JSON** — one request line, one response
line. cmux reports `{"protocol": "cmux-socket", "version": 2}`.

```
request   {"id": <str>, "method": <str>, "params": {…}}\n
response  {"id": <str>, "ok": true,  "result": {…}}\n
      or  {"id": <str>, "ok": false, "error": {"code": <str>, "message": <str>}}\n
```

**Response key order is not stable.** The same server returns `{"ok",…,"id"}` for one call
and `{"id","ok",…}` for the next. Parse as JSON; never by position. (The test fake
alternates key order deliberately so a positional parser fails in CI.)

Responses must be read **until a newline**, not with a single `recv`: a partial read is
indistinguishable from a healthy short reply, and a backend dying mid-write is one of the
fault classes the adapter must survive.

Observed error codes: `method_not_found`, `invalid_params`. `bb-shell` treats **every**
`ok: false` as a backend failure and falls back to degraded output; it never branches on
the code beyond quoting the message into its diagnostic note.

Socket operations use a **2.0-second timeout**, applied to connect and to every read. Every
call is local IPC where a healthy reply is sub-millisecond; the timeout exists so a wedged
cmux costs a responder two seconds, not a session.

## Verb mapping

| Interface verb | cmux method(s) | Params |
|---|---|---|
| `open-pane` *(no `--workspace`)* | `surface.create` | `type` (`browser`\|`terminal`), `url` \| `command` |
| `open-pane --workspace <id>` | `workspace.list` → `workspace.create` *(only when absent)* → `surface.create` | `workspace.create`: `name`; `surface.create`: `workspace_id`, `type`, `url` \| `command` |
| `navigate-pane` | `browser.navigate` | `surface_id`, `url` |
| `notify` | `notification.create` | `title`, `body` |
| `close-workspace` | `workspace.list` → `workspace.close` | `workspace_id` |

Params use `_id` suffixes. cmux rejects the un-suffixed form with an error that names the
correct one, e.g. ``Unsupported parameter `window`; use `window_id` …`` — a useful probe
when extending this mapping.

### Panes and surfaces

`browser.navigate` addresses a **surface**, not a pane: in cmux's model a *pane* is a split
container and a *surface* is the tab inside it that renders a terminal or a browser. The
interface says "pane" because that is the backend-independent word, and because slice 5's
commands already call it that. The mapping lives here, which is where a product-specific
concept belongs.

`surface.create` is used rather than `pane.create` for the same reason: `open-pane` wants a
rendered thing, and `pane.create` would additionally split the layout, which no requirement
asks for.

### Workspaces and reattach

The session ID is the workspace **title**. `open-pane --workspace S` lists workspaces,
matches on `title == S`, and reuses that workspace's ID if present — otherwise creates it.
`close-workspace S` resolves the same way and closes by ID; a session ID that matches no
workspace is a soft failure (it may already be closed), so it degrades rather than erroring.

Because the lookup is a read of the backend's own state on every invocation, workspaces
survive restarts without the shim tracking anything, and concurrent invocations cannot
disagree about what exists.

**Known gap**: `workspace.create`'s exact result shape was not probed (doing so would have
created real workspaces in a live session). The shim accepts any of `workspace_id`, `id`,
or a nested `workspace.id`, and raises a clear backend error — which then fails soft —
if none is present. Confirm the real shape before relying on the field name.

### Notification levels

cmux's `notification.create` accepts `title`, `subtitle`, and `body` — there is **no
level, priority, or urgency field**. `bb-shell` therefore encodes the level in the title:

```
title = "battle-buddy: <level>"      body = <message>
```

`title` was chosen over `subtitle` because cmux renders it most prominently and
`notification.list` always returns it populated, which makes "the level reached the
backend" verifiable. `subtitle` is optional in cmux's model and was observed empty on real
notifications.

## What `bb-shell` deliberately does not use

cmux's socket exposes 221 methods, including `browser.eval`, `browser.cookies.get`,
`browser.storage.*`, `browser.screenshot`, and `surface.read_text`. `bb-shell` binds
**six** — those in the table above — and its argument grammar cannot express the others.

The boundary is worth stating plainly: it is *ours*, not cmux's. The capability to read
page content and cookies exists on the socket, and the harness declines to expose it,
because the responder's SSO sessions in those panes are theirs alone (FR-24). Any future
change here is a change to a security boundary, not a feature addition.
