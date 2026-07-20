# Quickstart: validating slice 2

Prerequisites: slice 1 merged (`make verify` green, pytest installed). Everything below is
hermetic — no network, no credentials.

```bash
make verify          # both layers; slice-2 unit tests now populate layer 1
pytest tests/unit -q # layer 1 alone (all five components live here)
```

Validation scenarios (all must hold at slice completion):

1. **Misbehavior gate**: every fixture in `tests/fixtures/misbehaviors/` is blocked with
   its expected class; every fixture in `tests/fixtures/benign/` is allowed (SC-001).
   Add a new misbehavior fixture with `expected: "block"` and watch the suite fail until
   the deny table covers it.
2. **Fail-open**: the fault corpus (malformed stdin, unreadable state dir, seeded
   exceptions) yields allow/proceed for 100% of cases, with diagnostics (SC-007).
3. **Fingerprint stability**: golden corpus passes on 3.9 and 3.12 (CI matrix); flip one
   normalization rule locally and the corpus fails (SC-003).
4. **Validator corpus**: every schema rule and semantic invariant has a violating fixture
   caught, all violations of a multi-violation document reported in one pass (SC-004);
   valid documents pass byte-identical.
5. **Trace + budget**: the scripted 100-call session fixture yields exactly 100 ordered
   lines with `outcome` fields; call N+1 by the triage agent is denied at cap N with the
   emit-your-verdict message (SC-005). Denied call appears as `denied:turn_cap`.
6. **Tripwire**: instruction-shaped fixture from an untrusted-capability tool → one
   advisory + one tripwire trace event; same fixture with no binding map → no advisory,
   one disabled-notice (US4 Independent Test).
7. **Session guard states**: marker fixtures (absent / open-unconfirmed /
   open-confirmed-never-closed / cleared-by-deletion) → warnings on exactly the two
   present states; transcript fixture copied to `staging/`; config-absent fixture →
   FR-015 warning (US5 Independent Test).
8. **Protocol conformance**: every format/location assertion in
   [contracts/local-state-protocol.md](contracts/local-state-protocol.md) has a passing
   unit test (FR-013 acceptance).
9. **Stdlib boundary**: the import-check test proves zero third-party imports in
   `hooks/` and `bin/` (SC-006, extends slice 1's packaging check).
10. **Latency**: the R8 timing test passes — p95 well under 100ms per hook invocation
    (SC-002).
