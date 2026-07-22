# Quickstart: Shell Adapter (slice 9)

How to validate this slice, and the FR → test map that SC-001 requires.

## Run it

```bash
make verify                                  # the gate: unit + contract layers
make test-unit                               # layer 1 only — where this slice lives
pytest tests/unit/test_shell_failsoft.py -q  # the fault matrix alone
```

Hermetic by construction: no cmux, no network, no credentials. The fake backend is a real
Unix socket on `tmp_path` (research R7), so framing and teardown are exercised for real.

## Exercise the shim by hand

Degraded mode needs no configuration at all — that is the point (FR-002/FR-003):

```bash
bin/bb-shell notify "triage complete" --level approval    # -> bb-shell: [approval] triage complete
bin/bb-shell open-pane https://grafana.example/d/abc      # -> bb-shell: open https://…
bin/bb-shell navigate-pane surface:4 https://example.com  # -> bb-shell: https://… (pane surface:4)
bin/bb-shell close-workspace page-ALERT-1-2026-07-22      # -> bb-shell: close workspace page-…
echo $?                                                   # 0, every time

bin/bb-shell bogus-verb                                   # usage on stderr
echo $?                                                   # 2 — the one loud path
```

Against a real cmux (macOS, cmux running), add `{"battleBuddy": {"shell": "cmux"}}` to
`.claude/settings.json`. Kill cmux mid-session and re-run any verb: the output becomes the
printed form and the exit code stays `0` (FR-005). That contrast **is** user story 2.

## FR → test map (SC-001)

| Requirement | Verified by |
|---|---|
| FR-001 four-verb interface | `test_shell_dispatch.py` — grammar, dispatch, all four verbs |
| FR-002 config selection | `test_shell_degraded.py` — the six-state selection table incl. the absent-silent / unrecognized-noticed split |
| FR-003 degraded renders every verb | `test_shell_degraded.py` — four verbs × three selection paths |
| FR-004 cmux backend | `test_shell_cmux.py` — envelope, method+param mapping, create-vs-reattach, target typing |
| FR-005 fail soft; usage errors loud | `test_shell_failsoft.py` (24-case matrix) + `test_shell_dispatch.py` (exit 2) |
| FR-006 no credential surface | `test_shell_failsoft.py` — captured-traffic scan **and** the method-allowlist assertion; `test_shell_dispatch.py` — grammar rejects anything else |
| FR-007 interface documented backend-independently | `test_shell_dispatch.py` — `bin/bb-shell.md` exists, documents all four verbs, and names no backend product |
| FR-008 hermetic unit coverage | the suite itself; `make verify` |
| FR-009 pure function / stateless | `test_shell_failsoft.py` — per-invocation independence; no file writes |

| Success criterion | Verified by |
|---|---|
| SC-001 every FR ≥1 test | this table |
| SC-002 degraded correct on all three selection paths | `test_shell_degraded.py` |
| SC-003 100% of fault cases degrade, exit 0, note, no hang | `test_shell_failsoft.py` |
| SC-004 captured traffic carries nothing else | `test_shell_failsoft.py` scan |
| SC-005 zero third-party imports | existing `test_stdlib_boundary.py` (allowlist +`socket`, +`bb_shell`) |
| SC-006 usage errors exit nonzero | `test_shell_dispatch.py` |

## What this does not prove

Stated so the gate is not mistaken for more than it is:

- **That cmux behaves as probed.** The fake asserts *our* framing. Research R1–R3 pinned
  the real protocol empirically on 2026-07-22; drift in cmux is caught by a human running
  the manual steps above, not by CI. R2 and R11 name the two residual gaps.
- **That a live agent invokes the shim correctly.** Command/skill behavior is scenario-
  harness territory (design §10), the same boundary slices 5–7 drew.
