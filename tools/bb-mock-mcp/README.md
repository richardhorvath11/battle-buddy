# bb-mock-mcp

**Dev-only.** This package is the in-memory executable specification of the
operation contract — used in-process by the contract test layer, never shipped
to responders (Constitution I; spec FR-010 — the packaging boundary check in
`tests/unit/test_packaging.py` enforces this mechanically).

The contract's authority is
[`specs/001-test-scaffold/contracts/operations.md`](../../specs/001-test-scaffold/contracts/operations.md);
`contract.json` here is its machine-readable encoding, and the mock's behavior,
its schema registry (`describe()`, FR-011), and the conformance tests in
`tests/contract/` all load that one file so they cannot drift independently.

## Usage

Tests get a fresh instance per test via the `mock_mcp` fixture in
`tests/conftest.py`. Call `invoke(capability, op, payload)` for contract
operations (rejections come back as `{"error": {"op", "code", "message"}}`),
`describe()` for the per-capability schema surface without invoking anything,
and `load_seed(path)` to load a declarative seed fixture (all-or-nothing,
bypasses the write log). Test-inspection surface: `records.records`,
`artifacts.files`, `diary.entries`, `alerting.alerts` / `alerting.history`,
and `write_log.entries` (ordered `{seq, capability, op, summary}`).

The only dev dependency for the whole harness is pytest: `pip install pytest`.
