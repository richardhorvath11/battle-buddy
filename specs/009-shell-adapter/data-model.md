# Data Model: Shell Adapter (slice 9)

The shim has no persistent entities — FR-009 makes it a pure function. What follows are
the *shapes that cross its boundaries*: the argument grammar, the backend interface, the
wire envelope, the config selection table, and the fault matrix. These are the contracts
the tests assert on.

---

## 1. Verb grammar (the FR-006 boundary)

The complete argument surface. **This table is the credential boundary**: no verb and no
argument can express a credential, cookie, session-state, or page-content operation, and
that is verified structurally (a test asserts the parser accepts exactly these and rejects
everything else), not merely by a scan of what the tests happened to send.

| Verb | Positional | Options | Notes |
|---|---|---|---|
| `open-pane` | `<url\|command>` (1, required) | `--workspace <session-id>` (optional) | URL-vs-command typed by scheme (§4) |
| `navigate-pane` | `<pane> <url>` (2, required) | — | `<pane>` is an opaque handle string |
| `notify` | `<message>` (1, required) | `--level <info\|warn\|approval>` (optional, default `info`) | research R5 |
| `close-workspace` | `<session-id>` (1, required) | — | research R6 |

Rejected → exit `2` with usage on stderr (SC-006): unknown verb, no verb, wrong positional
count, unknown option, `--level` with a value outside the closed set.

**Closed sets.** `level ∈ {info, warn, approval}`. `battleBuddy.shell ∈ {cmux, none}` for
*recognized* values; anything else is handled, not rejected (§3).

## 2. Backend interface (the D-2 contract, in-process form)

Both backends implement the same four methods; the dispatcher never branches on which is
behind it. Method names mirror slice-5's `RecordingShellAdapter` (research R6) so the
fixture and the real shim stay one interface.

```
open_pane(target, workspace=None)   -> Result
navigate_pane(pane, url)            -> Result
notify(message, level)              -> Result
close_workspace(session_id)         -> Result
```

`Result` is a plain dict — `{"ok": bool, "detail": str, "degraded": bool}` — never an
exception across the boundary. `CmuxBackend` raises only `BackendError` (its own type)
internally; the fail-soft wrapper (§6) is the single place that catches, and it catches
`BackendError` **and** `OSError`/`socket.error`/`json.JSONDecodeError`, because a socket
can fail in ways the backend never wrapped.

## 3. Config selection (FR-002)

Source: `<cwd>/.claude/settings.json` → `battleBuddy` → `shell`. Read-only, never raises
(research R10).

| State of `battleBuddy.shell` | Backend | Notice on stderr? | Authority |
|---|---|---|---|
| absent (no key) | degraded | **no — silent** | FR-002; absence is the documented normal state |
| `"none"` | degraded | no | FR-002 |
| `"cmux"` | cmux | no | FR-002 |
| unrecognized string (`"cmuxx"`, `"tmux"`) | degraded | **yes** | FR-002; a probable typo must be visible |
| wrong type (`true`, `3`, `{}`, `[]`) | degraded | yes | slice-2 posture: malformed = absent, noticed |
| `battleBuddy` block absent or malformed | degraded | **no** for a missing block; yes for malformed | a missing block is the shell-less team's normal state |
| settings file absent / unreadable / bad JSON | degraded | yes (unreadable/bad JSON); no (absent) | `hooks/_config.py` posture |

The absent-vs-unrecognized split is the one behavior most likely to be implemented as a
single "not cmux → degraded" branch. It is three tests, not one.

## 4. Target typing for `open-pane` (research R11)

| Argument form | Surface type | cmux params |
|---|---|---|
| has a URL scheme (`https://`, `http://`, `file://`) | `browser` | `type: "browser"`, `url: <arg>` |
| anything else | `terminal` | `type: "terminal"`, `command: <arg>` |

