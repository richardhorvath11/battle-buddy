# Implementation Plan: Deterministic Layer

**Branch**: `002-deterministic-layer` | **Date**: 2026-07-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-deterministic-layer/spec.md`

## Summary

Build the five shipped deterministic components: `guardrail_deny.py` (PreToolUse deny
classes, misbehavior corpus as regression gate), `tool_trace.py` (PreToolUse turn-cap +
PostToolUse capture with `outcome` classification and injection tripwire),
`session_guard.py` (SessionStart config warning + SessionEnd marker check and
transcript staging), and the `bb-fingerprint` / `bb-validate` helpers (library + CLI).
All stdlib-only at the 3.9 floor, all fail-open, all tested as pure functions by the
slice-1 harness, with the local-state protocol pinned as a versioned contract document.

## Technical Context

**Language/Version**: Python 3, **3.9 floor** (shipped code — design D-1); CI matrix
3.9 + 3.12 proves both ends (slice-1 implementation merged in PR #6; this branch is
synced onto it and `make verify` runs its 97 tests green)

**Primary Dependencies**: none at runtime (stdlib only — Constitution Platform
Constraints, verified mechanically per SC-006); pytest dev-only

**Storage**: `.bb-session/` local-state files per `contracts/local-state-protocol.md`
(marker.json, trace.jsonl, counters.json, agents.json, staging/) — no external services

**Testing**: slice-1 pytest harness; table-driven fixtures for all five components;
two-corpus deny gate; fault-injection corpus for fail-open (SC-007); timing test (R8)

**Target Platform**: responder macOS/Linux machines (runtime), GitHub Actions (CI)

**Project Type**: shipped plugin components (`hooks/`, `bin/`) + their tests — first
slice to ship runtime code

**Performance Goals**: p95 < 100ms per hook invocation (SC-002; hooks run on every tool
call); trace appends O(1); auth-context reads bounded to the protocol's 10-line window

**Constraints**: fail-open under every internal failure (SC-007); no reads beyond the
three permitted sources (spec FR-002); append-only trace; no network

**Scale/Scope**: 3 hook scripts + 2 helpers + 1 protocol contract; ~10 fixture
directories; ≥1 unit test per protocol assertion

## Constitution Check

*GATE: evaluated pre-Phase-0 and re-evaluated post-Phase-1 — both passes clean.*

| Principle | Gate result |
|---|---|
| I — One Custom Component | ✅ Everything ships inside the plugin (`hooks/`, `bin/`); no server/storage/integration code |
| II — Deterministic Backstops | ✅ This slice *is* the backstop layer (D-11/D-12/D-14/D-17 made real) |
| III — Layered Guardrails | ✅ Deny layer + tripwire built to the constitutional letter: fail-open (SC-007), over-match with the corpus as the decided boundary, misbehaviors as regression tests, tripwire documented probabilistic |
| IV — Evidence Links+Excerpts | ✅ `bb-validate` enforces `{url, excerpt}` pairs (FR-006) |
| V — Causal Fields Human-Curated | ✅ N/A this slice (no drafting features) |
| VI — Validated Memory | ✅ `bb-validate` enforces provenance/validation/anchoring invariants — the principle's named enforcement mechanism |
| VII — Capability Contracts | ✅ Tripwire classifies via the binding map, never tool names; untrusted set grows only with the operation contract (R5) |
| VIII — Test-First, Agent-Led | ✅ Every component lands with table-driven tests in the same change; protocol doc assertions each get a test |
| Platform Constraints | ✅ Stdlib-only at 3.9 floor, mechanically verified (SC-006); per-responder credentials untouched (no credential handling in this slice) |

No violations — Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/002-deterministic-layer/
├── spec.md
├── plan.md                          # this file
├── research.md                      # R1–R9 (incl. spec-deferred: tripwire list, phase enum, config protocol)
├── data-model.md
├── quickstart.md                    # 10 validation scenarios
├── contracts/
│   └── local-state-protocol.md      # bb.local.v1 — the FR-013 artifact
├── checklists/requirements.md
└── tasks.md                         # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
hooks/
├── hooks.json                       # event registrations per research R1
├── guardrail_deny.py                # PreToolUse: DENY_CLASSES table, corpus-gated; appends denied:guardrail:* lines
├── tool_trace.py                    # PreToolUse (turn cap via counters) + PostToolUse (capture, outcome, tripwire)
├── session_guard.py                 # SessionStart (config warning) + SessionEnd (marker, transcript)
├── _config.py                       # shared read-only ConfigView helper (R6) — underscore: not a hook
└── _state.py                        # local-state protocol helpers: locked counters, trace append, marker read (R11) — not a hook; ships in the bundle like every hooks/ file

bin/
├── bb-fingerprint                   # CLI shim → bb_fingerprint.py
├── bb_fingerprint.py                # bb.fp.v1 normalization + hash (D-4)
├── bb-validate                      # CLI shim → bb_validate.py
└── bb_validate.py                   # schema + semantic invariants, one-pass JSON-lines output

tests/unit/
├── test_config_view.py              # R6 keys, defaults, malformed-config, reverse lookup
├── test_guardrail_deny.py           # two-corpus gate + context rule + fail-open
├── test_tool_trace.py               # capture/order/outcome, turn cap, tripwire (incl. degraded), parallel-append concurrency (R11)
├── test_session_guard.py            # four marker states, transcript staging, config warning
├── test_fingerprint.py              # golden corpus, both matrix ends, version-bump tripwire
├── test_validate.py                 # violation corpus, one-pass reporting, byte-identity
├── test_local_state_protocol.py     # one test per protocol-doc assertion (FR-013)
├── test_stdlib_boundary.py          # SC-006 import check over hooks/ + bin/
└── test_hook_latency.py             # R8 timing tripwire (SC-002)

tests/helpers/failopen.py            # shared fault-corpus runner (extends slice-1 tests/helpers/)

tests/fixtures/
├── misbehaviors/*.json              # must-block corpus (source-annotated)
├── benign/*.json                    # must-allow corpus (membership rule per spec US1 AS-2)
├── faults/*.json                    # fail-open corpus (SC-007)
├── outcomes/*.json                  # R4 classifier pairs
├── tripwire/*.json                  # trip/no-trip pairs per family + no-binding-map case
├── markers/*.json                   # four marker states
├── sessions/hundred-call.json       # scripted multi-agent session (SC-005)
├── validate/*.json                  # per-rule violation + valid documents
└── fingerprint/golden.json          # the executable §5.2 rules
```

**Structure Decision**: `hooks/` and `bin/` match the design §3.1 plugin layout exactly —
this slice starts the real shipped tree; tests extend the slice-1 harness in place.
`_config.py` lives in `hooks/` (shipped beside its consumers) with the underscore
convention marking it as a module, not a registered hook.

## Complexity Tracking

Not required — Constitution Check passed without violations.
