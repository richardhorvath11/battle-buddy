# Research: Shell Adapter (slice 9)

Plan-time pins. The spec's Assumptions delegate three things to this document —
the cmux wire protocol ("the plan pins framing against the real API"), the
fourth verb's name and semantics, and the socket-failure taxonomy. Everything
below is either verified against the real cmux binary/socket on 2026-07-22 or
derived from an artifact already committed in this repo; nothing here is a guess
presented as a fact, and the two places where a residual gap remains say so.

---

## R1 — cmux wire protocol: transport and framing

**Decision.** `AF_UNIX` / `SOCK_STREAM`; **newline-delimited JSON**, one request
line → one response line.

```
request   {"id": <str|int>, "method": <str>, "params": {…}}\n
response  {"id": <same>, "ok": true,  "result": {…}}\n
      or  {"id": <same>, "ok": false, "error": {"code": <str>,
                                                "message": <str>, "data": {…}?}}\n
```

**Verification.** Probed the live socket directly (not through the CLI):
`{"id":"1","method":"ping","params":{}}\n` →
`{"ok":false,"error":{"code":"method_not_found","message":"Unknown method"},"id":"1"}\n`.
`capabilities` self-reports `{"protocol":"cmux-socket","version":2,…}`.

**Pin with teeth: response key order is NOT stable.** The same server returned
`{"ok",…,"id"}` for one call and `{"id","ok",…}` for the next. The shim MUST
parse as JSON and MUST NOT assume key order or use string matching on the frame.
The fake socket in the test suite deliberately varies key order across fixtures
so a positional-parsing regression fails loudly.

**Alternatives considered.** Length-prefixed framing and JSON-RPC 2.0 envelopes —
both refuted by probe: a `{"jsonrpc":"2.0",…}` envelope is accepted only because
the extra key is ignored, and the response carries `ok`, not `jsonrpc`. This is
cmux's own envelope, not JSON-RPC.

## R2 — Socket discovery and auth

**Decision.** Resolution order, highest first:

1. `$CMUX_SOCKET_PATH` (canonical).
2. Default `~/.local/state/cmux/cmux.sock`.

`$CMUX_SOCKET` is a **deprecated alias**; the cmux CLI *fails* when both are set
and differ. The shim adopts the same rule rather than silently preferring one —
a disagreeing pair is a config error the responder must see. Because a usage
error must be loud (FR-005) but a *backend availability* problem must not, this
case is pinned as: **treat as a degraded fallback with a diagnostic notice**, not
a nonzero exit — the responder mistyped an env var, which is not a caller bug in
the slice-5 sense, and bricking a session over it would invert FR-005's intent.

**Residual gap, stated honestly.** The observed real socket on the development
machine is `~/.local/state/cmux/cmux-501.sock` (`cmux-<uid>.sock`), not
`cmux.sock`, and the CLI documents "auto-discovery of tagged/debug sockets"
without publishing the discovery algorithm. `/tmp/cmux-last-socket-path` also
held the live path. The shim does **not** reimplement undocumented discovery: it
tries `$CMUX_SOCKET_PATH`, then the documented default, and falls back to
degraded mode if neither connects. Teams whose socket is tagged set
`CMUX_SOCKET_PATH` — which cmux's own docs present as the supported override.
Reimplementing discovery would couple us to an unpublished detail that can change
under us; failing soft to degraded is exactly the posture FR-005 mandates.

**Auth — not supported in v1, deliberately.** cmux resolves `--password`, then
`$CMUX_SOCKET_PASSWORD`, then a password stored in Settings. The probes here
required none (`capabilities` reported `access_mode: cmuxOnly`), so the
*handshake* was never observed and is not publicly documented.

Implementing it blind would mean guessing a security-relevant protocol. The shim
therefore connects without authentication and never reads the password variable
at all; on a socket that demands it, the connection is rejected and the verb
degrades like any other backend failure. **No credential can reach a request
frame, a log line, or a diagnostic** (FR-006) — trivially, since none is read.

*(Corrected in review round 2: an earlier draft of this section and of
`bin/bb-shell.cmux.md` claimed the shim passed the password through. It never
did. A shipped document asserting a security behavior the code does not
implement is worse than the missing feature.)*

## R3 — Verb → method + param mapping

Params use `_id` suffixes. The server rejects the un-suffixed form with an error
that *names the right one* — e.g. sending `window` to `workspace.create` returns
``Unsupported parameter `window`; use `window_id` …`` with
`data: {method, supported_param, unsupported_param}`. All four verbs map to
methods present in the live 221-entry `capabilities` method list.

