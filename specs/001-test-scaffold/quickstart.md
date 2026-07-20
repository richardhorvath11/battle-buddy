# Quickstart: validating slice 1

Prerequisites: Python 3.11+, `pip install pytest` (or `uv pip install pytest`). Nothing
else — no credentials, no network (SC-001/SC-002; try it offline to prove hermeticity).

```bash
make verify          # both layers; expect "verify: green", < 30s
make test-unit       # layer 1 alone
make test-contract   # layer 2 alone
```

Validation scenarios (all must hold at slice completion):

1. **Green path**: fresh clone → `make verify` exits 0, prints per-layer results.
2. **Red path**: break an invariant (e.g. edit the D-3 size limit in
   `tools/bb-mock-mcp/contract.json` to 10) → `make verify` exits non-zero naming the
   failing conformance test; revert.
3. **Conformance coverage**: `pytest tests/contract -q --collect-only` lists ≥1 test per
   operation in [contracts/operations.md](contracts/operations.md) (SC-003).
4. **Ordering assertion**: the dual-write ordering demo test passes and its assertion
   reads the write log (SC-004) — see `tests/contract/test_write_ordering.py`.
5. **Seed fixtures**: `tests/contract/test_seeds.py` loads the synthetic incident seed and
   the corrupted-seed fixture fails naming the bad entry (Story 3).
6. **Packaging boundary**: `tests/unit/test_packaging.py` passes on the intended-bundle
   fixture and fails on the mis-packaged fixture (SC-007).
7. **CI mirror**: the PR for this slice shows the `verify` workflow green, running the
   same make targets (FR-009/SC-005).
