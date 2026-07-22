# Implementation Plan: Shell Adapter

**Branch**: `009-shell-adapter` | **Date**: 2026-07-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-shell-adapter/spec.md`

## Summary

Ship `bb-shell` — the single-screen surface and the first real shipped executable
beyond slice 2's hooks (design §6.3, §3.1, D-2, D-9): a Python 3 stdlib-only CLI shim
exposing four verbs (`open-pane`, `navigate-pane`, `notify`, `close-workspace`) over a
config-selected backend, with **degraded mode as the default and the universal fallback**.

Three implementations sit behind one dispatcher: a **cmux backend** speaking the real
`cmux-socket` v2 protocol (newline-delimited JSON over `AF_UNIX`, pinned empirically in
research R1–R3), a **degraded backend** that prints a link or message for every verb, and
the **fail-soft wrapper** that turns any socket, protocol, or error-response failure into
the degraded output with exit success (FR-005) — leaving usage errors as the one loud path
(FR-005, SC-006).

The test layer is `tests/unit/` per design §10's "`bb-shell` (fake socket)" line: a real
Unix-socket fake (not a monkeypatched module) that captures protocol traffic and injects
six fault classes, so the fail-soft matrix and the FR-006 credential-surface scan run on
bytes that actually crossed a socket. Two documents ship beside the shim — the
backend-independent contract (`bin/bb-shell.md`, FR-007/D-2) and the cmux mapping
(`bin/bb-shell.cmux.md`) — a split that makes US4's "no backend name outside the backend
doc" scan mechanically expressible.

Three cross-slice reconciliations land in the same change: `--level` becomes optional
defaulting to `info` so slice 4's landed doctor round-trip does not break (research R5),
`test_stdlib_boundary.py`'s allowlist gains `socket`/`bb_shell` as SC-005's deliberate
reviewed addition (research R9), and `bb-technical-design.md` records the fourth verb as a
**D-2 addendum** amending §6.3's three-verb block — the design's own gap, which the spec
pinned the *existence* of and delegated the naming to this plan (FR-001).

## Technical Context

**Language/Version**: **Python 3, stdlib only** — the binding constraint of this slice and
the first time it bites hard, since everything shipped so far in `bin/` was pure
computation and this talks to a socket. Floor is **3.9** (the unit layer's CI version;
design D-1) — no walrus-in-comprehension flourishes, no `dict |` merge, no
`str.removeprefix`. Imports are `argparse`, `json`, `os`, `socket`, `sys` and nothing else
(research R9).

**Primary Dependencies**: none shipped. cmux is an *adopted* external app reached over its
socket, never a dependency of the plugin — nothing imports it, and its absence is a normal,
silent, fully-functional state (FR-002/FR-003). pytest is dev-only.

**Storage**: none. The shim reads exactly one file — `.claude/settings.json` → `battleBuddy`
block, for backend selection — and writes none. FR-009's pure-function property
(`(arguments, config, socket behavior) → (exit code, output, protocol traffic)`) is what the
unit layer instruments.

**Testing**: `tests/unit/` only, per design §10 layer 1 ("`bb-shell` (fake socket)"). No
contract-layer work: `bb-mock-mcp` implements the §7.1 *capability* operations, and the
shell is not a capability — it is an adapter over a local app, so there is nothing for the
mock to double. Hermetic by construction: a `tmp_path` Unix socket, no network, no cmux, no
credentials. Runs under `make verify` on the 3.9 floor and 3.12.

**Target Platform**: the responder's machine. cmux is macOS-only (R-1) — which is exactly
why degraded mode is first-class rather than a fallback: the **tests** run degraded and
fake-socket paths on every platform CI uses, so the non-Mac path is the one with the
strongest coverage, not the weakest.

**Project Type**: shipped CLI shim (`bin/`) + its interface documentation + unit tests.

**Performance Goals**: no perceptible latency in the 3am path (NFR-1). Every call is local
IPC; the pinned 2.0s socket timeout (research R7) is a *wedged-app* bound, not a
steady-state target — a healthy call is sub-millisecond and a dead backend must not make
the responder wait.

**Constraints**: fail-soft is absolute for backend availability and absolutely *not* for
caller bugs (FR-005) — the two paths must never be conflated, and SC-003/SC-006 count both
directions; the interface must be structurally incapable of credential access (FR-006),
which is a property of the *argument grammar*, not of a runtime check; the shim holds no
state between invocations (FR-009), so reattach is a backend read, never shim memory.

**Scale/Scope**: 1 shim + 1 module (~350 lines shipped) + 2 interface docs; 1 fake-socket
test helper; 4 unit-test modules; 1 stdlib-allowlist extension; 1 design-doc amendment
(§6.3 + D-2 addendum). No changes to any command, skill, or agent — this slice *is* the
surface they already call.

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ `bb-shell` is named in §3.1's bundle layout and D-2 as a shipped helper — it is the one custom component doing exactly what the design allocated to it. No server, no database, no storage code. The line worth naming: this is a **bespoke integration with one external tool**, which Principle I forbids *for MCP-backed capabilities* (tier 0 storage goes through the team's own MCPs). The shell is not such a capability — it is the adapter D-2 pins precisely so the core stays shell-agnostic, and the interface doc doubles as the spec any replacement implements. Recorded, not waved past |
| II — Deterministic Backstops | ✅ The slice is nearly all backstop: the fail-soft guarantee is exercised as a six-fault × four-verb matrix (SC-003), the credential boundary is a scan over captured traffic (SC-004), and the stdlib boundary is an existing walk over `bin/` (SC-005). Honest limit: "cmux behaves as probed" is not backstopped by CI and cannot be — the fake socket asserts *our* framing, not cmux's fidelity. Research R2 and R11 name the two residual gaps rather than implying coverage |
| III — Layered Guardrails | ✅ No new guardrail surface, and no security *guarantee* rests on this slice. FR-006's boundary is structural (layer-1-shaped: the grammar admits no credential operation), not probabilistic — which is the only kind of claim §8/Principle III permits. Constitution III's fail-open rule is cited **by analogy only**; the binding authorities for fail-soft are the Platform Constraints and §9's R-2 row, exactly as the spec states |
| IV — Evidence Links+Excerpts | ✅ Not this slice's shape. `navigate-pane` *consumes* the URL half of an evidence entry (FR-9 deep-linking) and never produces, stores, or validates evidence — the shim sees a URL string and a pane handle, nothing more |
| V — Causal Fields Human-Curated | ✅ Untouched. No causal content crosses this surface; `notify` carries a message the caller composed |
| VI — Validated Memory | ✅ Untouched. No recall semantics |
| VII — Capability Contracts | ✅ Honored in its *spirit*, which is the interesting reading here. The letter of VII governs **MCP** capabilities and tool names; a shell backend is neither. The spirit — cores never name concrete products — is what FR-002/FR-007 enforce and US4 AS2 scans: commands and skills say `bb-shell`, never `cmux`, and the only place the product is named is the backend document and the config value (`battleBuddy.shell: cmux`), which is the same standing `templates/mcp.recommended.json` has under VII |
| VIII — Test-First, Agent-Led | ✅ Every user story's code and tests land in the same commit, and the phase is the commit seam. Assertions are on artifacts — exit codes, stdout/stderr text, captured socket bytes — never on prose. SC-001 maps every FR to ≥1 test in `quickstart.md`. Note that FR-006 is verified two ways, since one is weak alone: a scan of captured traffic (behavioral) **and** an assertion over the argument grammar (structural), because a scan only proves the *tested* calls stayed clean |
| Platform Constraints | ✅ The slice's defining constraint. Stdlib-only is gated by the existing `test_stdlib_boundary.py` walk, whose allowlist grows by exactly one module (`socket`) as a reviewed diff (research R9); the 3.9 floor binds. Degraded mode as a first-class path is not merely respected here — it is the subject: it is the default, the fallback, and the only path guaranteed on every platform |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/009-shell-adapter/
├── spec.md
├── plan.md                      # this file
├── research.md                  # R1–R14: the cmux protocol pinned against the real API,
│                                #   verb/param mapping, level encoding, fault taxonomy,
│                                #   exit codes, allowlist delta, and the two residual gaps
├── data-model.md                # Phase 1: verb grammar, backend interface, request/response
│                                #   envelope, fault matrix, config selection table
├── quickstart.md                # Phase 1: FR → test module map; how to run the suite
├── checklists/requirements.md
└── tasks.md                     # Phase 2 (/speckit-tasks)
```