| Verb | cmux method(s) | Params |
|---|---|---|
| `open-pane` | `workspace.create` when the named workspace does not exist, else `surface.create` into it | `workspace.create`: `name`, `cwd?`, `command?`, `window_id?` · `surface.create`: `type` (`terminal`\|`browser`), `url?`, `workspace_id` |
| `navigate-pane` | `browser.navigate` | `surface_id`, `url` |
| `notify` | `notification.create` | `title`, `body`, `subtitle?`, `workspace_id?`, `surface_id?` |
| `close-workspace` | `workspace.close` | `workspace_id` |

Handles accept UUIDs, short refs (`workspace:2`, `surface:4`), or indexes.
`workspace.list` returns `id`, `workspace_ref`, `index`, `title`, `selected`.

**`surface.create`, not `pane.create` — pinned.** cmux offers both: a *pane* is a split
container, a *surface* is the tab inside it that actually renders a terminal or a browser.
`open-pane` wants a rendered thing, so `surface.create` is the correct method and
`pane.create` would additionally split the layout, which no requirement asks for. Recorded
because the verb is *named* `open-pane` and the wrong method is the natural guess.

**Verified error codes:** `method_not_found`, `invalid_params`. The shim treats
**every** `ok:false` as a backend failure → degraded fallback (FR-005), and never
tries to interpret the code beyond putting `message` in the diagnostic note.

## R4 — `notify --level` has no cmux equivalent *(pin)*

**Problem.** §6.3 and FR-001 require `notify <message> --level <info|warn|approval>`,
and US1 AS4 asserts "the level reaches the backend". `notification.create` accepts
only `title`, `subtitle`, `body` — there is no level, priority, or urgency field.

**Decision.** The level is carried in **`title`**, as `battle-buddy: <level>`,
with the message in `body`. Rationale: `title` is the field cmux renders most
prominently and the one `notification.list` always returns populated, so the
assertion "the level reached the backend" is checkable against captured traffic
(SC-004 scans exactly these fields). `subtitle` was rejected — it is optional in
cmux's own model and was observed empty (`""`) on real notifications, making it
the field most likely to be dropped or restyled by a future cmux release.

**Verified.** `notification.create` with `{"title":"t","body":"b"}` returned
`ok:true` with `{surface_id, workspace_id}` and the notification appeared in
`notification.list` with both fields intact. (The probe notification was
dismissed via `notification.dismiss {"id": …}` — note that method takes `id`,
not `notification_id`.)

## R5 — `--level` is optional, defaulting to `info` *(cross-slice reconciliation)*

**Finding.** Slice 4 already consumes this verb with **no level at all**:
`tests/helpers/doctor_flows.py::check_shell` calls `adapter.notify(probe_message)`
and `doctor_fixtures.FixtureShellAdapter.notify(self, message)` takes one
argument. §6.3 writes `--level` as though mandatory.

**Decision.** `--level` is **optional and defaults to `info`**. A mandatory flag
would break slice 4's doctor round-trip the moment the real shim replaces the
fixture — a landed-slice regression discovered at plan time rather than in
slice-4's CI, which never exercises the real shim.

**Consequence.** An *unrecognized* `--level` value is a usage error (nonzero,
loud — FR-005), because it is a caller bug; an *absent* one is not. This mirrors
FR-002's own absent-vs-unrecognized split for `battleBuddy.shell` exactly, which
is the strongest argument that it is the intended reading.

## R6 — Slice-5 pins the verb names; `pane` means cmux *surface*

**Verb names.** `tests/helpers/lifecycle_fixtures.py::RecordingShellAdapter` is a
landed, consumed boundary pinning `open_pane(target, workspace=None)`,
`navigate_pane(pane, url)`, `notify(message, level)`, `close_workspace(session_id)`.
The CLI verbs are the kebab-case of exactly these — `open-pane`, `navigate-pane`,
`notify`, `close-workspace` — which also settles the spec's FR-001 "name at plan
time" delegation: the name was already chosen by a merged slice, so choosing
anything else would be the change.

**Terminology.** `browser.navigate` addresses a **`surface_id`**; in cmux's model
a *pane* contains *surfaces*. The backend-independent interface keeps saying
"pane" (FR-007, and slice 5 already calls it that); the **cmux backend document**
owns the pane→surface mapping. This keeps the concrete backend's vocabulary out
of the contract doc, which is what US4 AS1 asserts.

