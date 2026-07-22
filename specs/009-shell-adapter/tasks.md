# Tasks: Shell Adapter

**Input**: Design documents from `/specs/009-shell-adapter/`

**Prerequisites**: plan.md, spec.md, research.md (R1–R14), data-model.md, quickstart.md

**Tests**: REQUIRED — Constitution VIII (code without its tests in the same change is
incomplete) and FR-008 (hermetic unit coverage of every listed behavior). Code and test
tasks are paired inside each story; a story's checkpoint is `make verify` green, and the
**phase**, not the individual task, is the commit seam.

**Organization**: By user story, in spec priority order. US1 and US2 are both P1 and form
the MVP seam together — US1 makes the verbs work, US2 makes them *never* take a session
down, and shipping US1 alone would ship the exact failure mode R-2 exists to retire. US3
(P2) and US4 (P3) are droppable per the scope-cut rule; neither owns a file another phase
needs.

**Platform floor**: every shipped line is Python 3.9-compatible, stdlib only. `bin/` modules
import no local siblings (research R10) — `bb_shell.py` is self-contained.

**Artifact converge round 1 applied** (`/speckit-analyze`, 7 findings — 6 fixed, 1
disclosed-as-gap). The two that changed this file's shape were both CRITICAL and both mine:
no task *created* `tests/unit/test_shell_dispatch.py` (two later tasks only added to it), so
SC-006 had zero coverage — now T006; and Phase 2 shipped the grammar and config reader with
no test task in the phase, which is a Constitution VIII violation at the commit seam — T006
closes that too. Also fixed: the concurrent-invocation edge case and quickstart's
"no file writes" claim were untested (T015), and `pane.create`/`surface.create` drifted
across artifacts (pinned to `surface.create`, research R3).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallelizable (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 per spec.md

---

## Phase 1: Setup

**Purpose**: the files whose *existence* no story may own, plus the allowlist edit that must
land before the first `import socket` or `make verify` goes red mid-phase.

- [x] T001 Create the shim pair whose existence every later task assumes:
      (a) `bin/bb-shell` — extensionless launcher, `#!/usr/bin/env python3`, docstring citing
      D-2 and the interface, `sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))`,
      `from bb_shell import main`, `sys.exit(main())`. Copy the shape of `bin/bb-validate`
      exactly, including the exit-code line in the docstring (`0 ok / 2 usage error`).
      Must be `chmod +x` — the two landed shims are executable and a non-executable shim
      fails the moment a command shells out to it.
      (b) `bin/bb_shell.py` — module skeleton with the module docstring (design §6.3, D-2,
      the four verbs, the fail-soft rule, stdlib-only/3.9 note) and a `main(argv=None)` that
      currently prints usage and returns `2`. No `socket` import yet; T002 lands first in the
      same phase so the boundary test never observes an un-allowlisted import
- [x] T002 Extend `tests/unit/test_stdlib_boundary.py`'s allowlists per research R9 and
      SC-005 — `ALLOWED_STDLIB` gains **`socket`**; `LOCAL_MODULES` gains **`bb_shell`**.
      Add a comment on the `socket` entry recording *why* it is allowed (the cmux backend
      transport, slice 9, reviewed addition) so the next reader sees a decision rather than
      a name. Nothing else is added: `argparse`, `json`, `os`, `sys`, `errno` are already
      present, and the shim needs no `select`/`signal`/`threading` (research R9). This task
      is deliberately its own commit-visible diff on a security-relevant allowlist
- [x] T003 [P] Create `tests/helpers/fake_cmux.py` — the fake backend (research R7): a
      **real** `AF_UNIX` listener on a `tmp_path` socket file, not a monkeypatched `socket`
      module, so framing, partial reads, and teardown are exercised for real. Surface:
      a context manager yielding the socket path; `captured` — the list of decoded request
      frames in send order; a scripted-response queue keyed by method; and the six fault
      modes of data-model.md §6 (`absent`, `refused`, `timeout`, `mid_write_death`,
      `error_response`, `malformed_line`). Responses MUST be emitted with **varied JSON key
      order** across fixtures (research R1: cmux's own key order is unstable) so a
      positional-parsing regression fails here rather than in production. Runs on a thread
      with a hard join timeout so a wedged fake can never hang CI

**Checkpoint**: `make verify` green — T001's skeleton is importable, the boundary walk sees
`bin/bb_shell.py` and passes, and the fake is unused but self-testable.

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the two pure functions every story sits on. Both are argument/config → value
with no I/O, which is what makes FR-009's property testable at all.

- [x] T004 Implement the argument grammar and dispatch in `bin/bb_shell.py` per
      data-model.md §1: the four verbs with their exact positional counts and options, and
      **nothing else**. `--level` is optional defaulting to `info`, with the closed set
      `{info, warn, approval}` (research R5 — a mandatory flag breaks slice 4's landed
      `check_shell` round-trip, which calls `notify(message)` with no level). Usage errors
      — unknown verb, absent verb, wrong positional count, unknown option, out-of-set
      `--level` — print usage to **stderr** and return **2**. Parsing MUST be a function
      returning a parsed structure, not one that acts, so tests can assert on it directly.
      Use `argparse` with subparsers; set `add_help` such that `-h` works but no argparse
      path can `sys.exit` out from under `main()` unhandled
- [x] T005 Implement config selection in `bin/bb_shell.py` per data-model.md §3 and
      research R10: read `<cwd>/.claude/settings.json` → `battleBuddy` → `shell`; never
      raise, never write, return `(backend_name, notices)`. Implement FR-002's split
      exactly — **absent key → degraded, silent**; **unrecognized value or wrong type →
      degraded, with a notice**; missing `battleBuddy` block → silent; unreadable/malformed
      settings file → notice. Do **not** import `hooks/_config.py` (research R10 records
      why); mirror its posture, not its code. The six-row table in data-model.md §3 is the
      test's oracle, and the absent-vs-unrecognized split is three tests, not one
- [x] T006 **Create** `tests/unit/test_shell_dispatch.py` — the module T018 and T021 later
      extend, landing in the **same phase as the code it covers** (Constitution VIII: the
      phase is the commit seam, so T004/T005 must not be committed untested). Covers: the
      grammar as a pure function over data-model.md §1 (all four verbs, exact positional
      counts, options); **SC-006** — every usage-error class exits **2** with usage on
      stderr (unknown verb, absent verb, wrong positional count, unknown option,
      out-of-set `--level`); `--level` defaulting to `info` plus the closed-set rejection
      (research R5); and the config-selection table of data-model.md §3 row by row,
      including the absent-silent vs unrecognized-noticed split. *Analyze findings D1/D2:
      without this task no module exists for the later phases to add to, and SC-006 would
      have carried zero coverage.*

**Checkpoint**: `make verify` green — the grammar and config reader ship **with** their
tests. No backend behavior yet; both stories can now start.

---

## Phase 3: User Story 1 — One screen at 3am, or plain links (P1)

**Goal**: every verb does its real work through a configured backend, and does an
equally-first-class printed thing without one.

**Independent test**: invoke all four verbs under `shell: none` and assert printed output;
invoke them under a fake-socket cmux backend and assert the protocol frames sent.

- [x] T007 [US1] Implement `DegradedBackend` in `bin/bb_shell.py` — all four methods,
      rendering the one-line-per-call format pinned in research R12 to **stdout**, returning
      success. URLs print bare and unwrapped so terminal link detection can make them
      clickable. `open-pane` prints for both the URL and the command form (spec edge case;
      this slice owns the pin that supersedes design §3.2 step 3's "no-op in degraded mode")
- [x] T008 [US1] Write `tests/unit/test_shell_degraded.py` — SC-002: four verbs × the three
      selection paths (`none`, absent, unrecognized) all produce the correct printed output
      and exit 0, **plus** the notice-scoping assertions from data-model.md §3: stderr is
      empty for absent, non-empty for unrecognized. Assert the exact text shape, since
      "degraded output exists" would pass on a bare newline
- [x] T009 [US1] Implement `CmuxBackend`'s transport in `bin/bb_shell.py` per research
      R1–R2: socket discovery (`$CMUX_SOCKET_PATH` → `~/.local/state/cmux/cmux.sock`),
      the `$CMUX_SOCKET`-disagreement rule (degraded + notice, **not** a nonzero exit —
      research R2 records why), `$CMUX_SOCKET_PASSWORD` passthrough that never logs the
      value (FR-006), the **2.0s** timeout as a named module constant applied to connect
      and every recv, and one request line → one response line with JSON-only parsing.
      Reading the response MUST loop until a newline: a single `recv` is the classic
      partial-read bug and the fake's mid-write mode exists to catch it
- [x] T010 [US1] Implement the verb→method mapping in `CmuxBackend` per data-model.md §5:
      `open-pane` (`workspace.list` → `workspace.create` when no workspace titled
      `<session-id>` exists, else `surface.create` into its `workspace_id`; no `--workspace`
      → `surface.create` in the caller's workspace), `navigate-pane` → `browser.navigate`
      with `surface_id`, `close-workspace` → `workspace.list` → `workspace.close`. Target
      typing per data-model.md §4 (URL scheme → `browser` + `url`; else `terminal` +
      `command`). Reattach is a **backend read every invocation** — no shim state (FR-009).
      **Verification step this task owns**: `surface.create`'s param names beyond
      `type`/`url`/`command`/`workspace_id` were not probed at plan time (research R11's
      stated gap); confirm them by sending a deliberately unresolvable handle to a live cmux
      and reading the `invalid_params` message, which names the correct parameter. If no
      live cmux is available, implement to the documented CLI flag names and record the
      unverified params inline — do not silently guess
- [x] T011 [US1] Implement `notify`'s level encoding per research R4: `notification.create`
      with `title = "battle-buddy: <level>"` and `body = <message>`. cmux has no level field;
      this is the pin that makes US1 AS4's "the level reaches the backend" checkable against
      captured traffic. Record the choice in a comment citing R4 (title over subtitle:
      subtitle is optional in cmux's model and observed empty on real notifications)
- [x] T012 [US1] Write `tests/unit/test_shell_cmux.py` — the request envelope
      (`{"id","method","params"}` + trailing newline), the method/param table of
      data-model.md §5 per verb, response parsing **with varied key order**, workspace
      create-vs-reattach (both branches, asserting `workspace.create` is *not* sent when a
      titled workspace already exists), target typing both ways, and the level encoding.
      Assertions are on the captured frames, never on the backend's return value alone

**Checkpoint**: `make verify` green; US1 independently testable and demonstrable by hand
per quickstart.md.

---

## Phase 4: User Story 2 — A dead shell never takes the investigation with it (P1)

**Goal**: any backend failure becomes the degraded output, exit 0, and a diagnostic note.

**Independent test**: run every verb against every fault fixture; assert degraded output,
exit success, a note, and no hang.

- [x] T013 [US2] Implement the fail-soft wrapper in `bin/bb_shell.py` (FR-005): a single
      seam wrapping every `CmuxBackend` call that catches `BackendError`, `OSError`
      (covers `socket.error`, `ConnectionRefusedError`, `FileNotFoundError`,
      `BrokenPipeError`, `ConnectionResetError`, `socket.timeout`) and
      `json.JSONDecodeError`, then produces the **same** degraded output the
      `DegradedBackend` would have, writes a diagnostic note to **stderr**, and returns 0.
      An `ok:false` error response degrades identically (data-model.md §6 classes 5–6 are
      not socket faults but must be indistinguishable in outcome). Usage errors are raised
      before any backend is constructed, so they can never reach this seam — that ordering
      is the mechanism keeping FR-005's two halves from colliding
- [x] T014 [US2] Write `tests/unit/test_shell_failsoft.py` — the **24-case matrix**
      (6 fault classes × 4 verbs) of data-model.md §6, each asserting all three properties
      together: degraded stdout, exit 0, non-empty stderr note. A case that asserts only the
      exit code would pass on silence, which SC-003 explicitly forbids
- [x] T015 [US2] Add the per-invocation independence test to
      `tests/unit/test_shell_failsoft.py` (US2 AS3, FR-009): N sequential invocations against
      a permanently-dead fake produce N **identical** outcomes — no lockout, no backoff, no
      retry, no health memory. Then the recovery direction, which is what makes the property
      worth having: a dead fake followed by a live one produces a *successful* backend call
      on the next invocation with no intervening reset. Two further properties the same task
      owns, both from analyze findings C1/C2: **concurrency** — the spec's concurrent-
      invocation edge case (spec.md Edge Cases: "each invocation is an independent process
      with its own socket connection … no shared state in the shim") is asserted by driving
      several invocations against one fake from separate threads and checking every one
      succeeds with its own frames captured; and **no writes** — the invocation touches no
      file other than reading `.claude/settings.json`, asserted by snapshotting the
      `tmp_path` tree before and after. quickstart.md's FR-009 row claims both, so both are
      tested rather than asserted in prose
- [x] T016 [US2] Add the no-hang assertion to `tests/unit/test_shell_failsoft.py`: the
      timeout constant is set on the socket (assert the module constant is a positive float
      **and** that it is actually applied — an unset timeout is the real hang risk), and the
      `timeout` fault case completes well inside a test-level bound

**Checkpoint**: `make verify` green. **This is the MVP seam** — US1 + US2 together.

---

## Phase 5: User Story 3 — The responder's SSO is theirs alone (P2)

**Goal**: the interface is structurally incapable of credential access.

**Independent test**: scan every request frame the suite captured; inspect the grammar.

- [x] T017 [US3] Add the captured-traffic scan to `tests/unit/test_shell_failsoft.py` per
      data-model.md §7 (SC-004): over frames captured across the suite, assert the denied
      vocabulary (`cookie`, `password`, `token`, `credential`, `session_state`,
      `localStorage`, `eval`, `script`, `html`, `screenshot`, `snapshot`) appears nowhere,
      **and** — the load-bearing half — that every `method` sent is one of the five in
      data-model.md §5. cmux's socket exposes 221 methods including `browser.eval` and
      `browser.cookies.get`; the boundary that matters is which methods the shim can name
- [x] T018 [US3] Add the structural grammar assertion to `tests/unit/test_shell_dispatch.py`
      (FR-006 AS1): the parser accepts **exactly** the verbs and options of data-model.md §1
      and rejects everything else, including plausible credential-shaped options
      (`--cookie`, `--token`, `--header`, `--eval`). The scan in T017 only proves the
      *tested* calls stayed clean; this proves nothing else is expressible. Both are needed
      and the plan's Constitution Check says so

**Checkpoint**: `make verify` green; US3 adds no shipped behavior, only proof.

---

## Phase 6: User Story 4 — Any future shell slots in behind the same verbs (P3)

**Goal**: the interface documented as a backend-independent contract (D-2).

**Independent test**: the contract doc defines every verb without naming a backend; the
mechanical scan finds no shell-product name in other slices' deliverables.

- [x] T019 [P] [US4] Write `bin/bb-shell.md` — the backend-independent adapter contract
      (FR-007, D-2): for each of the four verbs, its arguments, semantics, degraded
      behavior, and failure behavior; the config-selection table; the exit-code contract;
      and the fail-soft rule. **Names no concrete backend** — not cmux, not tmux, not any
      product. This document is what a future shell implements against, so it is written for
      that reader, not as a summary of the code
- [x] T020 [P] [US4] Write `bin/bb-shell.cmux.md` — the cmux backend mapping: socket
      discovery order and the env-var disagreement rule, the wire envelope, the
      method/param table, the level encoding and why (research R4), the pane→surface
      terminology note (research R6), and research R2/R11's two residual gaps stated as
      gaps. This is the **only** shipped file permitted to name the product
- [x] T021 [US4] Add the documentation gates to `tests/unit/test_shell_dispatch.py`:
      `bin/bb-shell.md` exists and documents all four verbs (FR-007); the backend-name scan
      (US4 AS2) over `commands/`, `skills/`, `agents/`, and `bin/bb-shell.md` finds no shell
      product name, with `bin/bb-shell.cmux.md` as the single allowed exception and a
      **positive control** proving the scan can actually fail. Reuse the scan mechanism
      slice 7 established in `tests/contract/test_skill_capability_naming.py` rather than
      inventing a second one

**Checkpoint**: `make verify` green.

---

## Phase 7: Polish & cross-cutting

- [x] T022 Amend `bb-technical-design.md` per spec FR-001 and Assumptions ("flagged for
      design-doc reconciliation"): §6.3's three-verb interface block gains the fourth verb
      `close-workspace <session-id>`, and the decision log gains a **D-2 addendum** row
      recording the addition, the `--level`-optional pin (research R5), and the level
      encoding (research R4). The design doc is upstream of specs (Constitution Development
      Workflow) — the gap was the design's, and this closes it in the same PR that relies
      on it, per "hard-to-reverse decisions amend the decision log in the same change"
- [x] T023 Update `AGENTS.md`'s build-order line to mark slice 9 landed. **Conflict note**:
      slice 8 is in flight on a parallel branch and touches the same line; resolve by
      keeping both slices' status rather than either side's whole line
- [x] T024 Run quickstart.md's manual validation against a live cmux (macOS): all four
      verbs with `shell: cmux`, then kill cmux and re-run to observe the degraded fallback
      and exit 0. CI cannot prove cmux's fidelity (plan Constitution Check, gate II) — this
      is the human step that does, and its result goes in the PR body

---

## Dependencies

```
Phase 1 (T001–T003)  ──►  Phase 2 (T004–T005)  ──┬──►  Phase 3 US1 (T007–T012)
                                                 │              │
                                                 │              ▼
                                                 │     Phase 4 US2 (T013–T016)   ◄── MVP seam
                                                 │              │
                                                 ├──────────────┴──►  Phase 5 US3 (T017–T018)
                                                 └───────────────────►  Phase 6 US4 (T019–T021)
                                                                              │
                                                                              ▼
                                                                     Phase 7 (T022–T024)
```

- **US2 depends on US1**: the fail-soft wrapper wraps calls that must exist first, and its
  fallback output *is* the degraded backend from T007.
- **US3 depends on US1** (traffic to scan) but not on US2.
- **US4 is independent of US2/US3** — docs and a scan; it needs only the verb set from T004.

## Parallel opportunities

- T003 is `[P]` with T001/T002 — different files, no shared state.
- T019 and T020 are `[P]` with each other (two separate documents).
- Within Phase 3, T007/T008 (degraded) and T009 (transport) touch the same module and are
  **not** parallel; the test modules they produce are distinct files but the implementation
  is one file, so they run serially through the orchestrator.

## Implementation strategy

**MVP = Phase 1 → 2 → 3 → 4** (US1 + US2). That is a shipped `bb-shell` that works with and
without cmux and cannot take a session down. US3 and US4 add proof and documentation.

**Scope-cut rule**: drop whole stories, code and tests together, never code without its
tests (Constitution VIII). US4 then US3 are the drop order — P3 before P2. Neither owns a
file a later phase requires: T022–T024 depend on the verb set, not on US3/US4 artifacts.