No `specs/…/contracts/` directory — slice-3/6/7 precedent: this slice's contract artifact
**is** the shipped deliverable. `bin/bb-shell.md` is the normative backend-independent
interface (FR-007 requires it to ship, since a future shell integrator reads it), and
duplicating it under `specs/` would create a second source of truth for the exact content
D-2 pins. The cmux wire details live in `research.md` (plan-time evidence) and
`bin/bb-shell.cmux.md` (shipped mapping).

### Source Code (repository root)

```text
bin/
├── bb-shell                     # FR-001: extensionless launcher, `#!/usr/bin/env python3`,
│                                #   sys.path-inserts its own dir, calls main()
│                                #   (bb-validate/bb-fingerprint precedent, research R8)
├── bb_shell.py                  # the implementation: argument grammar + dispatch,
│                                #   config selection (FR-002), CmuxBackend (FR-004),
│                                #   DegradedBackend (FR-003), fail-soft wrapper (FR-005)
├── bb-shell.md                  # FR-007/D-2: the backend-independent adapter contract —
│                                #   per-verb arguments, semantics, degraded behavior,
│                                #   failure behavior. Names no concrete backend
└── bb-shell.cmux.md             # the cmux backend mapping: socket discovery, framing,
                                 #   method/param table, level encoding, pane→surface