## R7 — Fault taxonomy and the fake socket

**Decision.** Four fault classes, one per FR-005 clause, each a fake-socket
fixture:

| Class | Injection | Real-world cause |
|---|---|---|
| absent | socket path does not exist (`FileNotFoundError`) | cmux never ran; wrong path |
| refused | `ConnectionRefusedError` on connect | socket file stale, app dead |
| timeout | accept, then never reply (`socket.timeout`) | app hung/wedged |
| mid-write death | accept, read part, close (`BrokenPipeError`/`ConnectionResetError`) | app crashed mid-call |

Plus two protocol-level faults that are *not* socket faults but must degrade
identically: `ok:false` error responses, and a malformed/truncated response line
(`json.JSONDecodeError`). Six cases × four verbs is the SC-003 matrix.

**Timeout value: 2.0s**, applied to connect and to each recv. Rationale: the
shim sits in the 3am path (NFR-1) and every call is local IPC where a healthy
reply is sub-millisecond; a wedged app must not add perceptible latency to a
session. Pinned as a module constant so a test can assert it is set at all —
an unset timeout is the actual hang risk FR-005/SC-003 forbid.

**The fake is a real Unix socket**, not a monkeypatched `socket` module: a
`socketserver`-style listener on a `tmp_path` socket file, so framing, partial
reads, and connection teardown are exercised for real while staying hermetic
(no network, no cmux). This follows slice 1/2's "fake, not mock" posture and is
what makes SC-004's traffic capture meaningful — the assertion runs on bytes that
actually crossed a socket.

## R8 — Module layout, exit codes, and output channels

**Layout** follows the landed `bb-validate` / `bb-fingerprint` precedent exactly:
`bin/bb-shell` (extensionless, `#!/usr/bin/env python3`, inserts its own dir on
`sys.path`, calls `main()`) + `bin/bb_shell.py` (the implementation module).
Verified: neither existing `bin/*.py` imports any local sibling — `bin/` modules
are self-contained, so `bb_shell.py` reads config itself rather than importing
`hooks/_config.py` across bundle directories (see R10).

**Exit codes** (bb-fingerprint precedent: `0` ok / `2` usage error):

- `0` — verb succeeded via the backend **or** via degraded fallback. Fail-soft
  means these are indistinguishable in the exit code by design (FR-005).
- `2` — usage error only: unknown verb, missing/extra positional, unrecognized
  `--level`, unparseable flags (FR-005, SC-006).

There is deliberately **no** nonzero code for backend failure. That absence is
the requirement.

**Channels.** Degraded output (the link/message the responder reads) → **stdout**.
Diagnostic notices (fallback happened, config unrecognized, env-var conflict) →
**stderr**. A caller capturing stdout gets exactly the user-facing artifact; a
caller ignoring stderr still exits 0. Usage errors print usage to stderr.

## R9 — Stdlib allowlist extension *(SC-005, deliberate and reviewed)*

`tests/unit/test_stdlib_boundary.py` walks `bin/` already, so SC-005 needs no new
gate — but the shim's imports must be added to its allowlist, which that test's
own comment frames as "grow deliberately". This slice adds:

- `ALLOWED_STDLIB`: **`socket`** (the backend transport). `errno` is already
  present; `argparse`, `json`, `os`, `sys` are already present.
- `LOCAL_MODULES`: **`bb_shell`**.

No other module is needed: framing is `json`, discovery is `os.environ` +
`os.path`, timeouts are `socket.settimeout` (no `select`, no `signal`, no
threads). Any addition beyond this list is a review-visible diff on a
security-relevant allowlist — which is the point of the mechanism.

## R10 — Config reading: `bb_shell` reads its own

**Decision.** `bb_shell.py` implements a minimal `battleBuddy.shell` reader
rather than importing `hooks/_config.py`.

**Rationale.** `hooks/_config.py`'s docstring pins it as "a module shipped beside
its consumers" — a hooks-bundle module. `bin/` shims put only their own directory
on `sys.path`; importing across bundle directories would be a new coupling
between two independently-shipped plugin dirs, and `test_stdlib_boundary.py`'s
`LOCAL_MODULES` is a flat set that would then stop distinguishing them.

**What is reused is the *posture*, precisely:** read exactly
`<root>/.claude/settings.json` → `battleBuddy` block; malformed anything is
treated as absent with a notice; never raise; never write. FR-002's split is
implemented on top: key **absent → silent** degraded; key **present but
unrecognized → degraded + notice**. Root is the current working directory
(the workspace repo, per §2.1 "you run `/page` from the workspace repo").

