# Quickstart — Validating Doctor & Setup (slice 4)

Everything is hermetic: no credentials, no network, pytest only.

## Prerequisites

```bash
pip install pytest        # the harness's only dev dependency
make verify               # baseline must be green before this slice's work
```

## The one gate

```bash
make verify               # unit + contract layers (Constitution VIII)
make test-contract        # this slice's layer, alone
```

## Validation scenarios → test modules

| Scenario (spec) | Drive it | Expect |
|---|---|---|
| US2/SC-002 — binding resolution over a full roster | `pytest tests/contract/test_binding_resolution.py` | 100% required ops resolved; entries parse under `capability.operation`; missing-op roster fails naming the op; multi-match surfaces `ambiguous` + candidates; drifted map flags stale entries by name |
| US2 — doctor checks + report | `pytest tests/contract/test_doctor_checks.py` | per-check `bb.doctor.report.v1` outcomes: probes (report is the oracle — reads leave no write log), config validity, version seam (exact migration strings), shell round-trip ok/fail/skip |
| US2/US3 — reduced features & stamp | `pytest tests/contract/test_doctor_report.py tests/contract/test_stamp_lifecycle.py` | optional-missing ⇒ green + exact `enables` lists; green run writes 3-field stamp; plugin-version/roster-hash change ⇒ stale; timestamp never expiry-checked |
| US1/SC-003/SC-004 — team mode end-to-end | `pytest tests/contract/test_setup_team_mode.py` | full sequence order; header written through storage binding matching `COLUMN_NAMES` + sentinel; existing-store validate/mismatch paths (zero writes); smoke-test row `session_type: test` exercising all four paths, excluded from retrieval |
| US3 — responder mode | `pytest tests/contract/test_setup_responder_mode.py` | probes under responder credentials; stamp written; team-resource write log unchanged |
| US4/SC-005 — idempotence | `pytest tests/contract/test_setup_idempotence.py` | second run: zero mutating ops, already-green report; partial states do only what's missing; malformed config ⇒ repair, never re-create |
| FR-001 — manifest fidelity | `pytest tests/contract/test_capability_manifest.py` | required half ≡ `contract.json` shapes; optional half carries §7.1 ops + `enables` |
| FR-010 — naming gate | `pytest tests/contract/test_command_capability_naming.py` | no concrete server/tool names in `commands/`, `manifest/`, `templates/session-sheet.md`; `templates/mcp.recommended.json` is the sole allowed location |

## Reading a failure

Contract tests assert on artifacts: the `bb.doctor.report.v1` document, the mock's
`write_log.entries`, stamp file fields, scaffolded file sets — never prose. A failing
assertion names the check id / write-log seq / field it expected; cross-reference
[`contracts/doctor-protocol.md`](contracts/doctor-protocol.md) for the normative rule.