tests/helpers/
└── fake_cmux.py                 # research R7: a real Unix-socket listener on tmp_path —
                                 #   captures every request frame, scripts responses, and
                                 #   injects absent/refused/timeout/mid-write-death/
                                 #   error-response/malformed-line faults

tests/unit/
├── test_shell_dispatch.py       # US1/US4 + SC-006: argument grammar as a pure function,
│                                #   verb dispatch, usage errors exit 2, --level default
│                                #   and unrecognized-level rejection (research R5)
├── test_shell_degraded.py       # US1 + SC-002: degraded output for all four verbs across
│                                #   all three selection paths (none / absent / unrecognized)
│                                #   + the notice-scoping split (FR-002)
├── test_shell_cmux.py           # US1 + FR-004: protocol framing against the fake socket —
│                                #   request envelope, method+param mapping per verb,
│                                #   response parsing with varied key order, workspace
│                                #   create-vs-reattach, URL-vs-command target typing
└── test_shell_failsoft.py       # US2/US3 + SC-003/SC-004: the six-fault × four-verb matrix
                                 #   (degraded output, exit 0, diagnostic note, no hang),
                                 #   per-invocation independence, and the credential-surface
                                 #   scan over all captured traffic + the grammar assertion

tests/unit/test_stdlib_boundary.py   # research R9: ALLOWED_STDLIB += socket;
                                     #   LOCAL_MODULES += bb_shell (SC-005)

bb-technical-design.md               # §6.3 interface block + D-2 addendum: the fourth verb
                                     #   (spec FR-001's delegated pin, resolved in research R6)
```

**Structure Decision**: `bin/` is where §3.1's bundle layout already places `bb-shell`, and
the shim/module split copies the two landed `bin/` helpers exactly — one implementation
serving both shell-outs and (future) import-style callers. The interface docs go in `bin/`
rather than a new top-level `docs/` because AGENTS.md's Allowed tier enumerates the plugin
directories and `bin/` is one of them; adding a bundle root is a packaging decision this
slice does not need to make (research R13). Tests extend `tests/unit/` in place — the layer
design §10 names for this component — and `tests/helpers/fake_cmux.py` joins the existing
helper convention. **No command, skill, or agent file changes**: slices 4 and 5 already call
this surface through fixtures, and this slice makes the fixtures' real counterpart exist.

## Complexity Tracking

Not required — Constitution Check passed without violations.