Degraded mode prints either form (spec edge case: "degraded mode prints the command it
would have run") — the design's §3.2-step-3 "no-op in degraded mode" is superseded by the
spec's own pin, which this slice owns.

## 5. cmux wire envelope (research R1–R3)

```
request   {"id": <str>, "method": <str>, "params": {…}}\n
response  {"id": <str>, "ok": true,  "result": {…}}\n
      or  {"id": <str>, "ok": false, "error": {"code": <str>, "message": <str>}}\n
```

Response key order is **not stable** — parse as JSON only (research R1).

| Verb | Method sequence | Params |
|---|---|---|
| `open-pane` (new workspace) | `workspace.list` → `workspace.create` | `{"name": <session-id>}` |
| `open-pane` (existing workspace) | `workspace.list` → `surface.create` | `{"workspace_id": <uuid>, "type": …, "url"\|"command": …}` |
| `open-pane` (no `--workspace`) | `surface.create` | `{"type": …, "url"\|"command": …}` — caller's workspace |
| `navigate-pane` | `browser.navigate` | `{"surface_id": <pane>, "url": <url>}` |
| `notify` | `notification.create` | `{"title": "battle-buddy: <level>", "body": <message>}` |
| `close-workspace` | `workspace.list` → `workspace.close` | `{"workspace_id": <uuid>}` |

**Reattach** (spec edge case) is the `workspace.list` step: match on `title == session-id`.
No shim state — the backend's own truth is read on every invocation (FR-009).

## 6. Fault matrix (FR-005, SC-003)

Six fault classes × four verbs = **24 cases**, every one asserting the same three
properties: degraded output on stdout, **exit 0**, a diagnostic note on stderr — and none
hanging.

This is a deliberate **superset** of SC-003, which names four classes (16 cases). Classes 5
and 6 are protocol failures rather than socket failures; they are added because FR-005's
promise is that *a shell failure never surfaces as a session error*, and a malformed reply
is a shell failure the socket-level list would miss.

| # | Class | Injection | Real cause |
|---|---|---|---|
| 1 | absent | socket path does not exist | cmux never ran |
| 2 | refused | `ConnectionRefusedError` | stale socket file, app dead |
| 3 | timeout | accept, never reply | app wedged |
| 4 | mid-write death | accept, partial read, close | app crashed mid-call |
| 5 | error response | `{"ok": false, "error": {…}}` | method/params rejected |
| 6 | malformed line | truncated or non-JSON bytes | protocol drift |
| 7 | wrong-shaped result | `ok:true` with a non-object `result` | protocol drift |

Classes 5 and 6 are not socket faults but **must degrade identically** — the requirement is
"a shell failure never surfaces as a session error", not "a socket failure".

Class 7 was added during review, after it crashed with an uncaught `AttributeError`: a reply
that parses cleanly and says `ok:true` while carrying a non-object `result` is the shape that
bites, because nothing fails until a caller reads a field. It is **not** part of the
every-verb matrix — verbs that never read a result (`notify`, `navigate-pane`) genuinely
succeed, and asserting a fallback for them would assert a bug. It is fixed by normalizing at
the boundary, not by widening the `except` clause.

**Per-invocation independence** (FR-009, US2 AS3): repeated faults in one session produce
identical fallbacks — no lockout, no retry, no backoff, no health memory. Tested as N
sequential invocations against a permanently-dead fake, asserting N identical outcomes.

## 7. Captured-traffic scan (FR-006, SC-004)

Every request frame the fake socket captures across the **whole** unit suite is scanned.
Allowed JSON leaf content: workspace/pane/surface identifiers, URLs, messages, levels,
titles/bodies, and the fixed method/param key names of §5.

The scan asserts absence of a denied vocabulary — `cookie`, `password`, `token`,
`credential`, `session_state`, `localStorage`, `eval`, `script`, `html`, `screenshot`,
`snapshot` — and, more strongly, that **every method name sent is one of the five in §5**.
The method-allowlist form is the load-bearing half: cmux's socket exposes 221 methods
including `browser.eval`, `browser.cookies.get`, and `browser.storage.*`, so the boundary
that matters is which methods the shim can ever name (research R14).

## 8. Exit codes and channels (research R8)

| Code | Meaning |
|---|---|
| `0` | verb succeeded via backend **or** via degraded fallback — indistinguishable by design |
| `2` | usage error only (§1) |

stdout = the responder-facing link/message. stderr = diagnostic notices (fallback
occurred, config unrecognized, env-var conflict) and usage text. There is no exit code for
backend failure; **that absence is the requirement** (FR-005).