**Honest note:** this is duplicated logic, ~20 lines. The alternative — a shared
`bin/_config.py` plus a `hooks/` copy, or a cross-directory import — trades a
small duplication for either a second copy anyway or a new structural coupling.
Recorded here so a later reviewer sees a decision, not an oversight.

## R11 — Workspace creation, reattach, and caller-driven composition

**Decision.** `open-pane --workspace <session-id>` resolves as: `workspace.list`
→ match a workspace whose `title` equals the session ID → if found, add a pane to
it (`pane.create`/`surface.create` with its `workspace_id`); if not, create it
(`workspace.create` with `name = <session-id>`).

This implements FR-004's caller-driven composition (first call creates, later
calls add panes) and the spec's reattach edge case ("workspaces survive
restarts") **without the shim holding any state** — the lookup is a read of the
backend's own truth on every invocation, which is what keeps FR-009's
pure-function property true and makes concurrent invocations safe.

**Target type:** `open-pane <url|command>` — an argument parsed as a URL (has a
scheme) opens a **browser** surface with `url`; anything else is treated as a
command and opens a **terminal** surface. The spec's edge case requires the
command form to work (it is how the agent terminal pane itself is opened).

**Residual gap.** `pane.create`/`surface.create` param names beyond
`type`/`url`/`workspace_id` were not probed — probing them would have created
real panes in the developer's live cmux session. The implementation task
verifies them the same way R3's were verified: send a deliberately unresolvable
handle and read the `invalid_params` message, which cmux writes to name the
correct parameter. This is a bounded, mechanical check, not open research.

## R12 — Degraded output format

**Decision.** One line per call on stdout:

```
open-pane        bb-shell: open <target>  [workspace: <session-id>]
navigate-pane    bb-shell: <url>  (pane <pane>)
notify           bb-shell: [<level>] <message>
close-workspace  bb-shell: close workspace <session-id>
```

Every line carries the same information the backend call would have conveyed
(FR-003) and each is `grep`-able by verb. The URL appears bare and unwrapped so a
terminal's own link detection can make it clickable — degraded mode's entire
value at 3am is that the responder can still click through.

**Consistency with slice 5.** `lifecycle_fixtures.PrintedOutput` models degraded
entries as `{"kind": "message"|"link"}` records. That is an *in-process flow*
shape for slice-5's tests; the shim is a *process* whose interface is stdout
text. They are not required to match, and forcing JSON on stdout would make the
3am path less readable, not more. Recorded so the divergence is a decision.

## R13 — Interface documentation location

**Decision.** Two documents in `bin/`, beside the shim:

- `bin/bb-shell.md` — the backend-independent adapter contract (FR-007, D-2):
  every verb's arguments, semantics, degraded behavior, failure behavior, with
  **no concrete backend named**.
- `bin/bb-shell.cmux.md` — the cmux backend mapping: socket discovery, framing,
  method/param table, level encoding, pane→surface terminology.

**Rationale.** The split is what makes US4's mechanical scan expressible: "no
shell-product name appears in any command/skill deliverable, nor in the contract
doc — only in the backend document." A single file with a cmux appendix would
force the scan to reason about sections. `bin/` is chosen over a new top-level
`docs/` because AGENTS.md's Allowed path tier enumerates the plugin dirs and
`bin/` is one; a new bundle root is a packaging decision this slice does not need
to make. `.md` files are invisible to `test_stdlib_boundary.py`'s walk (it
selects `*.py` and extensionless shebang files), so nothing else shifts.

## R14 — What this slice does NOT do

Recorded so scope is a decision rather than an omission:

- **No retry, no backoff, no health memory.** Spec-pinned (stateless shim); each
  invocation attempts and falls back independently, which is what makes R-2
  recovery automatic.
- **No notification delivery beyond cmux.** Degraded `notify` prints; system
  notifications are a future backend concern (spec Assumptions).
- **No pane content, cookie, storage, or eval access.** cmux exposes
  `browser.eval`, `browser.cookies.*`, `browser.storage.*` in its 221-method
  surface; the shim binds **four** methods and the interface admits no argument
  that could reach the others. This is FR-006's structural boundary — and it is
  worth stating that the boundary is *ours*, not cmux's: the capability exists on
  the socket and we decline to expose it.
- **No `wmux`/Linux backend.** R-1 stands; degraded mode is the non-Mac path.
